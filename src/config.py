import os

from langchain_anthropic import ChatAnthropic
from enum import StrEnum
from src.secrets import get_secret


os.environ["ANTHROPIC_API_KEY"] = get_secret("ANTHROPIC_API_KEY")


class Version(StrEnum):
    V75 = "7.5"
    V74 = "7.4"
    V73 = "7.3"
    V72 = "7.2"
    V71 = "7.1"
    VBASE = "base_game"

    @classmethod
    def to_list_of_strings(cls):
        return "\n".join([v.value for v in cls])

    @classmethod
    def get_latest_version(cls):
        return next(iter(cls))


class Section(StrEnum):
    LEADERS = "leaders"
    GREATPEOPLE = "great_people"
    MISC = "misc"
    CONGRESS = "congress"
    IMPROVEMENTS = "improvements"
    UNITS = "units"
    BUILDINGS = "buildings"
    CHANGELOG = "changelog"
    CITYSTATES = "city_states"
    GOVERNORS = "governor"
    BBGEXPANDED = "bbg_expanded"
    NAMES = "names"
    NATURALWONDER = "natural_wonder"
    POLICIES = "policies"
    RELIGION = "religion"
    TECHTREE = "tech_tree"
    CIVICTREE = "civic_tree"
    WORLDWONDER = "world_wonder"


# LLM
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_JUDGE = "claude-sonnet-4-6"
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

# App
HISTORY_LIMIT = 4
RECURSION_LIMIT = 10
CHUNK_CONTENT_LIMIT = 1500


llm = ChatAnthropic(model_name=ANTHROPIC_MODEL, stop=[], timeout=LLM_TIMEOUT)
