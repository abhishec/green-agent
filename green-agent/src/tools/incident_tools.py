from __future__ import annotations

import aiosqlite
from typing import Any

# Mock log entries for incident diagnosis
_LOG_TEMPLATES: list[dict[str, Any]] = [
    {"level": "ERROR", "service": "api-gateway", "message": "Connection pool exhausted", "code": "CONN_POOL_FULL"},
    {"level": "ERROR", "service": "auth-service", "message": "JWT verification failed: signature mismatch", "code": "AUTH_FAIL"},
    {"level": "WARN",  "service": "database", "message": "Query timeout after 30s", "code": "DB_TIMEOUT"},
    {"level": "ERROR", "service": "payment-service", "message": "Downstream payment gateway returned 503", "code": "GW_UNAVAILABLE"},
    {"level": "ERROR", "service": "worker", "message": "Unhandled exception in job processor", "code": "WORKER_CRASH"},
    {"level": "INFO",  "service": "deploy", "message": "Deployment d-abc123 completed successfully", "code": "DEPLOY_OK"},
    {"level": "WARN",  "service": "cdn", "message": "Cache miss rate exceeds 80%", "code": "CDN_MISS"},
    {"level": "ERROR", "service": "search", "message": "Elasticsearch cluster health: red", "code": "ES_RED"},
]

TOOL_DESCRIPTORS = [
    {
        "name": "get_incident",
        "description": "Retrieve an incident by ID",
        "input_schema": {
            "type": "object",
            "properties": {"incident_id": {"type": "string", "description": "The incident ID"}},
            "required": ["incident_id"],
        },
    },
    {
        "name": "get_deployments",
        "description": "Get recent deployments, optionally filtered by service or time window",
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name to filter by"},
                "hours_back": {"type": "integer", "description": "How many hours back to look (default 24)"},
                "limit": {"type": "integer", "description": "Maximum records to return"},
            },
            "required": [],
        },
    },
    {
        "name": "get_logs",
        "description": "Retrieve log entries for an incident or service",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string", "description": "Incident ID to get logs for"},
                "service": {"type": "string", "description": "Service name to filter logs"},
                "level": {"type": "string", "description": "Log level filter: ERROR/WARN/INFO"},
                "limit": {"type": "integer", "description": "Maximum log entries to return (default 20)"},
            },
            "required": [],
        },
    },
    {
        "name": "create_rca",
        "description": "Create a Root Cause Analysis document for an incident",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string", "description": "The incident ID"},
                "root_cause": {"type": "string", "description": "Root cause description"},
                "timeline": {"type": "array", "items": {"type": "object"}, "description": "Incident timeline events"},
                "action_items": {"type": "array", "items": {"type": "string"}, "description": "Follow-up action items"},
                "author": {"type": "string", "description": "Author of the RCA"},
            },
            "required": ["incident_id", "root_cause"],
        },
    },
    {
        "name": "submit_change_request",
        "description": "Submit a change request record to prevent future incidents",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string", "description": "Related incident ID"},
                "change_type": {"type": "string", "description": "Type: 'config', 'code', 'infrastructure', 'process'"},
                "description": {"type": "string", "description": "Description of the proposed change"},
                "risk_level": {"type": "string", "description": "Risk level: low/medium/high"},
                "proposed_date": {"type": "string", "description": "Proposed implementation date (YYYY-MM-DD)"},
            },
            "required": ["incident_id", "change_type", "description"],
        },
    },
    {
        "name": "post_status",
        "description": "Update the public status page for an incident",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string", "description": "The incident ID"},
                "status": {"type": "string", "description": "Status: 'investigating', 'identified', 'monitoring', 'resolved'"},
                "message": {"type": "string", "description": "Public status message"},
                "affected_services": {"type": "array", "items": {"type": "string"}, "description": "Affected service names"},
            },
            "required": ["incident_id", "status", "message"],
        },
    },
]


async def get_incident(incident_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM incidents WHERE id = ?", [incident_id]) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Incident {incident_id} not found"}
    return dict(row)


async def get_deployments(
    db_path: str,
    session_id: str,
    service: str = "",
    hours_back: int = 24,
    limit: int = 20,
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            query = f"""
                SELECT * FROM deployments
                WHERE deployed_at >= datetime('now', '-{int(hours_back)} hours')
            """
            args: list[Any] = []
            if service:
                query += " AND service = ?"
                args.append(service)
            query += f" ORDER BY deployed_at DESC LIMIT {max(1, min(int(limit), 100))}"
            async with db.execute(query, args) as cur:
                rows = await cur.fetchall()
            return {"deployments": [dict(r) for r in rows], "count": len(rows)}
        except Exception:
            pass
    # Mock deployments
    mock = [
        {"id": "d-abc123", "service": "api-gateway", "version": "v2.4.1", "deployed_at": "2026-02-27T10:00:00Z", "status": "success", "deployed_by": "ci/cd"},
        {"id": "d-def456", "service": "auth-service", "version": "v1.8.3", "deployed_at": "2026-02-27T08:30:00Z", "status": "success", "deployed_by": "ci/cd"},
        {"id": "d-ghi789", "service": "payment-service", "version": "v3.1.0", "deployed_at": "2026-02-26T22:00:00Z", "status": "success", "deployed_by": "ci/cd"},
    ]
    if service:
        mock = [d for d in mock if d["service"] == service]
    return {"deployments": mock[:limit], "count": len(mock), "source": "fixture"}


async def get_logs(
    db_path: str,
    session_id: str,
    incident_id: str = "",
    service: str = "",
    level: str = "",
    limit: int = 20,
    **kwargs,
) -> dict:
    logs = list(_LOG_TEMPLATES)
    if service:
        logs = [l for l in logs if l.get("service") == service]
    if level:
        logs = [l for l in logs if l.get("level") == level.upper()]
    logs = logs[:max(1, min(int(limit), 100))]
    # Add timestamps
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    for i, log in enumerate(logs):
        log["timestamp"] = (now - timedelta(minutes=i * 3)).isoformat()
        if incident_id:
            log["incident_id"] = incident_id
    return {"logs": logs, "count": len(logs)}


async def create_rca(
    incident_id: str,
    root_cause: str,
    db_path: str,
    session_id: str,
    timeline: list[dict[str, Any]] | None = None,
    action_items: list[str] | None = None,
    author: str = "",
    **kwargs,
) -> dict:
    import uuid as _uuid
    rca_id = f"RCA-{_uuid.uuid4().hex[:8].upper()}"
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                """
                INSERT INTO rca_documents (id, incident_id, root_cause, author, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                [rca_id, incident_id, root_cause, author],
            )
            await db.execute(
                "UPDATE incidents SET rca_id = ?, status = 'post_incident_review' WHERE id = ?",
                [rca_id, incident_id],
            )
            await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "rca_id": rca_id,
        "incident_id": incident_id,
        "root_cause": root_cause,
        "timeline": timeline or [],
        "action_items": action_items or [],
        "author": author,
        "status": "created",
        "url": f"https://wiki.example.com/rca/{rca_id}",
    }


async def submit_change_request(
    incident_id: str,
    change_type: str,
    description: str,
    db_path: str,
    session_id: str,
    risk_level: str = "medium",
    proposed_date: str = "",
    **kwargs,
) -> dict:
    import uuid as _uuid
    cr_id = f"CR-{_uuid.uuid4().hex[:8].upper()}"
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                """
                INSERT INTO change_requests (id, incident_id, change_type, description, risk_level, proposed_date, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending_approval', datetime('now'))
                """,
                [cr_id, incident_id, change_type, description, risk_level, proposed_date],
            )
            await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "change_request_id": cr_id,
        "incident_id": incident_id,
        "change_type": change_type,
        "description": description,
        "risk_level": risk_level,
        "proposed_date": proposed_date,
        "status": "pending_approval",
    }


async def post_status(
    incident_id: str,
    status: str,
    message: str,
    db_path: str,
    session_id: str,
    affected_services: list[str] | None = None,
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                "UPDATE incidents SET status = ?, status_message = ?, updated_at = datetime('now') WHERE id = ?",
                [status, message, incident_id],
            )
            await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "incident_id": incident_id,
        "status": status,
        "message": message,
        "affected_services": affected_services or [],
        "posted_at": "now",
        "public_url": f"https://status.example.com/incidents/{incident_id}",
    }
