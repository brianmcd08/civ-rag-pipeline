from typing import cast

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.config import Version, llm
from src.schema import ParsedQuery


def query_parser(query: str, history: list) -> ParsedQuery:
    """
    1) Extract version from query by passing Version to LLM
    2) Clean query by passing to LLM
    Args:
        query (str): raw query

    Returns:
        ParsedQuery: clean query, and version
    """

    structured_llm = llm.with_structured_output(ParsedQuery)
    versions = Version.to_list_of_strings()
    latest_version = Version.get_latest_version()

    prompt = f"""
    Extract the following from the user input:

    1) VERSION
    Here are the valid versions:
    <Versions>
    {versions}
    </Versions>
    - Default to {latest_version} if the user doesn't specify a version.
    - "latest version", "most recent version", "current version" should be treated as {latest_version}.
    - If the query is asking WHICH versions something appears in, or spans
        all versions (e.g. "which versions is X in?", "has X changed across versions?",
        "when was X added?"), set version to null instead of defaulting to v74.

    2) CLEANED QUERY
    Fix typos and remove explicit version references (e.g. "in v74", "in version 6.5")
    AND cross-version phrasing (e.g. "which versions", "across versions", "when was X added").
    PRESERVE all semantic content — the subject, civilization name, unit/building/policy
    name, and the nature of the question. Do NOT reduce the query to a bare noun;
    keep enough context so a vector search can find the right documents.
    """

    cpt = ChatPromptTemplate.from_messages(
        [
            ("system", prompt),
            MessagesPlaceholder("history"),
            ("human", "{query}"),
        ]
    )

    chain = cpt | structured_llm
    response = chain.invoke({"query": query, "history": history})
    return cast(ParsedQuery, response)
