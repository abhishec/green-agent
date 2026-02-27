from __future__ import annotations

import aiosqlite
from typing import Any

# Mock AR aging data with 6 customers using different treatment paths
_AR_AGING_FIXTURE: list[dict[str, Any]] = [
    {
        "customer_id": "CUST-AR-001",
        "customer_name": "Acme Corp",
        "invoice_id": "INV-1001",
        "amount_due": 12500.0,
        "days_overdue": 15,
        "aging_bucket": "1-30",
        "treatment": "reminder",
        "contact_email": "ar@acme.com",
        "contact_phone": "+1-555-0101",
    },
    {
        "customer_id": "CUST-AR-002",
        "customer_name": "Bright Solutions",
        "invoice_id": "INV-1002",
        "amount_due": 8750.0,
        "days_overdue": 45,
        "aging_bucket": "31-60",
        "treatment": "reminder",
        "contact_email": "billing@bright.com",
        "contact_phone": "+1-555-0102",
    },
    {
        "customer_id": "CUST-AR-003",
        "customer_name": "CoreTech Ltd",
        "invoice_id": "INV-1003",
        "amount_due": 32000.0,
        "days_overdue": 75,
        "aging_bucket": "61-90",
        "treatment": "collections",
        "contact_email": "finance@coretech.com",
        "contact_phone": "+1-555-0103",
    },
    {
        "customer_id": "CUST-AR-004",
        "customer_name": "Delta Ventures",
        "invoice_id": "INV-1004",
        "amount_due": 5200.0,
        "days_overdue": 95,
        "aging_bucket": "91-120",
        "treatment": "payment_plan",
        "contact_email": "accounts@delta.com",
        "contact_phone": "+1-555-0104",
    },
    {
        "customer_id": "CUST-AR-005",
        "customer_name": "Eagle Systems",
        "invoice_id": "INV-1005",
        "amount_due": 1800.0,
        "days_overdue": 145,
        "aging_bucket": "121+",
        "treatment": "write_off",
        "contact_email": "admin@eagle.com",
        "contact_phone": "+1-555-0105",
    },
    {
        "customer_id": "CUST-AR-006",
        "customer_name": "Falcon Media",
        "invoice_id": "INV-1006",
        "amount_due": 67000.0,
        "days_overdue": 38,
        "aging_bucket": "31-60",
        "treatment": "payment_plan",
        "contact_email": "billing@falcon.com",
        "contact_phone": "+1-555-0106",
    },
]

TOOL_DESCRIPTORS = [
    {
        "name": "get_aging_report",
        "description": "Get the accounts receivable aging report",
        "input_schema": {
            "type": "object",
            "properties": {
                "bucket": {"type": "string", "description": "Filter by aging bucket: '1-30', '31-60', '61-90', '91-120', '121+'"},
                "min_amount": {"type": "number", "description": "Minimum amount due filter"},
            },
            "required": [],
        },
    },
    {
        "name": "get_customer",
        "description": "Get customer details for AR purposes",
        "input_schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string", "description": "The customer ID"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "send_reminder",
        "description": "Send a payment reminder to a customer",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "The customer ID"},
                "invoice_id": {"type": "string", "description": "The invoice ID"},
                "message": {"type": "string", "description": "Custom reminder message"},
                "channel": {"type": "string", "description": "Channel: 'email', 'phone', 'both'"},
            },
            "required": ["customer_id", "invoice_id"],
        },
    },
    {
        "name": "escalate_collections",
        "description": "Escalate an overdue account to collections",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "The customer ID"},
                "invoice_id": {"type": "string", "description": "The invoice ID"},
                "collections_agency": {"type": "string", "description": "Collections agency to assign to (optional)"},
                "notes": {"type": "string", "description": "Notes for the collections team"},
            },
            "required": ["customer_id", "invoice_id"],
        },
    },
    {
        "name": "write_off",
        "description": "Write off an uncollectible invoice",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "The invoice ID to write off"},
                "reason": {"type": "string", "description": "Reason for write-off"},
                "gl_account": {"type": "string", "description": "GL bad debt account code"},
            },
            "required": ["invoice_id", "reason"],
        },
    },
    {
        "name": "payment_plan",
        "description": "Create a payment plan with installments for an overdue invoice",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "The customer ID"},
                "invoice_id": {"type": "string", "description": "The invoice ID"},
                "installments": {"type": "integer", "description": "Number of installments (e.g. 3, 6, 12)"},
                "first_payment_date": {"type": "string", "description": "Date of first payment (YYYY-MM-DD)"},
                "discount_pct": {"type": "number", "description": "Optional discount percentage for early settlement"},
            },
            "required": ["customer_id", "invoice_id", "installments"],
        },
    },
]


async def get_aging_report(
    db_path: str,
    session_id: str,
    bucket: str = "",
    min_amount: float = 0.0,
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            query = "SELECT * FROM ar_aging WHERE 1=1"
            args: list[Any] = []
            if bucket:
                query += " AND aging_bucket = ?"; args.append(bucket)
            if min_amount:
                query += " AND amount_due >= ?"; args.append(min_amount)
            async with db.execute(query, args) as cur:
                rows = await cur.fetchall()
            if rows:
                items = [dict(r) for r in rows]
                return {
                    "aging_report": items,
                    "total_overdue": sum(i.get("amount_due", 0) for i in items),
                    "count": len(items),
                }
        except Exception:
            pass
    # Use fixture
    items = list(_AR_AGING_FIXTURE)
    if bucket:
        items = [i for i in items if i.get("aging_bucket") == bucket]
    if min_amount:
        items = [i for i in items if i.get("amount_due", 0) >= min_amount]
    return {
        "aging_report": items,
        "total_overdue": sum(i.get("amount_due", 0) for i in items),
        "count": len(items),
        "source": "fixture",
    }


async def get_customer(customer_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM customers WHERE id = ?", [customer_id]) as cur:
            row = await cur.fetchone()
    if row:
        return dict(row)
    # Fallback to fixture
    for entry in _AR_AGING_FIXTURE:
        if entry["customer_id"] == customer_id:
            return {
                "id": customer_id,
                "name": entry["customer_name"],
                "contact_email": entry.get("contact_email", ""),
                "contact_phone": entry.get("contact_phone", ""),
                "source": "fixture",
            }
    return {"error": f"Customer {customer_id} not found"}


async def send_reminder(
    customer_id: str,
    invoice_id: str,
    db_path: str,
    session_id: str,
    message: str = "",
    channel: str = "email",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                """
                INSERT INTO ar_reminders (customer_id, invoice_id, channel, message, sent_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                [customer_id, invoice_id, channel, message],
            )
            await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "customer_id": customer_id,
        "invoice_id": invoice_id,
        "channel": channel,
        "message": message or f"Payment reminder for invoice {invoice_id}",
        "status": "sent",
    }


async def escalate_collections(
    customer_id: str,
    invoice_id: str,
    db_path: str,
    session_id: str,
    collections_agency: str = "",
    notes: str = "",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                """
                UPDATE invoices
                SET status = 'in_collections', collections_agency = ?, collections_notes = ?, escalated_at = datetime('now')
                WHERE id = ?
                """,
                [collections_agency, notes, invoice_id],
            )
            await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "customer_id": customer_id,
        "invoice_id": invoice_id,
        "status": "in_collections",
        "collections_agency": collections_agency or "internal",
        "notes": notes,
    }


async def write_off(
    invoice_id: str,
    reason: str,
    db_path: str,
    session_id: str,
    gl_account: str = "6100",
    **kwargs,
) -> dict:
    import uuid as _uuid
    entry_id = f"WO-{_uuid.uuid4().hex[:8].upper()}"
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                "UPDATE invoices SET status = 'written_off', write_off_reason = ?, written_off_at = datetime('now') WHERE id = ?",
                [reason, invoice_id],
            )
            await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "invoice_id": invoice_id,
        "write_off_id": entry_id,
        "status": "written_off",
        "reason": reason,
        "gl_account": gl_account,
        "gl_entry": f"DR Bad Debt ({gl_account}) / CR AR ({invoice_id})",
    }


async def payment_plan(
    customer_id: str,
    invoice_id: str,
    installments: int,
    db_path: str,
    session_id: str,
    first_payment_date: str = "",
    discount_pct: float = 0.0,
    **kwargs,
) -> dict:
    import uuid as _uuid
    plan_id = f"PP-{_uuid.uuid4().hex[:8].upper()}"

    # Find invoice amount
    invoice_amount = 0.0
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute("SELECT amount FROM invoices WHERE id = ?", [invoice_id]) as cur:
                row = await cur.fetchone()
            if row:
                invoice_amount = float(row["amount"] or 0.0)
        except Exception:
            pass

    if not invoice_amount:
        # Fallback to fixture
        for entry in _AR_AGING_FIXTURE:
            if entry["invoice_id"] == invoice_id:
                invoice_amount = entry["amount_due"]
                break

    discounted_total = invoice_amount * (1 - discount_pct / 100) if discount_pct else invoice_amount
    per_installment = round(discounted_total / max(1, installments), 2)

    schedule = []
    from datetime import date, timedelta
    base_date = date.today()
    if first_payment_date:
        try:
            base_date = date.fromisoformat(first_payment_date)
        except ValueError:
            pass
    for i in range(installments):
        due = base_date + timedelta(days=30 * i)
        schedule.append({"installment": i + 1, "due_date": due.isoformat(), "amount": per_installment})

    return {
        "success": True,
        "plan_id": plan_id,
        "customer_id": customer_id,
        "invoice_id": invoice_id,
        "original_amount": invoice_amount,
        "discount_pct": discount_pct,
        "discounted_total": discounted_total,
        "installments": installments,
        "per_installment": per_installment,
        "schedule": schedule,
        "status": "active",
    }
