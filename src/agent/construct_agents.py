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
        # min_size=0 is deliberate and is what makes construction reuse safe on
        # Lambda. Now that the agent is built once per CONTAINER rather than per
        # invocation, a warm container sits idle between requests holding
        # whatever the pool parked. At min_size=1 that parked connection would
        # keep Neon's compute awake (or, worse, be the exact connection Neon
        # kills on autosuspend). At 0 the pool parks nothing, autosuspend works
        # normally, and connections are opened on demand. This was the one
        # objection that previously argued against reusing construction at all;
        # min_size=0 removes it. max_size stays small: one request per container
        # on Lambda, low-traffic demo, well under Neon's free-tier ceiling.
        #
        # open=False + pool.open(wait=True, timeout=10) USED to be the fail-fast
        # on a bad/unreachable DB. min_size=0 breaks that: open(wait=True)
        # returns immediately because there is nothing to pre-open, so the 10s
        # bound never applies and the first real need for a connection is
        # PostgresSaver.setup() below.
        #
        # timeout=10 is what restores the bound, and it is not optional here.
        # It sets the pool's default borrow timeout; without it getconn falls
        # back to psycopg_pool's 30s default. Measured 2026-08-01 against a
        # refused DATABASE_URL: "couldn't get a connection after 30.00 sec".
        # That is a real regression on Lambda, where API Gateway's integration
        # timeout is a hard 30s — a bad URL would race the gateway and surface
        # as an ambiguous 504 instead of a diagnosable 500. At 10s the error
        # comes back with room to spare and setup() is what raises it, through
        # the same except branch as before. connect_timeout still bounds each
        # individual libpq attempt underneath.
        #
        # check= validates a pooled connection before handing it out. Without
        # it the pool returns whatever it parked, and the CALLER eats the error
        # on a dead connection; the pool only logs "discarding closed
        # connection" afterward, so the next query succeeds and the failure
        # looks intermittent. Observed in prod 2026-07-29: a clean query at
        # 16:42 UTC, ~20 minutes idle, then a psycopg [BAD] connection surfaced
        # to the user on the next one. This matters MORE under construction
        # reuse, not less: a container can be frozen and thawed arbitrarily long
        # between invocations, so a connection opened on one request can be dead
        # by the next even with nothing parked at idle. Cost is one round trip
        # on borrow; a dead connection is discarded and replaced transparently.
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
