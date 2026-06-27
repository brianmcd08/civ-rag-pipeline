import os
import psycopg
from psycopg.rows import dict_row
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

db_uri = os.getenv("DATABASE_URL")
if db_uri:
    conn = psycopg.connect(db_uri, autocommit=True, row_factory=dict_row)  # pyright: ignore[reportArgumentType]
    checkpointer = PostgresSaver(conn)  # pyright: ignore[reportArgumentType]
    checkpointer.setup()
else:
    checkpointer = MemorySaver()

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

agent = create_agent(
    model=llm, tools=tool_list, system_prompt=prompt, checkpointer=checkpointer
)
