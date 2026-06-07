from langchain_core.runnables import RunnableConfig

from src.retrieval import version_extractor as ve
from src.config import RECURSION_LIMIT
from src.agent.construct_agents import agent


def generate_response(query: str, history: list, thread_id: str) -> str:
    parsed_query = ve.query_parser(query, history)
    message = parsed_query.cleaned_query

    if parsed_query.version:
        message += f"\n\nVersion: {parsed_query.version}"

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
    }
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]}, config=config
    )
    response = result["messages"][-1].content

    return response
