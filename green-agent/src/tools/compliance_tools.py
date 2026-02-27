from __future__ import annotations

import aiosqlite
from typing import Any

# PEP (Politically Exposed Person) fixture list
_PEP_LIST: list[dict[str, Any]] = [
    {"name": "John Politician", "dob": "1965-03-15", "country": "US", "role": "Senator", "risk_level": "high"},
    {"name": "Jane Diplomat", "dob": "1972-07-22", "country": "UK", "role": "Ambassador", "risk_level": "medium"},
    {"name": "Carlos Minister", "dob": "1958-11-08", "country": "BR", "role": "Finance Minister", "risk_level": "high"},
    {"name": "Li Official", "dob": "1970-02-14", "country": "CN", "role": "State Official", "risk_level": "high"},
]

TOOL_DESCRIPTORS = [
    {
        "name": "get_customer_kyc",
        "description": "Retrieve KYC (Know Your Customer) data for a customer",
        "input_schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string", "description": "The customer ID"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "check_pep_match",
        "description": "Check if a customer matches any entry in the PEP (Politically Exposed Person) list",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "Full name of the customer"},
                "dob": {"type": "string", "description": "Date of birth (YYYY-MM-DD)"},
                "country": {"type": "string", "description": "Country of residence or nationality"},
            },
            "required": ["customer_name"],
        },
    },
    {
        "name": "apply_edd",
        "description": "Apply Enhanced Due Diligence (EDD) to a compliance case",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "The compliance case ID"},
                "edd_reason": {"type": "string", "description": "Reason for applying EDD"},
                "assigned_analyst": {"type": "string", "description": "Analyst assigned to EDD review"},
            },
            "required": ["case_id", "edd_reason"],
        },
    },
    {
        "name": "flag_for_review",
        "description": "Flag a compliance case for manual review",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "The case ID"},
                "reason": {"type": "string", "description": "Reason for flagging"},
                "priority": {"type": "string", "description": "Priority level: high/medium/low"},
            },
            "required": ["case_id", "reason"],
        },
    },
    {
        "name": "close_case",
        "description": "Close a compliance case with a resolution",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "The case ID"},
                "resolution": {"type": "string", "description": "Resolution summary"},
                "outcome": {"type": "string", "description": "Outcome: 'cleared', 'escalated', 'reported'"},
            },
            "required": ["case_id", "resolution"],
        },
    },
]


async def get_customer_kyc(customer_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM customers WHERE id = ?", [customer_id]) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Customer {customer_id} not found"}
    result = dict(row)
    # Supplement with KYC fields if stored separately
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute(
                "SELECT * FROM kyc_records WHERE customer_id = ?", [customer_id]
            ) as cur:
                kyc_row = await cur.fetchone()
            if kyc_row:
                result.update(dict(kyc_row))
        except Exception:
            pass
    return result


async def check_pep_match(
    customer_name: str,
    db_path: str,
    session_id: str,
    dob: str = "",
    country: str = "",
    **kwargs,
) -> dict:
    name_lower = customer_name.lower()
    matches: list[dict[str, Any]] = []
    for entry in _PEP_LIST:
        entry_name_lower = entry["name"].lower()
        # Fuzzy name match: check if significant word overlap
        name_words = set(name_lower.split())
        entry_words = set(entry_name_lower.split())
        common = name_words & entry_words
        if len(common) >= min(2, len(name_words)):
            # Check optional filters
            dob_match = not dob or entry.get("dob") == dob
            country_match = not country or entry.get("country", "").upper() == country.upper()
            if dob_match and country_match:
                matches.append(entry)
    return {
        "customer_name": customer_name,
        "is_pep": len(matches) > 0,
        "matches": matches,
        "match_count": len(matches),
    }


async def apply_edd(
    case_id: str,
    edd_reason: str,
    db_path: str,
    session_id: str,
    assigned_analyst: str = "",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE cases
            SET status = 'edd_applied', edd_reason = ?, assigned_analyst = ?
            WHERE id = ?
            """,
            [edd_reason, assigned_analyst, case_id],
        )
        await db.commit()
    return {
        "success": True,
        "case_id": case_id,
        "status": "edd_applied",
        "edd_reason": edd_reason,
        "assigned_analyst": assigned_analyst,
    }


async def flag_for_review(
    case_id: str,
    reason: str,
    db_path: str,
    session_id: str,
    priority: str = "medium",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE cases
            SET status = 'flagged_for_review', review_reason = ?, priority = ?
            WHERE id = ?
            """,
            [reason, priority, case_id],
        )
        await db.commit()
    return {
        "success": True,
        "case_id": case_id,
        "status": "flagged_for_review",
        "reason": reason,
        "priority": priority,
    }


async def close_case(
    case_id: str,
    resolution: str,
    db_path: str,
    session_id: str,
    outcome: str = "cleared",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE cases
            SET status = 'closed', resolution = ?, outcome = ?, closed_at = datetime('now')
            WHERE id = ?
            """,
            [resolution, outcome, case_id],
        )
        await db.commit()
    return {
        "success": True,
        "case_id": case_id,
        "status": "closed",
        "resolution": resolution,
        "outcome": outcome,
    }
