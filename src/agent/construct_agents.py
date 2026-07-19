import os
import threading

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver

from src.config import llm
from src.agent.tools import (
    search_buildings_and_improvements,
    search_general,
    search_leaders,
    search_great_people,
    search_techs_and_civics,
    search_units,
)
from src.logging_config import logger

tool_list = [
    search_buildings_and_improvements,
    search_general,
    search_leaders,
    search_techs_and_civics,
    search_units,
    search_great_people,
]

prompt = """
Always use the available search tools to find the answer to the query
and only use that information.
When the user specifies a version, pass it to the tools. When no version is
specified, omit it.
If asked when something was introduced or first appeared, search across
versions and identify the earliest bbg_version value in the results —
that is the introduction version.
If you cannot find a confident answer using the tools, say so. Do not
make up information or use information outside of the tools.
"""


def build_checkpointer():
    """Build the conversation checkpointer.

    Returns ``(checkpointer, pool)``. When ``DATABASE_URL`` is set we back the
    checkpointer with a psycopg ``ConnectionPool`` so concurrent requests each
    borrow their own connection; ``pool`` is handed back so a caller that owns
    the lifecycle (FastAPI's lifespan) can ``.close()`` it on shutdown. When no
    database is configured, or connecting fails, we fall back to an in-process
    ``MemorySaver`` and return ``pool=None``.
    """
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        logger.info("MemorySaver is ready")
        return MemorySaver(), None

    pool = None
    try:
        # min/max kept small on purpose: the deployed target is one request per
        # container (Lambda) and the demo is low-traffic, so a handful of
        # connections is plenty and stays well under Neon's free-tier ceiling.
        #
        # open=False + pool.open(wait=True, timeout=10) makes a bad/unreachable
        # DB fail fast (bounded ~10s) into the MemorySaver fallback below,
        # instead of the pool silently retrying in the background while setup()
        # blocks on the default 30s borrow timeout. 10s is generous enough for a
        # cold Neon free-tier compute to wake and accept the first connection;
        # connect_timeout bounds each individual libpq attempt.
        pool = ConnectionPool(
            db_uri,
            min_size=1,
            max_size=5,
            open=False,
            kwargs={
                "autocommit": True,
                "row_factory": dict_row,
                "connect_timeout": 10,
            },
        )
        pool.open(wait=True, timeout=10)
        # row_factory=dict_row is set at runtime via kwargs, so the static type
        # is ConnectionPool[Connection[TupleRow]]; PostgresSaver wants DictRow.
        # Correct at runtime, invisible to the checker (same as the prior code).
        checkpointer = PostgresSaver(pool)  # pyright: ignore[reportArgumentType]
        checkpointer.setup()
        logger.info("PostgresSaver is ready")
        return checkpointer, pool
    except Exception as e:
        logger.exception(
            f"{str(e)}. Error connecting to the Postgres db. Falling back to MemorySaver"
        )
        if pool is not None:
            pool.close()
        logger.info("MemorySaver is ready")
        return MemorySaver(), None


def build_agent(checkpointer):
    """Construct the retrieval agent bound to the given checkpointer."""
    return create_agent(
        model=llm, tools=tool_list, system_prompt=prompt, checkpointer=checkpointer
    )


_agent = None
_agent_lock = threading.Lock()


def get_agent():
    """Lazily build and cache a process-wide agent (Streamlit / eval / tests).

    Importing this module now has no side effects; the agent is built on first
    call and reused thereafter. The lock closes the first-call race: Streamlit
    runs each session in its own thread, so two concurrent first queries could
    otherwise both see ``_agent is None`` and each open a ConnectionPool,
    leaking the loser's pool. The FastAPI service deliberately does NOT use
    this — it builds its own agent inside the lifespan so it can own the pool's
    lifecycle and close it on shutdown.
    """
    global _agent
    with _agent_lock:
        if _agent is None:
            checkpointer, _ = build_checkpointer()
            _agent = build_agent(checkpointer)
    return _agent
