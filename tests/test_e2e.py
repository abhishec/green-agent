from __future__ import annotations
import sys
import uuid
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "green-agent"))


@pytest.mark.asyncio
async def test_health_green(green_app):
    """Green agent /health returns 200."""
    resp = await green_app.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_agent_card_green(green_app):
    """Green agent card returns valid JSON with skills list."""
    resp = await green_app.get("/.well-known/agent-card.json")
    assert resp.status_code == 200
    card = resp.json()
    assert "skills" in card
    assert len(card["skills"]) == 15


@pytest.mark.asyncio
async def test_mcp_tools_list(green_app):
    """GET /mcp/tools returns non-empty tool list."""
    resp = await green_app.get("/mcp/tools")
    assert resp.status_code == 200
    tools = resp.json()
    assert isinstance(tools, list)
    assert len(tools) > 0
    # All tools have required Anthropic fields
    for t in tools:
        assert "name" in t
        assert "description" in t
        assert "input_schema" in t


@pytest.mark.asyncio
async def test_task_01_tool_call(green_app, task_01_fixture, sample_session_id):
    """MCP get_order returns order data after seeding."""
    from src.mcp_server import seed_session_db

    # Seed the session
    await seed_session_db(sample_session_id, task_01_fixture)

    resp = await green_app.post("/mcp", json={
        "tool": "get_order",
        "params": {"order_id": "ORD-001"},
        "session_id": sample_session_id,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("id") == "ORD-001"


@pytest.mark.asyncio
async def test_task_01_get_items(green_app, task_01_fixture, sample_session_id):
    """get_order_items returns 4 items for ORD-001."""
    from src.mcp_server import seed_session_db
    await seed_session_db(sample_session_id, task_01_fixture)

    resp = await green_app.post("/mcp", json={
        "tool": "get_order_items",
        "params": {"order_id": "ORD-001"},
        "session_id": sample_session_id,
    })
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    assert len(items) == 4


@pytest.mark.asyncio
async def test_task_01_modify_atomic(green_app, task_01_fixture, sample_session_id):
    """modify_order_items is atomic — single call updates multiple items."""
    from src.mcp_server import seed_session_db, get_tool_calls
    await seed_session_db(sample_session_id, task_01_fixture)

    # First confirm
    await green_app.post("/mcp", json={
        "tool": "confirm_with_user",
        "params": {"message": "Confirm changes?"},
        "session_id": sample_session_id,
    })

    # Single atomic modify
    resp = await green_app.post("/mcp", json={
        "tool": "modify_order_items",
        "params": {
            "order_id": "ORD-001",
            "modifications": [
                {"item_id": "ITEM-001", "variant_id": "VAR-SHIRT-RED-M", "unit_price": 44.00},
                {"item_id": "ITEM-002", "variant_id": "VAR-JEANS-L", "unit_price": 67.00},
                {"item_id": "ITEM-003", "status": "cancelled"},
            ]
        },
        "session_id": sample_session_id,
    })
    assert resp.status_code == 200
    result = resp.json()
    assert result.get("success") is True

    # Verify modify_order_items was called exactly once
    calls = await get_tool_calls(sample_session_id)
    modify_calls = [c for c in calls if c["tool_name"] == "modify_order_items"]
    assert len(modify_calls) == 1


@pytest.mark.asyncio
async def test_scenario_registry_complete():
    """All 15 scenarios are registered and instantiable."""
    from src.scenarios import SCENARIO_REGISTRY
    assert len(SCENARIO_REGISTRY) == 15
    for task_id, ScenarioClass in SCENARIO_REGISTRY.items():
        scenario = ScenarioClass()
        assert scenario.task_id == task_id
        assert len(scenario.tools_available) > 0
        assert scenario.task_text != ""
        assert scenario.fixture_path != ""


@pytest.mark.asyncio
async def test_all_fixtures_valid():
    """All 15 fixture JSON files exist and are non-empty."""
    import json
    from src.scenarios import SCENARIO_REGISTRY
    fixtures_dir = Path(__file__).parent.parent / "green-agent" / "src" / "fixtures"
    for task_id, ScenarioClass in SCENARIO_REGISTRY.items():
        scenario = ScenarioClass()
        path = fixtures_dir / scenario.fixture_path
        assert path.exists(), f"Missing fixture: {scenario.fixture_path}"
        data = json.loads(path.read_text())
        assert isinstance(data, dict), f"Fixture {scenario.fixture_path} is not a dict"
        assert len(data) > 0, f"Fixture {scenario.fixture_path} is empty"
