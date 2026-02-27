from __future__ import annotations

import aiosqlite
from typing import Any

# Historical FX rate fixture: (base_currency, target_currency) -> rate
_FX_RATE_FIXTURE: dict[tuple[str, str], float] = {
    ("USD", "EUR"): 0.92,
    ("USD", "GBP"): 0.79,
    ("USD", "JPY"): 149.50,
    ("USD", "CAD"): 1.36,
    ("USD", "AUD"): 1.53,
    ("EUR", "USD"): 1.09,
    ("EUR", "GBP"): 0.86,
    ("GBP", "USD"): 1.27,
    ("GBP", "EUR"): 1.17,
    ("JPY", "USD"): 0.0067,
    ("CAD", "USD"): 0.74,
    ("AUD", "USD"): 0.65,
}

TOOL_DESCRIPTORS = [
    {
        "name": "get_invoice",
        "description": "Retrieve an invoice by ID",
        "input_schema": {
            "type": "object",
            "properties": {"invoice_id": {"type": "string", "description": "The invoice ID"}},
            "required": ["invoice_id"],
        },
    },
    {
        "name": "get_vendor",
        "description": "Retrieve vendor details by vendor ID",
        "input_schema": {
            "type": "object",
            "properties": {"vendor_id": {"type": "string", "description": "The vendor ID"}},
            "required": ["vendor_id"],
        },
    },
    {
        "name": "get_fx_rate",
        "description": "Get the historical FX exchange rate between two currencies",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_currency": {"type": "string", "description": "Source currency code (e.g. USD)"},
                "to_currency": {"type": "string", "description": "Target currency code (e.g. EUR)"},
                "date": {"type": "string", "description": "Date for historical rate (YYYY-MM-DD). Uses latest if omitted."},
            },
            "required": ["from_currency", "to_currency"],
        },
    },
    {
        "name": "detect_duplicate",
        "description": "Check for duplicate invoices from the same vendor with the same amount within 30 days",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string", "description": "The vendor ID"},
                "amount": {"type": "number", "description": "Invoice amount to check"},
                "invoice_date": {"type": "string", "description": "Invoice date (YYYY-MM-DD)"},
                "exclude_invoice_id": {"type": "string", "description": "Invoice ID to exclude from duplicate check (the current invoice)"},
            },
            "required": ["vendor_id", "amount", "invoice_date"],
        },
    },
    {
        "name": "reconcile_invoice",
        "description": "Mark an invoice as reconciled after matching with transactions",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "The invoice ID"},
                "transaction_id": {"type": "string", "description": "Matching transaction ID"},
                "reconciled_amount": {"type": "number", "description": "The reconciled amount"},
            },
            "required": ["invoice_id", "transaction_id", "reconciled_amount"],
        },
    },
    {
        "name": "post_to_gl",
        "description": "Post an invoice to the General Ledger",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "The invoice ID"},
                "gl_account": {"type": "string", "description": "GL account code"},
                "cost_center": {"type": "string", "description": "Cost center code"},
                "posting_date": {"type": "string", "description": "GL posting date (YYYY-MM-DD)"},
            },
            "required": ["invoice_id", "gl_account"],
        },
    },
]


async def get_invoice(invoice_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM invoices WHERE id = ?", [invoice_id]) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Invoice {invoice_id} not found"}
    return dict(row)


async def get_vendor(vendor_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute("SELECT * FROM vendors WHERE id = ?", [vendor_id]) as cur:
                row = await cur.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
    return {"error": f"Vendor {vendor_id} not found"}


async def get_fx_rate(
    from_currency: str,
    to_currency: str,
    db_path: str,
    session_id: str,
    date: str = "",
    **kwargs,
) -> dict:
    from_upper = from_currency.upper()
    to_upper = to_currency.upper()
    if from_upper == to_upper:
        return {"from_currency": from_upper, "to_currency": to_upper, "rate": 1.0, "date": date or "current"}
    rate = _FX_RATE_FIXTURE.get((from_upper, to_upper))
    if rate is None:
        # Try inverse
        inverse = _FX_RATE_FIXTURE.get((to_upper, from_upper))
        if inverse:
            rate = round(1.0 / inverse, 6)
    if rate is None:
        return {"error": f"FX rate not found for {from_upper}/{to_upper}"}
    return {
        "from_currency": from_upper,
        "to_currency": to_upper,
        "rate": rate,
        "date": date or "current",
        "source": "fixture",
    }


async def detect_duplicate(
    vendor_id: str,
    amount: float,
    invoice_date: str,
    db_path: str,
    session_id: str,
    exclude_invoice_id: str = "",
    **kwargs,
) -> dict:
    query = """
        SELECT id, invoice_date, amount, status
        FROM invoices
        WHERE vendor_id = ?
          AND ABS(amount - ?) < 0.01
          AND invoice_date BETWEEN date(?, '-30 days') AND date(?, '+30 days')
    """
    args: list[Any] = [vendor_id, amount, invoice_date, invoice_date]
    if exclude_invoice_id:
        query += " AND id != ?"
        args.append(exclude_invoice_id)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, args) as cur:
            rows = await cur.fetchall()
    duplicates = [dict(r) for r in rows]
    return {
        "is_duplicate": len(duplicates) > 0,
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
        "vendor_id": vendor_id,
        "amount": amount,
        "invoice_date": invoice_date,
    }


async def reconcile_invoice(
    invoice_id: str,
    transaction_id: str,
    reconciled_amount: float,
    db_path: str,
    session_id: str,
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE invoices
            SET status = 'reconciled', transaction_id = ?, reconciled_amount = ?, reconciled_at = datetime('now')
            WHERE id = ?
            """,
            [transaction_id, reconciled_amount, invoice_id],
        )
        await db.commit()
    return {
        "success": True,
        "invoice_id": invoice_id,
        "transaction_id": transaction_id,
        "reconciled_amount": reconciled_amount,
        "status": "reconciled",
    }


async def post_to_gl(
    invoice_id: str,
    gl_account: str,
    db_path: str,
    session_id: str,
    cost_center: str = "",
    posting_date: str = "",
    **kwargs,
) -> dict:
    # In a real system this would call an ERP API; here we record the posting locally
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                """
                UPDATE invoices
                SET gl_account = ?, cost_center = ?, gl_posted_at = datetime('now'), status = 'posted'
                WHERE id = ?
                """,
                [gl_account, cost_center, invoice_id],
            )
            await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "invoice_id": invoice_id,
        "gl_account": gl_account,
        "cost_center": cost_center,
        "posting_date": posting_date or "today",
        "status": "posted",
        "gl_reference": f"GL-{invoice_id}-{gl_account}",
    }
