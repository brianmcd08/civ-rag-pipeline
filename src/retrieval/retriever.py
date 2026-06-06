import os
from typing import Any, cast

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, QueryResponse, SparseValues
from pinecone_text.sparse import BM25Encoder, SparseVector

from src.secrets import get_secret

os.environ["OPENAI_API_KEY"] = get_secret("OPENAI_API_KEY")
os.environ["PINECONE_API_KEY"] = get_secret("PINECONE_API_KEY")

pc = Pinecone(api_key=get_secret("PINECONE_API_KEY"))
index = pc.Index(get_secret("PINECONE_INDEX_NAME_V2"))
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
bm25_encoder = BM25Encoder()
bm25_encoder.load("models/bm25_values.json")
ALPHA = 0.5


def hybrid_query(
    query: str, k: int, filter: dict[str, Any] | None = None
) -> list[Document]:
    dense = embeddings.embed_query(query)
    sparse_result = bm25_encoder.encode_queries(query)
    sparse: SparseVector = (
        sparse_result if isinstance(sparse_result, dict) else sparse_result[0]
    )
    scaled_dense = [v * ALPHA for v in dense]
    scaled_sparse = SparseValues(
        indices=cast(list[int], sparse["indices"]),
        values=[v * (1 - ALPHA) for v in sparse["values"]],
    )

    result = cast(
        QueryResponse,
        index.query(
            vector=scaled_dense,
            sparse_vector=scaled_sparse,
            top_k=k,
            filter=filter,
            include_metadata=True,
        ),
    )

    return [
        Document(
            page_content=match.metadata.get("context", ""),
            metadata={
                key: val for key, val in match.metadata.items() if key != "context"
            },
        )
        for match in result.matches
    ]
