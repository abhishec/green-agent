from __future__ import annotations
import sys
from pathlib import Path

# Swap 'src' namespace to purple-agent for this module.
# Both agents use 'src/' as their top-level package; we must clear the green-agent
# cache before importing purple modules, then restore afterwards.
_PURPLE = str(Path(__file__).parent.parent / "purple-agent")
_GREEN = str(Path(__file__).parent.parent / "green-agent")

def _activate_purple():
    for k in [k for k in sys.modules if k == "src" or k.startswith("src.")]:
        del sys.modules[k]
    if _PURPLE not in sys.path:
        sys.path.insert(0, _PURPLE)
    if _GREEN in sys.path:
        sys.path.remove(_GREEN)

def _activate_green():
    for k in [k for k in sys.modules if k == "src" or k.startswith("src.")]:
        del sys.modules[k]
    if _GREEN not in sys.path:
        sys.path.insert(0, _GREEN)
    if _PURPLE in sys.path:
        sys.path.remove(_PURPLE)

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_mcp_bridge_discover(httpx_mock):
    """discover_tools returns list of tool descriptors."""
    _activate_purple()
    from src.mcp_bridge import discover_tools
    httpx_mock.add_response(
        url="http://localhost:9009/mcp/tools",
        json=[{"name": "get_order", "description": "Get order", "input_schema": {"type": "object", "properties": {}}}]
    )
    tools = await discover_tools("http://localhost:9009")
    assert isinstance(tools, list)
    assert tools[0]["name"] == "get_order"


@pytest.mark.asyncio
async def test_mcp_bridge_call(httpx_mock):
    """call_tool posts to /mcp and returns result dict."""
    _activate_purple()
    from src.mcp_bridge import call_tool
    httpx_mock.add_response(
        url="http://localhost:9009/mcp",
        json={"id": "ORD-001", "status": "pending", "total": 137.00}
    )
    result = await call_tool("http://localhost:9009", "get_order", {"order_id": "ORD-001"}, "sess-1")
    assert result["id"] == "ORD-001"


@pytest.mark.asyncio
async def test_fallback_solver_tool_loop():
    """fallback_solver terminates tool-use loop and returns text answer."""
    _activate_purple()
    from src.fallback_solver import solve_with_claude

    call_count = 0

    async def mock_tool_call(tool_name: str, params: dict) -> dict:
        nonlocal call_count
        call_count += 1
        return {"result": "ok", "tool": tool_name}

    tools = [{"name": "get_order", "description": "Get order", "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}}]

    # Mock the anthropic client
    mock_response_tool = MagicMock()
    mock_response_tool.stop_reason = "tool_use"
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.id = "tu_1"
    mock_tool_block.name = "get_order"
    mock_tool_block.input = {"order_id": "ORD-001"}
    mock_response_tool.content = [mock_tool_block]

    mock_response_end = MagicMock()
    mock_response_end.stop_reason = "end_turn"
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "Order ORD-001 processed successfully."
    mock_response_end.content = [mock_text_block]

    with patch("src.fallback_solver.anthropic.AsyncAnthropic") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.messages.create = AsyncMock(side_effect=[mock_response_tool, mock_response_end])

        result = await solve_with_claude(
            task_text="Get order ORD-001",
            policy_doc="Standard policy",
            tools=tools,
            on_tool_call=mock_tool_call,
            session_id="sess-test",
        )

    assert "ORD-001" in result or result != ""
    assert call_count == 1


@pytest.mark.asyncio
async def test_executor_fallback():
    """executor falls back to Claude when BrainOS raises BrainOSUnavailableError."""
    _activate_purple()
    from src.executor import handle_task
    from src.brainos_client import BrainOSUnavailableError

    with patch("src.executor.run_task", side_effect=BrainOSUnavailableError("unavailable")):
        with patch("src.executor.discover_tools", return_value=[]):
            with patch("src.executor.solve_with_claude", return_value="Fallback answer") as mock_fallback:
                result = await handle_task(
                    task_text="Test task",
                    policy_doc="Test policy",
                    tools_endpoint="http://localhost:9009",
                    task_id="task_01",
                    session_id="sess-test",
                )
    assert result == "Fallback answer"
    mock_fallback.assert_called_once()
    _activate_green()  # restore green-agent src for any subsequent tests
