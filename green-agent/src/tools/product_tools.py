from __future__ import annotations

import aiosqlite
from typing import Any

# Mock product backlog fixture
_BACKLOG_FIXTURE: list[dict[str, Any]] = [
    {"id": "TICK-101", "title": "OAuth2 SSO integration", "priority": "high", "story_points": 8, "status": "ready", "sprint_id": None},
    {"id": "TICK-102", "title": "Dashboard performance optimization", "priority": "high", "story_points": 5, "status": "in_progress", "sprint_id": "SPR-5"},
    {"id": "TICK-103", "title": "CSV export for reports", "priority": "medium", "story_points": 3, "status": "ready", "sprint_id": None},
    {"id": "TICK-104", "title": "Mobile app push notifications", "priority": "medium", "story_points": 8, "status": "backlog", "sprint_id": None},
    {"id": "TICK-105", "title": "API rate limiting", "priority": "high", "story_points": 5, "status": "ready", "sprint_id": None},
    {"id": "TICK-106", "title": "Multi-currency billing", "priority": "low", "story_points": 13, "status": "backlog", "sprint_id": None},
    {"id": "TICK-107", "title": "Dark mode UI", "priority": "low", "story_points": 5, "status": "backlog", "sprint_id": None},
    {"id": "TICK-108", "title": "GDPR data export endpoint", "priority": "high", "story_points": 3, "status": "ready", "sprint_id": None},
]

_SPRINT_FIXTURE: dict[str, dict[str, Any]] = {
    "SPR-5": {
        "id": "SPR-5",
        "name": "Sprint 5",
        "start_date": "2026-02-24",
        "end_date": "2026-03-07",
        "status": "active",
        "team_id": "TEAM-ENG",
        "velocity_target": 40,
        "committed_points": 35,
        "completed_points": 22,
        "tickets": ["TICK-102", "TICK-109", "TICK-110", "TICK-111"],
    },
    "SPR-6": {
        "id": "SPR-6",
        "name": "Sprint 6",
        "start_date": "2026-03-10",
        "end_date": "2026-03-21",
        "status": "planning",
        "team_id": "TEAM-ENG",
        "velocity_target": 40,
        "committed_points": 0,
        "completed_points": 0,
        "tickets": [],
    },
}

TOOL_DESCRIPTORS = [
    {
        "name": "get_product_backlog",
        "description": "Get the product backlog, optionally filtered by priority or status",
        "input_schema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "description": "Filter by priority: high/medium/low"},
                "status": {"type": "string", "description": "Filter by status: backlog/ready/in_progress/done"},
                "limit": {"type": "integer", "description": "Max items to return"},
            },
            "required": [],
        },
    },
    {
        "name": "get_sprint",
        "description": "Get sprint details by sprint ID",
        "input_schema": {
            "type": "object",
            "properties": {"sprint_id": {"type": "string", "description": "The sprint ID"}},
            "required": ["sprint_id"],
        },
    },
    {
        "name": "get_team_capacity",
        "description": "Get team capacity for a sprint, accounting for PTO and availability",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "The team ID"},
                "sprint_id": {"type": "string", "description": "The sprint ID to calculate capacity for"},
            },
            "required": ["team_id"],
        },
    },
    {
        "name": "create_jira_ticket",
        "description": "Create a new Jira ticket in the product backlog",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Ticket title/summary"},
                "description": {"type": "string", "description": "Detailed description"},
                "priority": {"type": "string", "description": "Priority: high/medium/low"},
                "story_points": {"type": "integer", "description": "Story point estimate"},
                "assignee": {"type": "string", "description": "Assignee user ID (optional)"},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "Ticket labels"},
            },
            "required": ["title", "priority"],
        },
    },
    {
        "name": "set_dependencies",
        "description": "Set dependency links between Jira tickets",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "The ticket that has dependencies"},
                "depends_on": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ticket IDs that must be completed first",
                },
                "blocks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ticket IDs that this ticket blocks",
                },
            },
            "required": ["ticket_id"],
        },
    },
]


async def get_product_backlog(
    db_path: str,
    session_id: str,
    priority: str = "",
    status: str = "",
    limit: int = 50,
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            query = "SELECT * FROM backlog WHERE 1=1"
            args: list[Any] = []
            if priority:
                query += " AND priority = ?"; args.append(priority)
            if status:
                query += " AND status = ?"; args.append(status)
            query += f" ORDER BY priority DESC LIMIT {max(1, min(int(limit), 200))}"
            async with db.execute(query, args) as cur:
                rows = await cur.fetchall()
            if rows:
                return {"backlog": [dict(r) for r in rows], "count": len(rows)}
        except Exception:
            pass
    # Fallback to fixture
    items = list(_BACKLOG_FIXTURE)
    if priority:
        items = [i for i in items if i.get("priority") == priority]
    if status:
        items = [i for i in items if i.get("status") == status]
    items = items[:max(1, min(int(limit), 200))]
    return {"backlog": items, "count": len(items), "source": "fixture"}


async def get_sprint(sprint_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute("SELECT * FROM sprints WHERE id = ?", [sprint_id]) as cur:
                row = await cur.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
    fixture = _SPRINT_FIXTURE.get(sprint_id)
    if fixture:
        return fixture
    return {"error": f"Sprint {sprint_id} not found"}


async def get_team_capacity(
    team_id: str,
    db_path: str,
    session_id: str,
    sprint_id: str = "",
    **kwargs,
) -> dict:
    sprint = None
    if sprint_id:
        sprint = await get_sprint(sprint_id, db_path, session_id)

    # Try to get team members from DB
    members: list[dict[str, Any]] = []
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute(
                "SELECT id, name, pto_balance FROM employees WHERE team_id = ?", [team_id]
            ) as cur:
                rows = await cur.fetchall()
            members = [dict(r) for r in rows]
        except Exception:
            pass

    # Fallback mock members
    if not members:
        members = [
            {"id": "EMP-001", "name": "Alice", "pto_planned_days": 0, "availability_pct": 100},
            {"id": "EMP-002", "name": "Bob", "pto_planned_days": 2, "availability_pct": 80},
            {"id": "EMP-003", "name": "Carol", "pto_planned_days": 0, "availability_pct": 100},
            {"id": "EMP-004", "name": "Dave", "pto_planned_days": 0, "availability_pct": 100},
        ]

    sprint_days = 10  # 2-week sprint
    total_person_days = len(members) * sprint_days
    pto_days = sum(m.get("pto_planned_days", 0) for m in members)
    capacity_points = max(0, (total_person_days - pto_days) * 0.8 * 2)  # ~1.6 pts/person/day average

    return {
        "team_id": team_id,
        "sprint_id": sprint_id,
        "member_count": len(members),
        "members": members,
        "sprint_days": sprint_days,
        "total_person_days": total_person_days,
        "pto_days": pto_days,
        "available_person_days": total_person_days - pto_days,
        "capacity_points": int(capacity_points),
    }


async def create_jira_ticket(
    title: str,
    priority: str,
    db_path: str,
    session_id: str,
    description: str = "",
    story_points: int = 0,
    assignee: str = "",
    labels: list[str] | None = None,
    **kwargs,
) -> dict:
    import uuid as _uuid
    ticket_id = f"TICK-{_uuid.uuid4().hex[:6].upper()}"
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                """
                INSERT INTO backlog (id, title, description, priority, story_points, assignee, status)
                VALUES (?, ?, ?, ?, ?, ?, 'backlog')
                """,
                [ticket_id, title, description, priority, story_points, assignee],
            )
            await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "ticket_id": ticket_id,
        "title": title,
        "priority": priority,
        "story_points": story_points,
        "assignee": assignee,
        "labels": labels or [],
        "status": "backlog",
        "url": f"https://jira.example.com/browse/{ticket_id}",
    }


async def set_dependencies(
    ticket_id: str,
    db_path: str,
    session_id: str,
    depends_on: list[str] | None = None,
    blocks: list[str] | None = None,
    **kwargs,
) -> dict:
    links_created = []
    async with aiosqlite.connect(db_path) as db:
        try:
            for dep in (depends_on or []):
                await db.execute(
                    "INSERT OR IGNORE INTO ticket_links (ticket_id, linked_ticket_id, link_type) VALUES (?, ?, 'depends_on')",
                    [ticket_id, dep],
                )
                links_created.append({"type": "depends_on", "ticket": dep})
            for blk in (blocks or []):
                await db.execute(
                    "INSERT OR IGNORE INTO ticket_links (ticket_id, linked_ticket_id, link_type) VALUES (?, ?, 'blocks')",
                    [ticket_id, blk],
                )
                links_created.append({"type": "blocks", "ticket": blk})
            await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "ticket_id": ticket_id,
        "depends_on": depends_on or [],
        "blocks": blocks or [],
        "links_created": links_created,
    }
