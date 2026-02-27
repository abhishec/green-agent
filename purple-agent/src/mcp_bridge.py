from __future__ import annotations
import httpx
from src.config import TOOL_TIMEOUT


async def discover_tools(tools_endpoint: str) -> list[dict]:
    """GET {tools_endpoint}/mcp/tools — returns Anthropic-format tool list."""
    async with httpx.AsyncClient(timeout=TOOL_TIMEOUT) as client:
        resp = await client.get(f"{tools_endpoint}/mcp/tools")
        resp.raise_for_status()
        return resp.json()


async def call_tool(
    tools_endpoint: str,
    tool_name: str,
    params: dict,
    session_id: str,
) -> dict:
    """POST {tools_endpoint}/mcp — calls a tool and returns result."""
    async with httpx.AsyncClient(timeout=TOOL_TIMEOUT) as client:
        resp = await client.post(
            f"{tools_endpoint}/mcp",
            json={"tool": tool_name, "params": params, "session_id": session_id},
        )
        resp.raise_for_status()
        return resp.json()
