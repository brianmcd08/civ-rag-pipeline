# Given a clean query string and an optional version string (parsed from the chain),
# return relevant Documents. This file knows nothing about LLMs or intent parsing.

import os
from typing import Any

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

from src.config import Section, Version
from src.secrets import get_secret

os.environ["OPENAI_API_KEY"] = get_secret("OPENAI_API_KEY")
os.environ["PINECONE_API_KEY"] = get_secret("PINECONE_API_KEY")


class Retriever:
    def __init__(self) -> None:
        self.vector_store = PineconeVectorStore(
            index_name=get_secret("PINECONE_INDEX_NAME"),
            embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
        )

    def retrieve(
        self,
        query: str,
        version: str | None = Version.get_latest_version(),
        section_hint: Section | None = None,
    ) -> list[Document]:
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

        pinecone_filter: dict[str, Any]
        k = 25

        if version is not None and section_hint is not None:
            pinecone_filter = {
                "$and": [
                    {"bbg_version": {"$in": [version]}},
                    {"section": {"$eq": section_hint}},
                ]
            }
        elif version is not None:
            pinecone_filter = {"bbg_version": {"$in": [version]}}
        elif section_hint is not None:
            pinecone_filter = {"section": {"$eq": section_hint}}
        else:
            pinecone_filter = {"section": {"$ne": "names"}}
            k = 40

        result = self.vector_store.similarity_search(query, k=k, filter=pinecone_filter)

        # Fallback: if the filtered search returned nothing at all, retry
        # completely unfiltered so we never return an empty result when docs exist.
        if not result:
            result = self.vector_store.similarity_search(query, k=25)

        return result


vectorstore_connection = Retriever()
