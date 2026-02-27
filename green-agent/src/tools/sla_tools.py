from __future__ import annotations

import aiosqlite
from datetime import datetime, timezone
from typing import Any

TOOL_DESCRIPTORS = [
    {
        "name": "get_sla_config",
        "description": "Retrieve the SLA configuration for a service or tier",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string", "description": "The service or SLA config ID"},
            },
            "required": ["service_id"],
        },
    },
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
        "name": "get_on_call",
        "description": "Get the current on-call engineer for a service or team",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string", "description": "The service or team ID"},
                "timestamp": {"type": "string", "description": "ISO timestamp to check on-call for (defaults to now)"},
            },
            "required": ["service_id"],
        },
    },
    {
        "name": "is_quiet_hours",
        "description": "Check whether the current time (or a given time) falls within quiet hours (22:00-08:00 local)",
        "input_schema": {
            "type": "object",
            "properties": {
                "timestamp": {"type": "string", "description": "ISO timestamp to check (defaults to now)"},
                "timezone_offset": {"type": "integer", "description": "UTC offset in hours (e.g. -5 for EST)"},
            },
            "required": [],
        },
    },
    {
        "name": "create_escalation",
        "description": "Create an escalation incident record",
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_incident_id": {"type": "string", "description": "The parent incident being escalated"},
                "escalation_level": {"type": "string", "description": "Escalation level (L1/L2/L3/management)"},
                "assigned_to": {"type": "string", "description": "ID of the person/team to escalate to"},
                "reason": {"type": "string", "description": "Reason for escalation"},
                "severity": {"type": "string", "description": "Severity level (critical/high/medium/low)"},
            },
            "required": ["parent_incident_id", "escalation_level", "assigned_to"],
        },
    },
    {
        "name": "schedule_maintenance",
        "description": "Schedule a maintenance window for a service",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string", "description": "The service ID"},
                "start_time": {"type": "string", "description": "Maintenance window start (ISO timestamp)"},
                "end_time": {"type": "string", "description": "Maintenance window end (ISO timestamp)"},
                "description": {"type": "string", "description": "Description of the maintenance work"},
                "notify_stakeholders": {"type": "boolean", "description": "Whether to send notifications"},
            },
            "required": ["service_id", "start_time", "end_time"],
        },
    },
]


async def get_sla_config(service_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sla_configs WHERE id = ? OR service_id = ?", [service_id, service_id]
        ) as cur:
            row = await cur.fetchone()
    if not row:
        # Return a default SLA config
        return {
            "service_id": service_id,
            "tier": "standard",
            "response_time_minutes": 60,
            "resolution_time_hours": 24,
            "uptime_target": 99.9,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
            "escalation_after_minutes": 30,
        }
    return dict(row)


async def get_incident(incident_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM incidents WHERE id = ?", [incident_id]) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Incident {incident_id} not found"}
    return dict(row)


async def get_on_call(
    service_id: str,
    db_path: str,
    session_id: str,
    timestamp: str = "",
    **kwargs,
) -> dict:
    check_time = timestamp or datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute(
                """
                SELECT * FROM on_call_schedules
                WHERE service_id = ?
                  AND start_time <= ?
                  AND end_time >= ?
                ORDER BY start_time DESC
                LIMIT 1
                """,
                [service_id, check_time, check_time],
            ) as cur:
                row = await cur.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
    # Fallback mock
    return {
        "service_id": service_id,
        "on_call_engineer": "ops-team@example.com",
        "phone": "+1-555-0100",
        "as_of": check_time,
        "source": "fallback",
    }


async def is_quiet_hours(
    db_path: str,
    session_id: str,
    timestamp: str = "",
    timezone_offset: int = 0,
    **kwargs,
) -> dict:
    if timestamp:
        try:
            check_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            check_dt = datetime.now(timezone.utc)
    else:
        check_dt = datetime.now(timezone.utc)

    # Apply timezone offset
    local_hour = (check_dt.hour + timezone_offset) % 24
    # Quiet hours: 22:00 (10 PM) to 08:00 (8 AM)
    in_quiet = local_hour >= 22 or local_hour < 8
    return {
        "is_quiet_hours": in_quiet,
        "current_hour_local": local_hour,
        "quiet_hours_window": "22:00-08:00",
        "timezone_offset": timezone_offset,
        "timestamp_checked": check_dt.isoformat(),
    }


async def create_escalation(
    parent_incident_id: str,
    escalation_level: str,
    assigned_to: str,
    db_path: str,
    session_id: str,
    reason: str = "",
    severity: str = "high",
    **kwargs,
) -> dict:
    import uuid as _uuid
    escalation_id = f"ESC-{_uuid.uuid4().hex[:8].upper()}"
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                """
                INSERT INTO incidents
                    (id, parent_incident_id, type, escalation_level, assigned_to, reason, severity, status, created_at)
                VALUES (?, ?, 'escalation', ?, ?, ?, ?, 'open', datetime('now'))
                """,
                [escalation_id, parent_incident_id, escalation_level, assigned_to, reason, severity],
            )
            await db.commit()
        except Exception:
            # If column set doesn't match, try minimal insert
            try:
                await db.execute(
                    "INSERT INTO incidents (id, status, severity) VALUES (?, 'open', ?)",
                    [escalation_id, severity],
                )
                await db.commit()
            except Exception:
                pass
    return {
        "success": True,
        "escalation_id": escalation_id,
        "parent_incident_id": parent_incident_id,
        "escalation_level": escalation_level,
        "assigned_to": assigned_to,
        "severity": severity,
        "reason": reason,
        "status": "open",
    }


async def schedule_maintenance(
    service_id: str,
    start_time: str,
    end_time: str,
    db_path: str,
    session_id: str,
    description: str = "",
    notify_stakeholders: bool = True,
    **kwargs,
) -> dict:
    import uuid as _uuid
    window_id = f"MNT-{_uuid.uuid4().hex[:8].upper()}"
    return {
        "success": True,
        "maintenance_id": window_id,
        "service_id": service_id,
        "start_time": start_time,
        "end_time": end_time,
        "description": description,
        "notify_stakeholders": notify_stakeholders,
        "status": "scheduled",
    }
