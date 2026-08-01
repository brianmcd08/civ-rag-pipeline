"""Shared test fixtures.

Two jobs, both about keeping the suite off any real database.
"""

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _no_database_url():
    """Guarantee the suite never touches a real Postgres.

    ``src/secrets.py`` calls ``load_dotenv()`` at import, so a developer's local
    ``.env`` silently populates ``DATABASE_URL`` for the whole process. Before
    the checkpointer was made Postgres-only that was merely wasteful; now that
    ``build_checkpointer()`` raises without a database, an inherited
    ``DATABASE_URL`` would point the suite at whatever that file names, which
    on this machine has at times been production Neon.

    Popping it is also what makes the stateless-agent fixture below the only
    construction path the tests can take.
    """
    os.environ.pop("DATABASE_URL", None)
    yield


@pytest.fixture
def stateless_agent():
    """An agent with no checkpointer at all.

    The integration tests are single-turn and pass ``history=[]``, so
    conversation persistence is not under test and a database would be pure
    overhead. ``checkpointer=None`` is LangGraph's documented "no persistence"
    default.
    """
    from src.agent.construct_agents import build_agent

    return build_agent(None)
