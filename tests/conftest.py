from __future__ import annotations
import asyncio
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

GREEN_AGENT_PATH = str(Path(__file__).parent.parent / "green-agent")
PURPLE_AGENT_PATH = str(Path(__file__).parent.parent / "purple-agent")

# Only green-agent in global path; test_purple.py swaps this for its own tests
sys.path.insert(0, GREEN_AGENT_PATH)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_session_id():
    return str(uuid.uuid4())


@pytest.fixture
def task_01_fixture():
    import json
    fixture_path = Path(__file__).parent.parent / "green-agent" / "src" / "fixtures" / "task_01_fixture.json"
    return json.loads(fixture_path.read_text())


@pytest_asyncio.fixture
async def green_app():
    from httpx import AsyncClient, ASGITransport
    from src.server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def purple_app():
    from httpx import AsyncClient, ASGITransport
    from src.server import app as purple_server
    async with AsyncClient(transport=ASGITransport(app=purple_server), base_url="http://test") as client:
        yield client
