import asyncio
from unittest.mock import patch

from langchain_core.documents import Document
from mcp_types import CallToolResult, TextContent

from src.agent.tools import tool_list
from src.mcp_server import mcp


def test_registers_all_six_tools():
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == {t.name for t in tool_list}


def test_descriptions_match_tools_py():
    tools = asyncio.run(mcp.list_tools())
    registered = {t.name: t.description for t in tools}
    expected = {t.name: t.description for t in tool_list}
    assert registered == expected


def test_call_tool_reaches_hybrid_query_without_live_network():
    """First mock of hybrid_query in this repo (no existing test patches it).
    Patches src.agent.tools.hybrid_query, not src.retrieval.retriever's copy,
    since tools.py imports it by name at module load -- patching the retriever
    module's attribute after that import has already happened would not
    affect the reference tools.py actually calls."""
    fake_docs = [Document(page_content="Warrior stats", metadata={"section": "units"})]
    with patch("src.agent.tools.hybrid_query", return_value=fake_docs) as mock_query:
        result = asyncio.run(mcp.call_tool("search_units", {"query": "warrior"}))
    mock_query.assert_called_once()

    assert isinstance(result, CallToolResult)
    first_block = result.content[0]
    assert isinstance(first_block, TextContent)
    assert "Warrior stats" in first_block.text
