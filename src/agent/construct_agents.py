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
You are an expert in Civilization 6 BBG (Better Balance Game mod).
Always use the available search tools to find information before answering.
Do not use your own knowledge about Civilization.
When the user specifies a version, pass it to the tools. When no version is
specified, omit it.
If asked when something was introduced or first appeared, search across
versions and identify the earliest bbg_version value in the results —
that is the introduction version.
If you cannot find a confident answer using the tools, say so. Do not
make up information or use information outside of the tools.
When generating your answer, use ONLY information returned by the tools.
Do not supplement with your own knowledge even if the tool results seem incomplete.
"""

agent = create_agent(
    model=llm, tools=tool_list, system_prompt=prompt, checkpointer=checkpointer
)
