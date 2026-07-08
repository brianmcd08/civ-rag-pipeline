from langchain_core.tools import tool
from src.config import K_GENERAL, K_SECTION
from src.retrieval.retriever import hybrid_query
from src.utils import format_docs


def _build_filter(section_filter: dict | None, version: str | None) -> dict | None:
    if section_filter and version:
        return {"$and": [section_filter, {"bbg_version": {"$eq": version}}]}
    elif section_filter:
        return section_filter
    elif version:
        return {"bbg_version": {"$eq": version}}
    else:
        return None


@tool
def search_units(query: str, version: str | None = None) -> str:
    """Search for a specific unit or unit attributes.
    Pass version if the user specified one."""
    section_filter = {"section": {"$eq": "units"}}
    docs = hybrid_query(
        query,
        k=K_SECTION,
        filter=_build_filter(section_filter=section_filter, version=version),
    )
    return format_docs(docs)


@tool
def search_leaders(query: str, version: str | None = None) -> str:
    """Search for civilization leaders and their unique abilities. For a civ's
    unique unit (e.g. the Aztec unique unit), use search_units instead; for its
    unique building or improvement, use search_buildings_and_improvements.
    Pass version if the user specified one."""
    section_filter = {"section": {"$eq": "leaders"}}
    docs = hybrid_query(
        query,
        k=K_SECTION,
        filter=_build_filter(section_filter=section_filter, version=version),
    )
    return format_docs(docs)


@tool
def search_great_people(query: str, version: str | None = None) -> str:
    """Search for a great person, their unique abilities, and their era.
    Pass version if the user specified one."""
    section_filter = {"section": {"$eq": "great_people"}}
    docs = hybrid_query(
        query,
        k=K_SECTION,
        filter=_build_filter(section_filter=section_filter, version=version),
    )
    return format_docs(docs)


@tool
def search_techs_and_civics(query: str, version: str | None = None) -> str:
    """Search for a particular technology or civic, or for their prerequisites or what abilities or policies they unlock.
    Pass version if the user specified one."""
    section_filter = {"section": {"$in": ["tech_tree", "civic_tree"]}}
    docs = hybrid_query(
        query,
        k=K_SECTION,
        filter=_build_filter(section_filter=section_filter, version=version),
    )
    return format_docs(docs)


@tool
def search_buildings_and_improvements(query: str, version: str | None = None) -> str:
    """Search for a building or a tile improvement.
    Pass version if the user specified one."""
    section_filter = {"section": {"$in": ["buildings", "improvements"]}}
    docs = hybrid_query(
        query,
        k=K_SECTION,
        filter=_build_filter(section_filter=section_filter, version=version),
    )
    return format_docs(docs)


@tool
def search_general(query: str, version: str | None = None) -> str:
    """Search for changelogs, policies, congress, religion, natural wonders, world wonders, bbg expanded, governors, city states, names of things, era dedications
    Pass version if the user specified one."""
    docs = hybrid_query(
        query, k=K_GENERAL, filter=_build_filter(section_filter=None, version=version)
    )
    return format_docs(docs)
