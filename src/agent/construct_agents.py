import os
import threading

from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.agent.tools import (
    search_buildings_and_improvements,
    search_general,
    search_great_people,
    search_leaders,
    search_techs_and_civics,
    search_units,
)
from src.config import llm
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
    """Build the conversation checkpointer. Postgres or nothing.

    Returns ``(checkpointer, pool)``, backed by a psycopg ``ConnectionPool`` so
    concurrent requests each borrow their own connection; ``pool`` is handed
    back so a caller that owns the lifecycle (FastAPI's lifespan) can
    ``.close()`` it on shutdown.

    There is deliberately NO in-memory fallback. The old code dropped to a
    ``MemorySaver`` when ``DATABASE_URL`` was unset or the connection failed,
    which meant a dead database presented as a healthy app that had silently
    stopped persisting anything: conversations vanished between requests and
    the only signal was a log line nobody was reading. Failing to start is the
    correct behavior for a service whose whole job is durable conversation
    state. Callers that genuinely do not need persistence (tests, the eval
    runner) pass ``checkpointer=None`` to ``build_agent`` instead of relying on
    a fallback here.
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
        # min/max kept small on purpose: the deployed target is one request per
        # container (Lambda) and the demo is low-traffic, so a handful of
        # connections is plenty and stays well under Neon's free-tier ceiling.
        #
        # open=False + pool.open(wait=True, timeout=10) makes a bad/unreachable
        # DB fail fast (bounded ~10s) and raise, instead of the pool retrying in
        # the background while setup() blocks on the default 30s borrow timeout.
        # (This used to fall through to a MemorySaver; it now propagates.)
        # 10s is generous enough for a
        # cold Neon free-tier compute to wake and accept the first connection;
        # connect_timeout bounds each individual libpq attempt.
        # check= validates a pooled connection before handing it out. Without
        # it the pool returns whatever it parked, and the CALLER eats the error
        # on a dead connection; the pool only logs "discarding closed
        # connection" afterward, so the next query succeeds and the failure
        # looks intermittent. Neon's free tier autosuspends its compute after
        # ~5 minutes idle, which kills exactly the connection min_size=1 keeps
        # parked, so any gap between queries reproduces this. Observed in prod
        # 2026-07-29: a clean query at 16:42 UTC, ~20 minutes idle, then a
        # psycopg [BAD] connection surfaced to the user on the next one.
        # Cost of the check is one round trip on borrow; a dead connection is
        # discarded and replaced transparently instead of raising.
        #
        # NOTE: max_idle would NOT help here. It only reaps connections ABOVE
        # min_size, and the parked connection at min_size=1 is the one Neon
        # kills.
        pool = ConnectionPool(
            db_uri,
            min_size=1,
            max_size=5,
            open=False,
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
    return create_agent(
        model=llm, tools=tool_list, system_prompt=prompt, checkpointer=checkpointer
    )


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
