import os
import time

from dotenv import load_dotenv
from langchain_community.retrievers import PineconeHybridSearchRetriever
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec
from pinecone_text.sparse import BM25Encoder
from src.logging_config import logger

from src.config import (
    ALPHA,
    BM25_MODEL_PATH,
    EMBEDDINGS_MODEL,
    INDEX_CLOUD,
    INDEX_DIMENSION,
    INDEX_METRIC,
    INDEX_REGION,
    K_INGEST,
)
import src.scraping.scrape_orchestrator as scrape_orchestrator
from src.schema import UnifiedEntry

load_dotenv()


def get_batches(lst, batch_size):
    for i in range(0, len(lst), batch_size):
        yield lst[i : i + batch_size]


def deduplicate(entries):
    groups = {}  # hash -> (entry, [versions])
    for entry in entries:
        h = entry.generate_hash()
        if h not in groups:
            groups[h] = (entry, [])
        groups[h][1].append(str(entry.version))
    return list(groups.values())


def get_texts(entries):
    return [entry.generate_embedding_text() for entry, _ in entries]


def main():
    entries: list[UnifiedEntry] = scrape_orchestrator.run_all()
    logger.info("Total scraped entries", total_entries=len(entries))
    deduplicated_entries = deduplicate(entries)
    logger.info(
        "Total entries after deduplication", total_entries=len(deduplicated_entries)
    )
    bm25_encoder = BM25Encoder(language="english", remove_stopwords=True, stem=True)
    bm25_encoder.fit(get_texts(deduplicated_entries))
    os.makedirs("models", exist_ok=True)
    bm25_encoder.dump(BM25_MODEL_PATH)

    # wait for index to be available
    time.sleep(5)

    logger.info("BM25 Encoder successfully fit and saved")

    # Initialize the embedding model
    embeddings = OpenAIEmbeddings(model=EMBEDDINGS_MODEL)

    # Initialize Pinecone and ensure index exists
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index_name = os.environ["PINECONE_INDEX_NAME_V2"]

    if index_name not in [idx.name for idx in pc.list_indexes()]:
        pc.create_index(
            name=index_name,
            dimension=INDEX_DIMENSION,
            metric=INDEX_METRIC,
            spec=ServerlessSpec(cloud=INDEX_CLOUD, region=INDEX_REGION),
        )
        logger.info("Created Pinecone index", index_name=index_name)
    else:
        logger.info("Using existing Pinecone index", index_name=index_name)

    retriever = PineconeHybridSearchRetriever(
        embeddings=embeddings,
        sparse_encoder=bm25_encoder,
        index=pc.Index(index_name),
        top_k=K_INGEST,
        alpha=ALPHA,
    )

    for batch_num, batch in enumerate(get_batches(deduplicated_entries, 200)):
        texts = get_texts(batch)
        metadatas = [
            {**entry.generate_metadata(), "bbg_version": versions}
            for entry, versions in batch
        ]
        ids = [entry.generate_hash() for entry, _ in batch]

        try:
            retriever.add_texts(texts=texts, metadatas=metadatas, ids=ids)
            logger.info(
                "Batch Upsert",
                batch_num=batch_num,
                batch_size=len(batch),
                sections={m["section"] for m in metadatas},
                bbg_versions={
                    bbg_version for m in metadatas for bbg_version in m["bbg_version"]
                },
                status="success",
            )
        except Exception as error:
            logger.error(
                "Batch Upsert",
                batch_num=batch_num,
                batch_size=len(batch),
                sections={m["section"] for m in metadatas},
                bbg_versions={
                    bbg_version for m in metadatas for bbg_version in m["bbg_version"]
                },
                status="error",
                error_type=type(error).__name__,
                error_msg=str(error),
            )

    logger.info("Ingestion complete")


if __name__ == "__main__":
    main()
