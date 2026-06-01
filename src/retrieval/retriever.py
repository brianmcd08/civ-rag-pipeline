# Given a clean query string and an optional version string (parsed from the chain),
# return relevant Documents. This file knows nothing about LLMs or intent parsing.

import os
from typing import Any

from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.schema import RetrieverState
from src.secrets import get_secret

os.environ["OPENAI_API_KEY"] = get_secret("OPENAI_API_KEY")
os.environ["PINECONE_API_KEY"] = get_secret("PINECONE_API_KEY")

vector_store = PineconeVectorStore(
    index_name=get_secret("PINECONE_INDEX_NAME"),
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)


def retrieval(state: RetrieverState):
    """
    Retrieve relevant documents for a query.

    Version-specific query (version is set):
        Filter to that version only. This keeps the search space small
        and precision is high.

    Cross-version query (version is None):
        If the version_extractor inferred a section_hint (e.g. "units" for a
        question about the Eagle Warrior), we filter to that section
        across all versions. This reduces the search space and gives the
        right entries a fair shot.

        If no section_hint was provided, we fall back to an unfiltered
        search but exclude the names section, which is pure lookup data
        and is never a useful result for balance questions.

    Args:
        query: cleaned query string from version_extractor
        version: BBG version string, or None for cross-version queries
        section_hint: optional section name to filter on (e.g. "units")

    Returns:
        list[Document]
    """

    print("retrieval called")

    pinecone_filter: dict[str, Any]
    k = 25

    if state["version"] is not None and state["current_section"] is not None:
        pinecone_filter = {
            "$and": [
                {"bbg_version": {"$eq": state["version"]}},
                {"section": {"$eq": state["current_section"]}},
            ]
        }
    elif state["version"] is not None:
        pinecone_filter = {"bbg_version": {"$eq": state["version"]}}
    elif state["current_section"] is not None:
        pinecone_filter = {"section": {"$eq": state["current_section"]}}
    else:
        pinecone_filter = {"section": {"$ne": "names"}}
        k = 40

    result = vector_store.similarity_search(state["query"], k=k, filter=pinecone_filter)

    # Fallback: if the filtered search returned nothing at all, retry
    # completely unfiltered so we never return an empty result when docs exist.
    if not result:
        result = vector_store.similarity_search(state["query"], k=25)

    return {"documents": result}


def supervise_retrieval(state: RetrieverState):
    if state["section_hints"] is None:
        return [
            Send(
                "retriever",
                {
                    "current_section": None,
                    "query": state["query"],
                    "version": state["version"],
                },
            )
        ]
    else:
        result = []
        for section in state["section_hints"]:
            result.append(
                Send(
                    "retriever",
                    {
                        "current_section": section,
                        "query": state["query"],
                        "version": state["version"],
                    },
                )
            )
        return result


retrieval_graph = StateGraph(RetrieverState)
retrieval_graph.add_node("retriever", retrieval)
retrieval_graph.add_conditional_edges(START, supervise_retrieval)
retrieval_graph.add_edge("retriever", END)
graph = retrieval_graph.compile()
