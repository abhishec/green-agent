from __future__ import annotations

import math
import aiosqlite
from typing import Any

TOOL_DESCRIPTORS = [
    {
        "name": "get_employee",
        "description": "Retrieve employee record by employee ID",
        "input_schema": {
            "type": "object",
            "properties": {"employee_id": {"type": "string", "description": "The employee ID"}},
            "required": ["employee_id"],
        },
    },
    {
        "name": "get_pto_balance",
        "description": "Get an employee's PTO balance, rounded up to the nearest 0.5 day",
        "input_schema": {
            "type": "object",
            "properties": {"employee_id": {"type": "string", "description": "The employee ID"}},
            "required": ["employee_id"],
        },
    },
    {
        "name": "revoke_access",
        "description": "Revoke system access for an employee (sets revoked_at timestamp on access records)",
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "The employee ID"},
                "systems": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of system names to revoke access for. Revokes all if omitted.",
                },
            },
            "required": ["employee_id"],
        },
    },
    {
        "name": "transfer_assets",
        "description": "Mark company assets as transferred from a departing employee",
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "The employee ID"},
                "asset_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific asset IDs to transfer. Transfers all if omitted.",
                },
                "transfer_to": {"type": "string", "description": "Employee ID or department receiving the assets"},
            },
            "required": ["employee_id"],
        },
    },
    {
        "name": "process_final_pay",
        "description": "Compute and record the final pay for a departing employee",
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "The employee ID"},
                "termination_date": {"type": "string", "description": "Termination date in YYYY-MM-DD format"},
                "include_pto_payout": {"type": "boolean", "description": "Whether to include PTO payout in final pay"},
            },
            "required": ["employee_id", "termination_date"],
        },
    },
    {
        "name": "send_offboarding_checklist",
        "description": "Send an offboarding checklist to the employee and their manager",
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "The employee ID"},
                "manager_id": {"type": "string", "description": "The manager's employee ID"},
                "custom_items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional checklist items beyond the standard template",
                },
            },
            "required": ["employee_id", "manager_id"],
        },
    },
]


def _round_up_half(value: float) -> float:
    """Round up to nearest 0.5 day."""
    return math.ceil(value * 2) / 2


async def get_employee(employee_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM employees WHERE id = ?", [employee_id]) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Employee {employee_id} not found"}
    return dict(row)


async def get_pto_balance(employee_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT pto_balance FROM employees WHERE id = ?", [employee_id]
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Employee {employee_id} not found"}
    raw_balance = float(row["pto_balance"] or 0.0)
    rounded = _round_up_half(raw_balance)
    return {
        "employee_id": employee_id,
        "pto_balance_raw": raw_balance,
        "pto_balance": rounded,
        "rounding_rule": "rounded up to nearest 0.5 day",
    }


async def revoke_access(
    employee_id: str,
    db_path: str,
    session_id: str,
    systems: list[str] | None = None,
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        if systems:
            for system in systems:
                await db.execute(
                    """
                    UPDATE access_records
                    SET revoked_at = datetime('now')
                    WHERE employee_id = ? AND system_name = ? AND revoked_at IS NULL
                    """,
                    [employee_id, system],
                )
        else:
            await db.execute(
                """
                UPDATE access_records
                SET revoked_at = datetime('now')
                WHERE employee_id = ? AND revoked_at IS NULL
                """,
                [employee_id],
            )
        await db.commit()
        async with db.execute(
            "SELECT COUNT(*) FROM access_records WHERE employee_id = ? AND revoked_at IS NOT NULL",
            [employee_id],
        ) as cur:
            row = await cur.fetchone()
        revoked_count = row[0] if row else 0
    return {
        "success": True,
        "employee_id": employee_id,
        "systems_revoked": systems or "all",
        "revoked_count": revoked_count,
    }


async def transfer_assets(
    employee_id: str,
    db_path: str,
    session_id: str,
    asset_ids: list[str] | None = None,
    transfer_to: str = "unassigned",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        if asset_ids:
            transferred = []
            for asset_id in asset_ids:
                await db.execute(
                    "UPDATE assets SET status = 'transferred', assigned_to = ? WHERE id = ? AND employee_id = ?",
                    [transfer_to, asset_id, employee_id],
                )
                transferred.append(asset_id)
        else:
            await db.execute(
                "UPDATE assets SET status = 'transferred', assigned_to = ? WHERE employee_id = ?",
                [transfer_to, employee_id],
            )
            async with db.execute(
                "SELECT COUNT(*) FROM assets WHERE employee_id = ?", [employee_id]
            ) as cur:
                row = await cur.fetchone()
            transferred = f"{row[0] if row else 0} assets"
        await db.commit()
    return {
        "success": True,
        "employee_id": employee_id,
        "transferred_assets": transferred,
        "transfer_to": transfer_to,
        "status": "transferred",
    }


async def process_final_pay(
    employee_id: str,
    termination_date: str,
    db_path: str,
    session_id: str,
    include_pto_payout: bool = True,
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT salary, pto_balance FROM employees WHERE id = ?", [employee_id]
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Employee {employee_id} not found"}

    annual_salary = float(row["salary"] or 0.0)
    pto_balance = _round_up_half(float(row["pto_balance"] or 0.0))
    daily_rate = annual_salary / 260  # 52 weeks * 5 days

    pto_payout = round(pto_balance * daily_rate, 2) if include_pto_payout else 0.0
    # Assume final pay covers the current pay period up to termination_date
    final_pay = {
        "employee_id": employee_id,
        "termination_date": termination_date,
        "annual_salary": annual_salary,
        "daily_rate": round(daily_rate, 2),
        "pto_balance_days": pto_balance,
        "pto_payout": pto_payout,
        "final_paycheck_gross": pto_payout,
        "currency": "USD",
        "include_pto_payout": include_pto_payout,
        "status": "computed",
    }
    return final_pay


async def send_offboarding_checklist(
    employee_id: str,
    manager_id: str,
    db_path: str,
    session_id: str,
    custom_items: list[str] | None = None,
    **kwargs,
) -> dict:
    standard_checklist = [
        "Return company laptop and equipment",
        "Return company badge/key card",
        "Complete knowledge transfer documentation",
        "Remove personal files from company systems",
        "Complete exit interview",
        "Return any company credit cards",
        "Update out-of-office message",
        "Provide handover notes to team",
    ]
    full_checklist = standard_checklist + (custom_items or [])
    # In a real system, send email to employee and manager
    return {
        "success": True,
        "employee_id": employee_id,
        "manager_id": manager_id,
        "checklist_items": full_checklist,
        "checklist_count": len(full_checklist),
        "recipients": [employee_id, manager_id],
        "status": "sent",
    }
