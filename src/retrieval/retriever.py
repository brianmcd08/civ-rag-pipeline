import os
from typing import Any, cast

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, QueryResponse, SparseValues
from pinecone.config import ConfigBuilder
from pinecone.db_data.index import Index
from pinecone.openapi_support.retry_urllib3 import JitterRetry
from pinecone_text.sparse import BM25Encoder, SparseVector

from src.config import (
    ALPHA,
    BM25_MODEL_PATH,
    EMBEDDINGS_MAX_RETRIES,
    EMBEDDINGS_MODEL,
    EMBEDDINGS_REQUEST_TIMEOUT,
    PINECONE_MAX_RETRIES,
    PINECONE_REQUEST_TIMEOUT,
)
from src.secrets import get_secret

os.environ["OPENAI_API_KEY"] = get_secret("OPENAI_API_KEY")
os.environ["PINECONE_API_KEY"] = get_secret("PINECONE_API_KEY")

_api_key = get_secret("PINECONE_API_KEY")
_host = Pinecone(api_key=_api_key).describe_index(get_secret("PINECONE_INDEX_NAME_V2")).host
_openapi_config = ConfigBuilder.build_openapi_config(
    ConfigBuilder.build(api_key=_api_key, host=_host)
)
# The SDK declares retries as None with no annotation, so the checker infers
# NoneType. Correct at runtime; the client reads whatever is assigned here.
_openapi_config.retries = JitterRetry(  # pyright: ignore[reportAttributeAccessIssue]
    total=PINECONE_MAX_RETRIES,
    backoff_factor=0.25,
    status_forcelist=(500, 502, 503, 504),
    allowed_methods=None,
)
index = Index(api_key=_api_key, host=_host, openapi_config=_openapi_config)

embeddings = OpenAIEmbeddings(
    model=EMBEDDINGS_MODEL, max_retries=EMBEDDINGS_MAX_RETRIES, timeout=EMBEDDINGS_REQUEST_TIMEOUT
)
bm25_encoder = BM25Encoder()
bm25_encoder.load(BM25_MODEL_PATH)


def hybrid_query(query: str, k: int, filter: dict[str, Any] | None = None) -> list[Document]:
    dense = embeddings.embed_query(query)
    sparse_result = bm25_encoder.encode_queries(query)
    sparse: SparseVector = sparse_result if isinstance(sparse_result, dict) else sparse_result[0]
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
            _request_timeout=PINECONE_REQUEST_TIMEOUT,
        ),
    )

    return [
        Document(
            page_content=match.metadata.get("context", ""),
            metadata={key: val for key, val in match.metadata.items() if key != "context"},
        )
        for match in result.matches
    ]
