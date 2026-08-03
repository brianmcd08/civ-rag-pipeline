import os

from src.constants import (  # noqa: F401  (re-exported for existing import sites)
    API_KEY_HEADER_NAME,
    CHUNK_CONTENT_LIMIT,
    HISTORY_LIMIT,
    RECURSION_LIMIT,
    Section,
    Version,
)
from src.secrets import get_secret

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
if LLM_PROVIDER != "bedrock":
    os.environ["ANTHROPIC_API_KEY"] = get_secret("ANTHROPIC_API_KEY")


# LLM
# ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_JUDGE = "claude-haiku-4-5"
LLM_TIMEOUT = 30

# Ingestion
K_INGEST = 25

# Retrieval
ALPHA = 0.5
K_SECTION = 5
K_GENERAL = 8

# Embeddings
EMBEDDINGS_MODEL = "text-embedding-3-small"
BM25_MODEL_PATH = "models/bm25_values.json"

# Pinecone
INDEX_DIMENSION = 1536
INDEX_CLOUD = "aws"
INDEX_METRIC = "dotproduct"
INDEX_REGION = "us-east-1"

# App constants (API_KEY_HEADER_NAME, HISTORY_LIMIT, RECURSION_LIMIT,
# CHUNK_CONTENT_LIMIT) and the Version/Section enums now live in
# src/constants.py and are re-exported by the import at the top of this file.


if LLM_PROVIDER == "bedrock":
    from langchain_aws import ChatBedrockConverse

    llm = ChatBedrockConverse(model=os.environ["BEDROCK_MODEL_ID"])
else:
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(model_name=ANTHROPIC_MODEL, stop=[], timeout=LLM_TIMEOUT)
