"""Side-effect-free constants and enums.

STDLIB IMPORTS ONLY. Nothing in this module may import `src.config`,
`src.secrets`, langchain, or any other third-party package.

`src/config.py` mutates `os.environ` at import time and constructs a live
`ChatAnthropic`/`ChatBedrockConverse` client, so importing it requires an API
key and a working provider. The thin Streamlit client (and any test that only
needs an enum) must be able to get these values without paying that cost.

`src/config.py` re-exports everything here, so existing import sites are
unchanged.
"""

from enum import StrEnum


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


# App
API_KEY_HEADER_NAME = "X-API-Key"
HISTORY_LIMIT = 4
RECURSION_LIMIT = 25
CHUNK_CONTENT_LIMIT = 1500
