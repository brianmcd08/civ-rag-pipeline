"""MCP server wrapping the 6 retrieval tools for local MCP clients.

Phase B, Phase 1. Registers each tool in `src.agent.tools.tool_list` directly
by function, name, and description, rather than hand-writing wrapper
functions: the schema an MCP client sees stays in sync with `tools.py`
automatically, with nothing to duplicate or drift.

Local/stdio only for this phase — no HTTP/SSE transport, no Docker/Lambda
packaging. An MCP client launches this as a subprocess and talks to it over
stdin/stdout.
"""

from langchain_core.tools import StructuredTool
from mcp.server.mcpserver import MCPServer

from src.agent.tools import tool_list
from src.config import MCP_SERVER_NAME

mcp = MCPServer(MCP_SERVER_NAME)

for t in tool_list:
    # tool_list is typed as list[BaseTool]; .func only exists on StructuredTool,
    # which is what the @tool decorator always produces for a plain function
    # (all 6 tools). Narrow explicitly rather than relying on the runtime type.
    if not isinstance(t, StructuredTool) or t.func is None:
        raise TypeError(f"{t.name} is not a StructuredTool with a plain .func; MCP needs one")
    mcp.add_tool(t.func, name=t.name, description=t.description)

if __name__ == "__main__":
    mcp.run(transport="stdio")
