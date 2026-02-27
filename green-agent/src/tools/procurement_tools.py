from __future__ import annotations

import aiosqlite
from typing import Any

TOOL_DESCRIPTORS = [
    {
        "name": "get_purchase_request",
        "description": "Retrieve a purchase request by ID",
        "input_schema": {
            "type": "object",
            "properties": {"request_id": {"type": "string", "description": "The purchase request ID"}},
            "required": ["request_id"],
        },
    },
    {
        "name": "get_approval_chain",
        "description": "Get the approval chain for a purchase request",
        "input_schema": {
            "type": "object",
            "properties": {"request_id": {"type": "string", "description": "The purchase request ID"}},
            "required": ["request_id"],
        },
    },
    {
        "name": "get_budget",
        "description": "Get budget information for a department",
        "input_schema": {
            "type": "object",
            "properties": {"department": {"type": "string", "description": "Department name or ID"}},
            "required": ["department"],
        },
    },
    {
        "name": "approve_request",
        "description": "Approve a purchase request, updating its status to approved",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "The purchase request ID"},
                "approved_by": {"type": "string", "description": "ID or name of the approver"},
                "notes": {"type": "string", "description": "Approval notes (optional)"},
            },
            "required": ["request_id", "approved_by"],
        },
    },
    {
        "name": "escalate_to_committee",
        "description": "Escalate a purchase request to the committee for review",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "The purchase request ID"},
                "reason": {"type": "string", "description": "Reason for escalation"},
            },
            "required": ["request_id", "reason"],
        },
    },
    {
        "name": "send_notification",
        "description": "Send a notification about a purchase request to relevant stakeholders",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "The purchase request ID"},
                "recipient": {"type": "string", "description": "Recipient email or user ID"},
                "message": {"type": "string", "description": "Notification message body"},
                "subject": {"type": "string", "description": "Notification subject"},
            },
            "required": ["request_id", "recipient", "message"],
        },
    },
]


async def get_purchase_request(request_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM purchase_requests WHERE id = ?", [request_id]
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Purchase request {request_id} not found"}
    return dict(row)


async def get_approval_chain(request_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        # Try approval_chains table first
        try:
            async with db.execute(
                "SELECT * FROM approval_chains WHERE request_id = ? ORDER BY step_order ASC",
                [request_id],
            ) as cur:
                rows = await cur.fetchall()
            return {"approval_chain": [dict(r) for r in rows]}
        except Exception:
            pass
        # Fallback: try approvers column on the request itself
        try:
            async with db.execute(
                "SELECT approvers, status FROM purchase_requests WHERE id = ?", [request_id]
            ) as cur:
                row = await cur.fetchone()
            if row:
                return {"approval_chain": row[0], "status": row[1]}
        except Exception:
            pass
    return {"approval_chain": [], "request_id": request_id}


async def get_budget(department: str, db_path: str, session_id: str, **kwargs) -> dict:
    # Try to query a budgets table; fall back to mock data if it doesn't exist
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute(
                "SELECT * FROM budgets WHERE department = ?", [department]
            ) as cur:
                row = await cur.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
    # Mock budget data when table doesn't exist
    mock_budgets: dict[str, dict[str, Any]] = {
        "engineering": {"allocated": 500000.0, "spent": 320000.0, "remaining": 180000.0},
        "marketing": {"allocated": 200000.0, "spent": 150000.0, "remaining": 50000.0},
        "operations": {"allocated": 300000.0, "spent": 180000.0, "remaining": 120000.0},
        "hr": {"allocated": 150000.0, "spent": 90000.0, "remaining": 60000.0},
        "finance": {"allocated": 100000.0, "spent": 60000.0, "remaining": 40000.0},
    }
    dept_lower = department.lower()
    budget = mock_budgets.get(dept_lower, {"allocated": 100000.0, "spent": 50000.0, "remaining": 50000.0})
    return {"department": department, **budget, "currency": "USD"}


async def approve_request(
    request_id: str,
    approved_by: str,
    db_path: str,
    session_id: str,
    notes: str = "",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE purchase_requests SET status = 'approved', approved_by = ?, notes = ? WHERE id = ?",
            [approved_by, notes, request_id],
        )
        await db.commit()
    return {
        "success": True,
        "request_id": request_id,
        "status": "approved",
        "approved_by": approved_by,
        "notes": notes,
    }


async def escalate_to_committee(
    request_id: str,
    reason: str,
    db_path: str,
    session_id: str,
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE purchase_requests SET status = 'escalated_to_committee', escalation_reason = ? WHERE id = ?",
            [reason, request_id],
        )
        await db.commit()
    return {
        "success": True,
        "request_id": request_id,
        "status": "escalated_to_committee",
        "reason": reason,
    }


async def send_notification(
    request_id: str,
    recipient: str,
    message: str,
    db_path: str,
    session_id: str,
    subject: str = "",
    **kwargs,
) -> dict:
    # In a real system this would send an email/Slack message
    # Here we log the notification attempt
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                """
                INSERT INTO notifications (request_id, recipient, message, subject, sent_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                [request_id, recipient, message, subject],
            )
            await db.commit()
        except Exception:
            # notifications table may not exist; silently succeed
            pass
    return {
        "success": True,
        "request_id": request_id,
        "recipient": recipient,
        "subject": subject,
        "message": message,
        "status": "sent",
    }
