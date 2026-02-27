from __future__ import annotations

import aiosqlite
from typing import Any

TOOL_DESCRIPTORS = [
    {
        "name": "get_journal_entries",
        "description": "Retrieve journal entries, optionally filtered by date range or account",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "GL account code to filter by (optional)"},
                "date_from": {"type": "string", "description": "Start date filter (YYYY-MM-DD)"},
                "date_to": {"type": "string", "description": "End date filter (YYYY-MM-DD)"},
                "limit": {"type": "integer", "description": "Maximum records to return (default 50)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_deferred_revenue",
        "description": "Get the deferred revenue schedule for a customer or contract",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID (optional)"},
                "contract_id": {"type": "string", "description": "Contract ID (optional)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_depreciation",
        "description": "Get the depreciation schedule for an asset or asset class",
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "Asset ID (optional)"},
                "asset_class": {"type": "string", "description": "Asset class (e.g. 'equipment', 'software')"},
                "fiscal_year": {"type": "string", "description": "Fiscal year (YYYY)"},
            },
            "required": [],
        },
    },
    {
        "name": "run_close",
        "description": "Perform month-end close operations for a given period",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "Accounting period to close (YYYY-MM)"},
                "dry_run": {"type": "boolean", "description": "If true, validate only without committing"},
            },
            "required": ["period"],
        },
    },
    {
        "name": "post_fx_variance",
        "description": "Post a foreign exchange variance journal entry",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "Accounting period (YYYY-MM)"},
                "from_currency": {"type": "string", "description": "Source currency"},
                "to_currency": {"type": "string", "description": "Target currency"},
                "variance_amount": {"type": "number", "description": "FX variance amount (in to_currency)"},
                "gl_account": {"type": "string", "description": "GL account for FX variance posting"},
            },
            "required": ["period", "from_currency", "to_currency", "variance_amount"],
        },
    },
]


async def get_journal_entries(
    db_path: str,
    session_id: str,
    account: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 50,
    **kwargs,
) -> dict:
    query = "SELECT * FROM transactions WHERE 1=1"
    args: list[Any] = []
    if account:
        query += " AND (debit_account = ? OR credit_account = ?)"
        args.extend([account, account])
    if date_from:
        query += " AND date >= ?"
        args.append(date_from)
    if date_to:
        query += " AND date <= ?"
        args.append(date_to)
    query += f" ORDER BY date DESC LIMIT {max(1, min(int(limit), 500))}"

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, args) as cur:
            rows = await cur.fetchall()
    return {"journal_entries": [dict(r) for r in rows], "count": len(rows)}


async def get_deferred_revenue(
    db_path: str,
    session_id: str,
    customer_id: str = "",
    contract_id: str = "",
    **kwargs,
) -> dict:
    # Mock deferred revenue schedule
    schedule = [
        {"period": "2026-03", "amount": 5000.0, "recognized": 0.0, "deferred": 5000.0},
        {"period": "2026-04", "amount": 5000.0, "recognized": 0.0, "deferred": 5000.0},
        {"period": "2026-05", "amount": 5000.0, "recognized": 0.0, "deferred": 5000.0},
        {"period": "2026-06", "amount": 5000.0, "recognized": 0.0, "deferred": 5000.0},
    ]
    return {
        "customer_id": customer_id,
        "contract_id": contract_id,
        "total_deferred": sum(s["deferred"] for s in schedule),
        "schedule": schedule,
        "currency": "USD",
    }


async def get_depreciation(
    db_path: str,
    session_id: str,
    asset_id: str = "",
    asset_class: str = "",
    fiscal_year: str = "",
    **kwargs,
) -> dict:
    year = fiscal_year or "2026"
    # Mock depreciation schedule
    schedule = [
        {"month": f"{year}-01", "depreciation": 1500.0, "book_value": 48500.0},
        {"month": f"{year}-02", "depreciation": 1500.0, "book_value": 47000.0},
        {"month": f"{year}-03", "depreciation": 1500.0, "book_value": 45500.0},
        {"month": f"{year}-04", "depreciation": 1500.0, "book_value": 44000.0},
        {"month": f"{year}-05", "depreciation": 1500.0, "book_value": 42500.0},
        {"month": f"{year}-06", "depreciation": 1500.0, "book_value": 41000.0},
        {"month": f"{year}-07", "depreciation": 1500.0, "book_value": 39500.0},
        {"month": f"{year}-08", "depreciation": 1500.0, "book_value": 38000.0},
        {"month": f"{year}-09", "depreciation": 1500.0, "book_value": 36500.0},
        {"month": f"{year}-10", "depreciation": 1500.0, "book_value": 35000.0},
        {"month": f"{year}-11", "depreciation": 1500.0, "book_value": 33500.0},
        {"month": f"{year}-12", "depreciation": 1500.0, "book_value": 32000.0},
    ]
    return {
        "asset_id": asset_id,
        "asset_class": asset_class or "equipment",
        "fiscal_year": year,
        "method": "straight_line",
        "annual_depreciation": 18000.0,
        "schedule": schedule,
        "currency": "USD",
    }


async def run_close(
    period: str,
    db_path: str,
    session_id: str,
    dry_run: bool = False,
    **kwargs,
) -> dict:
    # Simulate month-end close steps
    steps = [
        {"step": "validate_open_items", "status": "passed", "items_reviewed": 42},
        {"step": "reconcile_sub_ledgers", "status": "passed", "accounts_reconciled": 18},
        {"step": "post_accruals", "status": "passed", "entries_posted": 7},
        {"step": "calculate_depreciation", "status": "passed", "assets_processed": 31},
        {"step": "recognize_deferred_revenue", "status": "passed", "contracts_processed": 15},
        {"step": "post_fx_adjustments", "status": "passed", "currencies_processed": 3},
        {"step": "lock_period", "status": "passed" if not dry_run else "skipped"},
    ]
    if not dry_run:
        async with aiosqlite.connect(db_path) as db:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO close_history (period, closed_at, status) VALUES (?, datetime('now'), 'closed')",
                    [period],
                )
                await db.commit()
            except Exception:
                pass
    return {
        "success": True,
        "period": period,
        "dry_run": dry_run,
        "steps": steps,
        "status": "validated" if dry_run else "closed",
    }


async def post_fx_variance(
    period: str,
    from_currency: str,
    to_currency: str,
    variance_amount: float,
    db_path: str,
    session_id: str,
    gl_account: str = "5900",
    **kwargs,
) -> dict:
    import uuid as _uuid
    entry_id = f"JE-FX-{_uuid.uuid4().hex[:8].upper()}"
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                """
                INSERT INTO transactions
                    (id, date, description, amount, debit_account, credit_account, currency, type)
                VALUES (?, date('now'), ?, ?, ?, ?, ?, 'fx_variance')
                """,
                [
                    entry_id,
                    f"FX variance {from_currency}/{to_currency} for {period}",
                    abs(variance_amount),
                    gl_account if variance_amount < 0 else "1200",
                    gl_account if variance_amount >= 0 else "1200",
                    to_currency,
                ],
            )
            await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "entry_id": entry_id,
        "period": period,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "variance_amount": variance_amount,
        "gl_account": gl_account,
        "type": "gain" if variance_amount > 0 else "loss",
    }
