from langchain_core.runnables import RunnableConfig
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphRecursionError

from src.retrieval import version_extractor as ve
from src.config import RECURSION_LIMIT
from src.agent.construct_agents import agent

NO_ANSWER_MESSAGE = (
    "I wasn't able to find a confident answer to that — try rephrasing or "
    "narrowing your question."
)


def generate_response(query: str, history: list, thread_id: str) -> tuple[str, list[str]]:
    parsed_query = ve.query_parser(query, history)
    message = parsed_query.cleaned_query

    if parsed_query.version:
        message += f"\n\nVersion: {parsed_query.version}"

    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
    }
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": message}]}, config=config
        )
    except GraphRecursionError:
        return NO_ANSWER_MESSAGE, []

    response = result["messages"][-1].content
    documents = [m.content for m in result["messages"] if isinstance(m, ToolMessage)]

    return response, documents
