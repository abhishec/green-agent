"""
Green Agent — FastAPI server.
Exposes: GET /.well-known/agent-card.json, POST / (A2A), POST /mcp, GET /mcp/tools, GET /health
"""
from __future__ import annotations
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.mcp_server import call_tool, get_tools_for_session
from src.scenarios import SCENARIO_REGISTRY

app = FastAPI(title="GreenBenchmark Agent", version="1.0.0")


# ── Agent Card ──────────────────────────────────────────────────────────────
AGENT_CARD = {
    "name": "GreenBenchmark Agent",
    "description": "Benchmark orchestrator that issues tasks to AI agents and scores their responses across 15 business scenarios.",
    "version": "1.0.0",
    "url": "http://localhost:9009",
    "capabilities": {"streaming": False, "tools": True},
    "skills": [
        {"id": task_id, "name": task_id.replace("_", " ").title()}
        for task_id in SCENARIO_REGISTRY
    ],
}


@app.get("/.well-known/agent-card.json")
async def agent_card():
    return JSONResponse(AGENT_CARD)


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "green-benchmark", "scenarios": len(SCENARIO_REGISTRY)}


# ── MCP Tool Server ─────────────────────────────────────────────────────────
class MCPRequest(BaseModel):
    tool: str
    params: dict[str, Any] = {}
    session_id: str = ""


@app.post("/mcp")
async def mcp_call(req: MCPRequest):
    session_id = req.session_id or str(uuid.uuid4())
    result = await call_tool(req.tool, req.params, session_id)
    return result


@app.get("/mcp/tools")
async def mcp_tools(session_id: str = ""):
    return get_tools_for_session(session_id or "")


# ── A2A Receiver ─────────────────────────────────────────────────────────────
@app.post("/")
async def a2a_handler(request: Request):
    body = await request.json()

    if body.get("method") != "tasks/send":
        raise HTTPException(400, "Only tasks/send method is supported")

    params = body.get("params", {})
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    metadata = params.get("metadata", {})
    session_id = metadata.get("session_id", task_id)

    task_text = ""
    for part in message.get("parts", []):
        task_text += part.get("text", "")

    # For the green agent receiving A2A from bench-runner:
    # the green agent IS the assessor — it runs the task against the purple agent
    # and returns the score. But when the purple agent calls back to green's /mcp,
    # that's handled by the /mcp endpoint above.
    # Here we just acknowledge receipt.
    return {
        "jsonrpc": "2.0",
        "result": {
            "id": task_id,
            "status": {"state": "completed"},
            "artifacts": [
                {
                    "parts": [
                        {
                            "text": f"Task {task_id} received. Use /mcp endpoint to access tools. Session: {session_id}"
                        }
                    ]
                }
            ],
        },
    }
