import os
import threading

from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.agent.tools import tool_list
from src.config import llm
from src.logging_config import logger

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
    """Build the conversation checkpointer. Postgres or nothing.

    Returns ``(checkpointer, pool)``, backed by a psycopg ``ConnectionPool`` so
    concurrent requests each borrow their own connection; ``pool`` is handed
    back so a caller that owns the lifecycle (FastAPI's lifespan) can
    ``.close()`` it on shutdown.

    There is deliberately NO in-memory fallback: failing to start is the
    correct behavior for a service whose whole job is durable conversation
    state. Callers that genuinely do not need persistence (tests, the eval
    runner) pass ``checkpointer=None`` to ``build_agent``.
    """
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        raise RuntimeError(
            "DATABASE_URL is not set. The agent requires a Postgres "
            "checkpointer. Set DATABASE_URL, or call build_agent(None) if you "
            "genuinely want a stateless agent (tests and the eval runner do)."
        )

    pool = None
    try:
        # Every argument here is load-bearing; the reasoning is in docs/architecture.md
        # ("One construction path on every surface" and the borrow-timeout entry under
        # "What measurement caught"). Short version: min_size=0 keeps Neon's autosuspend
        # working, timeout=10 restores the fail-fast that min_size=0 removed, and check=
        # validates on borrow because a thawed container can hold a dead connection.
        pool = ConnectionPool(
            db_uri,
            min_size=0,
            max_size=5,
            open=False,
            timeout=10,
            check=ConnectionPool.check_connection,
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
        logger.exception(f"{str(e)}. Error connecting to the Postgres db.")
        if pool is not None:
            pool.close()
        # Re-raise rather than degrade. See the docstring: a silent fallback
        # here is what let a dead database look like a working app.
        raise


def build_agent(checkpointer):
    """Construct the retrieval agent bound to the given checkpointer."""
    return create_agent(model=llm, tools=tool_list, system_prompt=prompt, checkpointer=checkpointer)


_agent = None
_pool = None
_agent_lock = threading.Lock()


def get_agent():
    """Lazily build and cache a process-wide agent.

    Importing this module has no side effects; the agent is built on first call
    and reused thereafter. The lock closes the first-call race: two concurrent
    first queries could otherwise both see ``_agent is None`` and each open a
    ConnectionPool, leaking the loser's pool.

    The pool is kept in a module global rather than discarded, so
    ``close_agent()`` can release it on shutdown. Previously it was dropped on
    the floor here, which meant the only way to free those connections was to
    end the process.
    """
    global _agent, _pool
    with _agent_lock:
        if _agent is None:
            checkpointer, pool = build_checkpointer()
            _agent = build_agent(checkpointer)
            _pool = pool
    return _agent


def close_agent():
    """Release the process-wide agent's connection pool.

    Only meaningful for long-lived local processes (a Ctrl-C'd uvicorn). Lambda
    never runs it: the execution environment is destroyed wholesale.
    """
    global _agent, _pool
    with _agent_lock:
        if _pool is not None:
            _pool.close()
        _pool = None
        _agent = None
