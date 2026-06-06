import os
from typing import cast

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.config import ANTHROPIC_MODEL, Section, Version
from src.schema import ParsedQuery, RoutingDecision
from src.secrets import get_secret

os.environ["ANTHROPIC_API_KEY"] = get_secret("ANTHROPIC_API_KEY")


def query_parser(query: str, history: list) -> ParsedQuery:
    """
    1) Extract version from query by passing Version to LLM
    2) Clean query by passing to LLM
    Args:
        query (str): raw query

    Returns:
        ParsedQuery: clean query, and version
    """

    llm = ChatAnthropic(model_name=ANTHROPIC_MODEL, stop=[], timeout=30)
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


def section_router(cleaned_query: str) -> RoutingDecision:
    """
    Infer a section_hint when the query clearly targets one section
    """

    llm = ChatAnthropic(model_name=ANTHROPIC_MODEL, stop=[], timeout=30)
    structured_llm = llm.with_structured_output(RoutingDecision)
    sections = "\n".join([s.value for s in Section])

    prompt = f"""
    Extract the following from the user input:

    1) SECTION HINT
    If the query clearly targets one or more sections, set section_hint to a list
    of matching section values. If the query is too broad to target any sections, 
    set it to null.
    
    Here are the valid section values:
    <Sections>
    {sections}
    </Sections>
    
    Examples:
    - "which versions have the Eagle Warrior?" → section_hint: ["units"]
    - "what does the Monument building do?" → section_hint: ["buildings"]
    - "tell me about Montezuma" → section_hint: ["leaders"]
    - "what changed for units in 7.4?" → section_hint: ["changelog"]
    - "what are the best policy cards?" → section_hint: ["policies"]
    - "what are the general game mechanic changes?" → section_hint: null
        (too broad, could span misc/changelog/etc.)
    - "tell me about the Aztec civilization" → section_hint: null
        (spans leaders, units, buildings, etc.)
    - "which wonders give diplomatic victory points?" → section_hint: ["world_wonder"]
    - "what are the best wonders to build?" → section_hint: ["world_wonder"]
    - "which natural wonders give faith?" → section_hint: ["natural_wonder"]
    - "what is the Migration Treaty?" → section_hint: ["congress"]
    - "which version introduced the expanded leader set?" → section_hint: ["bbg_expanded"]
    - "was Spearthrower Owl introduced in bbg expanded?" → section_hint: ["bbg_expanded"]
    - "what is the X unique unit?" → section_hint: ["units"]
    - "what is the [unit name]?" → section_hint: ["units"]
    - "which civilization has the ice hockey rink?" → section_hint: ["improvements", "leaders"]
    """

    cpt = ChatPromptTemplate.from_messages(
        [
            ("system", prompt),
            ("human", "{query}"),
        ]
    )

    chain = cpt | structured_llm
    response = chain.invoke({"query": cleaned_query})
    return cast(RoutingDecision, response)


def run_extraction_pipeline(
    query: str, history: list
) -> tuple[ParsedQuery, RoutingDecision]:
    parsed_query = query_parser(query, history)  # history passed here
    routing_decision = section_router(parsed_query.cleaned_query)  # not here
    return parsed_query, routing_decision
