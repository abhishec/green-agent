from __future__ import annotations

import aiosqlite
from typing import Any

# Mock parties fixture for disputes
_PARTIES_FIXTURE: dict[str, list[dict[str, Any]]] = {
    "CASE-001": [
        {"party_id": "PARTY-A1", "name": "Alice Corp", "role": "claimant", "contact": "alice@corp.com"},
        {"party_id": "PARTY-B1", "name": "Bob Industries", "role": "respondent", "contact": "bob@industries.com"},
        {"party_id": "PARTY-M1", "name": "Mediator Services LLC", "role": "mediator", "contact": "mediate@services.com"},
    ],
    "CASE-002": [
        {"party_id": "PARTY-A2", "name": "Carol Enterprises", "role": "claimant", "contact": "carol@enterprises.com"},
        {"party_id": "PARTY-B2", "name": "Dave Solutions", "role": "respondent", "contact": "dave@solutions.com"},
    ],
    "CASE-003": [
        {"party_id": "PARTY-A3", "name": "Eve Consulting", "role": "claimant", "contact": "eve@consulting.com"},
        {"party_id": "PARTY-B3", "name": "Frank Systems", "role": "respondent", "contact": "frank@systems.com"},
        {"party_id": "PARTY-C3", "name": "Grace Holdings", "role": "third_party", "contact": "grace@holdings.com"},
    ],
}

TOOL_DESCRIPTORS = [
    {
        "name": "get_dispute",
        "description": "Retrieve a dispute case by ID",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string", "description": "The dispute case ID"}},
            "required": ["case_id"],
        },
    },
    {
        "name": "get_parties",
        "description": "Get all parties involved in a dispute case",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string", "description": "The dispute case ID"}},
            "required": ["case_id"],
        },
    },
    {
        "name": "escalate_dispute",
        "description": "Escalate a dispute case to a higher authority",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "The dispute case ID"},
                "escalation_reason": {"type": "string", "description": "Reason for escalation"},
                "escalated_to": {"type": "string", "description": "Person or body being escalated to"},
            },
            "required": ["case_id", "escalation_reason"],
        },
    },
    {
        "name": "request_mediation",
        "description": "Request mediation for a dispute case",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "The dispute case ID"},
                "mediator_id": {"type": "string", "description": "Preferred mediator ID (optional)"},
                "proposed_date": {"type": "string", "description": "Proposed mediation date (YYYY-MM-DD)"},
                "notes": {"type": "string", "description": "Additional notes for the mediation request"},
            },
            "required": ["case_id"],
        },
    },
]


async def get_dispute(case_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM cases WHERE id = ?", [case_id]) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Dispute case {case_id} not found"}
    return dict(row)


async def get_parties(case_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    # Try DB first
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute(
                "SELECT * FROM dispute_parties WHERE case_id = ?", [case_id]
            ) as cur:
                rows = await cur.fetchall()
            if rows:
                return {"case_id": case_id, "parties": [dict(r) for r in rows]}
        except Exception:
            pass
    # Fall back to fixture
    parties = _PARTIES_FIXTURE.get(case_id, [])
    return {
        "case_id": case_id,
        "parties": parties,
        "party_count": len(parties),
        "source": "fixture" if parties else "none",
    }


async def escalate_dispute(
    case_id: str,
    escalation_reason: str,
    db_path: str,
    session_id: str,
    escalated_to: str = "",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE cases
            SET status = 'escalated', escalation_reason = ?, escalated_to = ?
            WHERE id = ?
            """,
            [escalation_reason, escalated_to, case_id],
        )
        await db.commit()
    return {
        "success": True,
        "case_id": case_id,
        "status": "escalated",
        "escalation_reason": escalation_reason,
        "escalated_to": escalated_to,
    }


async def request_mediation(
    case_id: str,
    db_path: str,
    session_id: str,
    mediator_id: str = "",
    proposed_date: str = "",
    notes: str = "",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE cases
            SET status = 'mediation_requested', mediator_id = ?, mediation_date = ?, mediation_notes = ?
            WHERE id = ?
            """,
            [mediator_id, proposed_date, notes, case_id],
        )
        await db.commit()
    return {
        "success": True,
        "case_id": case_id,
        "status": "mediation_requested",
        "mediator_id": mediator_id,
        "proposed_date": proposed_date,
        "notes": notes,
    }
