from __future__ import annotations

import aiosqlite
from typing import Any

# Mock policy/rider fixture data
_POLICY_FIXTURE: dict[str, dict[str, Any]] = {
    "POL-001": {
        "id": "POL-001",
        "holder_name": "Alice Johnson",
        "policy_type": "health",
        "coverage_amount": 100000.0,
        "deductible": 2000.0,
        "premium": 450.0,
        "status": "active",
        "effective_date": "2024-01-01",
        "expiry_date": "2024-12-31",
    },
    "POL-002": {
        "id": "POL-002",
        "holder_name": "Bob Smith",
        "policy_type": "auto",
        "coverage_amount": 50000.0,
        "deductible": 1000.0,
        "premium": 120.0,
        "status": "active",
        "effective_date": "2024-03-01",
        "expiry_date": "2025-02-28",
    },
    "POL-003": {
        "id": "POL-003",
        "holder_name": "Carol White",
        "policy_type": "property",
        "coverage_amount": 250000.0,
        "deductible": 5000.0,
        "premium": 800.0,
        "status": "active",
        "effective_date": "2023-06-01",
        "expiry_date": "2024-05-31",
    },
}

_RIDER_FIXTURE: dict[str, dict[str, Any]] = {
    "RDR-001": {
        "id": "RDR-001",
        "policy_id": "POL-001",
        "rider_type": "dental",
        "coverage_amount": 5000.0,
        "additional_premium": 25.0,
        "status": "active",
    },
    "RDR-002": {
        "id": "RDR-002",
        "policy_id": "POL-001",
        "rider_type": "vision",
        "coverage_amount": 2000.0,
        "additional_premium": 10.0,
        "status": "active",
    },
    "RDR-003": {
        "id": "RDR-003",
        "policy_id": "POL-002",
        "rider_type": "roadside_assistance",
        "coverage_amount": 500.0,
        "additional_premium": 5.0,
        "status": "active",
    },
}

TOOL_DESCRIPTORS = [
    {
        "name": "get_claim",
        "description": "Retrieve an insurance claim/case by ID",
        "input_schema": {
            "type": "object",
            "properties": {"claim_id": {"type": "string", "description": "The claim/case ID"}},
            "required": ["claim_id"],
        },
    },
    {
        "name": "get_policy",
        "description": "Retrieve an insurance policy by ID",
        "input_schema": {
            "type": "object",
            "properties": {"policy_id": {"type": "string", "description": "The policy ID"}},
            "required": ["policy_id"],
        },
    },
    {
        "name": "get_rider",
        "description": "Retrieve an insurance rider by ID",
        "input_schema": {
            "type": "object",
            "properties": {"rider_id": {"type": "string", "description": "The rider ID"}},
            "required": ["rider_id"],
        },
    },
    {
        "name": "check_fraud_flag",
        "description": "Check whether a claim or policy has any fraud flags",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string", "description": "The claim/case ID to check"},
            },
            "required": ["claim_id"],
        },
    },
    {
        "name": "approve_claim_partial",
        "description": "Partially approve an insurance claim for a specified amount",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string", "description": "The claim/case ID"},
                "approved_amount": {"type": "number", "description": "The approved payout amount"},
                "notes": {"type": "string", "description": "Approval notes"},
            },
            "required": ["claim_id", "approved_amount"],
        },
    },
    {
        "name": "schedule_inspection",
        "description": "Schedule a physical inspection for an insurance claim",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string", "description": "The claim/case ID"},
                "inspection_date": {"type": "string", "description": "Requested inspection date (YYYY-MM-DD)"},
                "inspector_id": {"type": "string", "description": "ID of the assigned inspector (optional)"},
            },
            "required": ["claim_id", "inspection_date"],
        },
    },
    {
        "name": "flag_for_review",
        "description": "Flag a claim for manual review due to irregularities or high value",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string", "description": "The claim/case ID"},
                "reason": {"type": "string", "description": "Reason for flagging"},
            },
            "required": ["claim_id", "reason"],
        },
    },
]


async def get_claim(claim_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        # Claims may live in a 'cases' table
        async with db.execute(
            "SELECT * FROM cases WHERE id = ?", [claim_id]
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Claim {claim_id} not found"}
    return dict(row)


async def get_policy(policy_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    # Try DB first, then fixture
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute(
                "SELECT * FROM policies WHERE id = ?", [policy_id]
            ) as cur:
                row = await cur.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
    fixture = _POLICY_FIXTURE.get(policy_id)
    if fixture:
        return fixture
    return {"error": f"Policy {policy_id} not found"}


async def get_rider(rider_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    # Try DB first, then fixture
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute(
                "SELECT * FROM riders WHERE id = ?", [rider_id]
            ) as cur:
                row = await cur.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
    fixture = _RIDER_FIXTURE.get(rider_id)
    if fixture:
        return fixture
    return {"error": f"Rider {rider_id} not found"}


async def check_fraud_flag(claim_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT fraud_flag, fraud_reason, status FROM cases WHERE id = ?", [claim_id]
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Claim {claim_id} not found"}
    result = dict(row)
    result["has_fraud_flag"] = bool(result.get("fraud_flag"))
    return result


async def approve_claim_partial(
    claim_id: str,
    approved_amount: float,
    db_path: str,
    session_id: str,
    notes: str = "",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE cases
            SET status = 'partially_approved', approved_amount = ?, notes = ?
            WHERE id = ?
            """,
            [approved_amount, notes, claim_id],
        )
        await db.commit()
    return {
        "success": True,
        "claim_id": claim_id,
        "status": "partially_approved",
        "approved_amount": approved_amount,
        "notes": notes,
    }


async def schedule_inspection(
    claim_id: str,
    inspection_date: str,
    db_path: str,
    session_id: str,
    inspector_id: str = "",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE cases
            SET status = 'inspection_scheduled', inspection_date = ?, inspector_id = ?
            WHERE id = ?
            """,
            [inspection_date, inspector_id, claim_id],
        )
        await db.commit()
    return {
        "success": True,
        "claim_id": claim_id,
        "status": "inspection_scheduled",
        "inspection_date": inspection_date,
        "inspector_id": inspector_id,
    }


async def flag_for_review(
    claim_id: str,
    reason: str,
    db_path: str,
    session_id: str,
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE cases
            SET status = 'flagged_for_review', fraud_reason = ?
            WHERE id = ?
            """,
            [reason, claim_id],
        )
        await db.commit()
    return {
        "success": True,
        "claim_id": claim_id,
        "status": "flagged_for_review",
        "reason": reason,
    }
