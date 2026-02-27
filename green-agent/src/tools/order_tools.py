from __future__ import annotations

import aiosqlite
from typing import Any

TOOL_DESCRIPTORS = [
    {
        "name": "get_order",
        "description": "Retrieve order details by order ID",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "The order ID to look up"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "get_order_items",
        "description": "Get all items in an order",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "The order ID"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "get_product_variants",
        "description": "Get available variants for a product, optionally filtered by color and size",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product ID"},
                "color": {"type": "string", "description": "Filter by color (optional)"},
                "size": {"type": "string", "description": "Filter by size (optional)"},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "get_gift_card_balance",
        "description": "Get gift card balance",
        "input_schema": {
            "type": "object",
            "properties": {"gift_card_id": {"type": "string", "description": "The gift card ID"}},
            "required": ["gift_card_id"],
        },
    },
    {
        "name": "modify_order_items",
        "description": "Modify multiple order items in a single atomic call. Each modification can update variant_id, quantity, unit_price, or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID"},
                "modifications": {
                    "type": "array",
                    "description": "List of modifications to apply",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string"},
                            "variant_id": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "unit_price": {"type": "number"},
                            "status": {"type": "string"},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            "required": ["order_id", "modifications"],
        },
    },
    {
        "name": "cancel_order_item",
        "description": "Cancel a specific order item and recalculate order total",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID"},
                "item_id": {"type": "string", "description": "The item ID to cancel"},
            },
            "required": ["order_id", "item_id"],
        },
    },
    {
        "name": "process_payment_adjustment",
        "description": "Process refund or charge adjustment to gift card or payment method",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID"},
                "amount": {"type": "number", "description": "Amount to adjust (positive = refund, negative = charge)"},
                "target_id": {"type": "string", "description": "ID of the payment target (gift card ID or payment method ID)"},
                "target_type": {"type": "string", "description": "Type of target: 'gift_card' or 'payment_method'"},
            },
            "required": ["order_id", "amount", "target_id", "target_type"],
        },
    },
    {
        "name": "confirm_with_user",
        "description": "Request user confirmation before performing an irreversible action",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The confirmation message to display to the user"},
                "action_summary": {"type": "string", "description": "Brief summary of the action about to be taken"},
            },
            "required": ["message"],
        },
    },
]


async def get_order(order_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id = ?", [order_id]) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Order {order_id} not found"}
    return dict(row)


async def get_order_items(order_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT oi.*, p.name as product_name
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
            """,
            [order_id],
        ) as cur:
            rows = await cur.fetchall()
    return {"items": [dict(r) for r in rows]}


async def get_product_variants(
    product_id: str,
    db_path: str,
    session_id: str,
    color: str = None,
    size: str = None,
    **kwargs,
) -> dict:
    query = "SELECT * FROM product_variants WHERE product_id = ?"
    args: list[Any] = [product_id]
    if color:
        query += " AND color = ?"
        args.append(color)
    if size:
        query += " AND size = ?"
        args.append(size)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, args) as cur:
            rows = await cur.fetchall()
    return {"variants": [dict(r) for r in rows]}


async def get_gift_card_balance(gift_card_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM gift_cards WHERE id = ?", [gift_card_id]) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Gift card {gift_card_id} not found"}
    return dict(row)


async def modify_order_items(
    order_id: str,
    modifications: list,
    db_path: str,
    session_id: str,
    **kwargs,
) -> dict:
    """Single atomic call to modify multiple items.

    modifications: list of dicts with keys: item_id (required), variant_id, quantity, unit_price, status
    """
    applied = 0
    async with aiosqlite.connect(db_path) as db:
        for mod in modifications:
            item_id = mod.get("item_id")
            if not item_id:
                continue
            fields: list[str] = []
            vals: list[Any] = []
            for field in ["variant_id", "quantity", "unit_price", "status"]:
                if field in mod:
                    fields.append(f"{field} = ?")
                    vals.append(mod[field])
            if fields:
                vals.append(item_id)
                await db.execute(
                    f"UPDATE order_items SET {', '.join(fields)} WHERE id = ?",
                    vals,
                )
                applied += 1
        # Recalculate order total from active items
        async with db.execute(
            "SELECT SUM(unit_price * quantity) FROM order_items WHERE order_id = ? AND (status IS NULL OR status = 'active')",
            [order_id],
        ) as cur:
            row = await cur.fetchone()
        new_total = row[0] or 0.0
        await db.execute(
            "UPDATE orders SET total = ? WHERE id = ?",
            [new_total, order_id],
        )
        await db.commit()
    return {
        "success": True,
        "order_id": order_id,
        "new_total": new_total,
        "modifications_applied": applied,
    }


async def cancel_order_item(order_id: str, item_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE order_items SET status = 'cancelled' WHERE id = ? AND order_id = ?",
            [item_id, order_id],
        )
        async with db.execute(
            "SELECT SUM(unit_price * quantity) FROM order_items WHERE order_id = ? AND (status IS NULL OR status = 'active')",
            [order_id],
        ) as cur:
            row = await cur.fetchone()
        new_total = row[0] or 0.0
        await db.execute("UPDATE orders SET total = ? WHERE id = ?", [new_total, order_id])
        await db.commit()
    return {"success": True, "item_id": item_id, "order_id": order_id, "new_total": new_total}


async def process_payment_adjustment(
    order_id: str,
    amount: float,
    target_id: str,
    target_type: str,
    db_path: str,
    session_id: str,
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        if target_type == "gift_card":
            await db.execute(
                "UPDATE gift_cards SET balance = balance + ? WHERE id = ?",
                [amount, target_id],
            )
        # For payment_method, we log the adjustment but don't update a local balance
        await db.commit()
    return {
        "success": True,
        "order_id": order_id,
        "amount": amount,
        "target_id": target_id,
        "target_type": target_type,
        "action": "refund" if amount > 0 else "charge",
    }


async def confirm_with_user(
    message: str,
    db_path: str,
    session_id: str,
    action_summary: str = "",
    **kwargs,
) -> dict:
    """In an automated benchmark context this always returns confirmed=True.
    A real implementation would pause for human input.
    """
    return {
        "confirmed": True,
        "message": message,
        "action_summary": action_summary,
    }
