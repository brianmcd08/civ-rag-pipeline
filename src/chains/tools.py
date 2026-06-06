from langchain_core.tools import tool
from src.retrieval.retriever import hybrid_query
from src.utils import format_docs


@tool
def search_units(query: str) -> str:
    """Search for a specific unit or unit attributes."""
    docs = hybrid_query(query, k=5, filter={"section": {"$eq": "units"}})
    return format_docs(docs)


@tool
def search_leaders(query: str) -> str:
    """Search for civilization leaders, their unique abilities, unique units, and unique improvements."""
    docs = hybrid_query(query, k=5, filter={"section": {"$eq": "leaders"}})
    return format_docs(docs)


@tool
def search_great_people(query: str) -> str:
    """Search for a great person, their unique abilities, and their era."""
    docs = hybrid_query(query, k=5, filter={"section": {"$eq": "great_people"}})
    return format_docs(docs)


@tool
def search_techs_and_civics(query: str) -> str:
    """Search for a particular technology or civic, or for their prerequisites or what abilities or policies they unlock."""
    docs = hybrid_query(
        query, k=5, filter={"section": {"$in": ["tech_tree", "civic_tree"]}}
    )
    return format_docs(docs)


@tool
def search_buildings_and_improvements(query: str) -> str:
    """Search for a building or a tile improvement."""
    docs = hybrid_query(
        query, k=5, filter={"section": {"$in": ["buildings", "improvements"]}}
    )
    return format_docs(docs)


@tool
def search_general(query: str) -> str:
    """Search for changelogs, policies, congress, religion, natural wonders, world wonders, bbg expanded, governors, city states, names of things, era dedications"""
    docs = hybrid_query(query, k=8, filter=None)
    return format_docs(docs)
