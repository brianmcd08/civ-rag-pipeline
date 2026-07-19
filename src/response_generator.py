from langchain_core.runnables import RunnableConfig
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphRecursionError

from src.retrieval import version_extractor as ve
from src.config import HISTORY_LIMIT, RECURSION_LIMIT

NO_ANSWER_MESSAGE = (
    "I wasn't able to find a confident answer to that — try rephrasing or "
    "narrowing your question."
)


def generate_response(
    query: str, history: list, thread_id: str, agent=None
) -> tuple[str, list[str]]:
    if agent is None:
        # Streamlit / eval / tests path: reuse the lazily-built process-wide
        # agent. The FastAPI service passes its own lifespan-built agent.
        from src.agent.construct_agents import get_agent

        agent = get_agent()

    # Enforce the memory window here so every client (Streamlit, API, eval)
    # inherits it; app.py's own slice is then a harmless no-op. Without this,
    # an API caller could send unbounded history straight into the parser
    # prompt.
    history = history[-HISTORY_LIMIT:]

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

    response = result["messages"][-1].text
    documents: list[str] = [
        m.text for m in result["messages"] if isinstance(m, ToolMessage)
    ]

    return response, documents
