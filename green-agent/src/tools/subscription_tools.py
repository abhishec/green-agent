from __future__ import annotations

import aiosqlite
from typing import Any

# Mock subscription fixture data
_SUBSCRIPTION_FIXTURE: dict[str, dict[str, Any]] = {
    "SUB-001": {
        "id": "SUB-001",
        "customer_id": "CUST-001",
        "plan_id": "PLAN-STARTER",
        "status": "active",
        "billing_cycle": "monthly",
        "seats": 5,
        "features": ["analytics", "reporting", "api_access"],
        "created_at": "2024-01-15",
        "next_billing_date": "2026-03-15",
        "monthly_cost": 99.0,
    },
    "SUB-002": {
        "id": "SUB-002",
        "customer_id": "CUST-002",
        "plan_id": "PLAN-PRO",
        "status": "active",
        "billing_cycle": "annual",
        "seats": 25,
        "features": ["analytics", "reporting", "api_access", "sso", "custom_roles"],
        "created_at": "2023-06-01",
        "next_billing_date": "2026-06-01",
        "monthly_cost": 399.0,
    },
    "SUB-003": {
        "id": "SUB-003",
        "customer_id": "CUST-003",
        "plan_id": "PLAN-ENTERPRISE",
        "status": "active",
        "billing_cycle": "annual",
        "seats": 100,
        "features": ["analytics", "reporting", "api_access", "sso", "custom_roles", "dedicated_support", "sla_99_9"],
        "created_at": "2022-09-01",
        "next_billing_date": "2026-09-01",
        "monthly_cost": 1299.0,
    },
}

_PLAN_FIXTURE: dict[str, dict[str, Any]] = {
    "PLAN-STARTER": {
        "id": "PLAN-STARTER",
        "name": "Starter",
        "monthly_cost": 99.0,
        "annual_cost": 990.0,
        "max_seats": 10,
        "features": ["analytics", "reporting", "api_access"],
    },
    "PLAN-PRO": {
        "id": "PLAN-PRO",
        "name": "Pro",
        "monthly_cost": 399.0,
        "annual_cost": 3990.0,
        "max_seats": 50,
        "features": ["analytics", "reporting", "api_access", "sso", "custom_roles"],
    },
    "PLAN-ENTERPRISE": {
        "id": "PLAN-ENTERPRISE",
        "name": "Enterprise",
        "monthly_cost": 1299.0,
        "annual_cost": 12990.0,
        "max_seats": -1,
        "features": ["analytics", "reporting", "api_access", "sso", "custom_roles", "dedicated_support", "sla_99_9"],
    },
}

# 5 conflicting items per spec
_CONFLICT_ITEMS = [
    {"item": "sso", "conflict": "SSO is not available on Starter plan"},
    {"item": "custom_roles", "conflict": "Custom roles require Pro plan or higher"},
    {"item": "dedicated_support", "conflict": "Dedicated support is Enterprise only"},
    {"item": "sla_99_9", "conflict": "99.9% SLA guarantee is Enterprise only"},
    {"item": "advanced_audit_logs", "conflict": "Advanced audit logs not included in current plan"},
]

TOOL_DESCRIPTORS = [
    {
        "name": "get_subscription",
        "description": "Retrieve a subscription by ID",
        "input_schema": {
            "type": "object",
            "properties": {"subscription_id": {"type": "string", "description": "The subscription ID"}},
            "required": ["subscription_id"],
        },
    },
    {
        "name": "get_plan",
        "description": "Retrieve a subscription plan by ID",
        "input_schema": {
            "type": "object",
            "properties": {"plan_id": {"type": "string", "description": "The plan ID"}},
            "required": ["plan_id"],
        },
    },
    {
        "name": "detect_conflicts",
        "description": "Detect feature or plan conflicts for a subscription migration",
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string", "description": "The current subscription ID"},
                "target_plan_id": {"type": "string", "description": "The target plan to migrate to"},
            },
            "required": ["subscription_id", "target_plan_id"],
        },
    },
    {
        "name": "export_data",
        "description": "Export subscription and usage data for a customer",
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string", "description": "The subscription ID"},
                "format": {"type": "string", "description": "Export format: 'csv', 'json', 'xlsx'"},
                "include_usage": {"type": "boolean", "description": "Whether to include usage data"},
            },
            "required": ["subscription_id"],
        },
    },
    {
        "name": "migrate_subscription",
        "description": "Migrate a subscription to a different plan",
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string", "description": "The subscription ID"},
                "target_plan_id": {"type": "string", "description": "The target plan ID"},
                "effective_date": {"type": "string", "description": "When the migration takes effect (YYYY-MM-DD)"},
                "prorate": {"type": "boolean", "description": "Whether to prorate the billing"},
            },
            "required": ["subscription_id", "target_plan_id"],
        },
    },
]


async def get_subscription(subscription_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute(
                "SELECT * FROM subscriptions WHERE id = ?", [subscription_id]
            ) as cur:
                row = await cur.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
    fixture = _SUBSCRIPTION_FIXTURE.get(subscription_id)
    if fixture:
        return fixture
    return {"error": f"Subscription {subscription_id} not found"}


async def get_plan(plan_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute("SELECT * FROM plans WHERE id = ?", [plan_id]) as cur:
                row = await cur.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
    fixture = _PLAN_FIXTURE.get(plan_id)
    if fixture:
        return fixture
    return {"error": f"Plan {plan_id} not found"}


async def detect_conflicts(
    subscription_id: str,
    target_plan_id: str,
    db_path: str,
    session_id: str,
    **kwargs,
) -> dict:
    sub = await get_subscription(subscription_id, db_path, session_id)
    if "error" in sub:
        return sub
    target_plan = await get_plan(target_plan_id, db_path, session_id)
    if "error" in target_plan:
        return target_plan

    current_features: list[str] = sub.get("features") or []
    target_features: list[str] = target_plan.get("features") or []

    # Features in current subscription but not in target plan
    losing_features = [f for f in current_features if f not in target_features]

    # Return up to 5 conflict items per spec
    conflicts = [
        item for item in _CONFLICT_ITEMS
        if item["item"] in losing_features or item["item"] not in target_features
    ][:5]

    return {
        "subscription_id": subscription_id,
        "current_plan_id": sub.get("plan_id"),
        "target_plan_id": target_plan_id,
        "has_conflicts": len(conflicts) > 0,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "features_losing": losing_features,
    }


async def export_data(
    subscription_id: str,
    db_path: str,
    session_id: str,
    format: str = "json",
    include_usage: bool = True,
    **kwargs,
) -> dict:
    sub = await get_subscription(subscription_id, db_path, session_id)
    return {
        "success": True,
        "subscription_id": subscription_id,
        "format": format,
        "include_usage": include_usage,
        "record_count": 1,
        "export_url": f"https://exports.example.com/{subscription_id}.{format}",
        "expires_at": "2026-03-06T00:00:00Z",
        "data_summary": {
            "subscription": sub,
            "usage_included": include_usage,
        },
    }


async def migrate_subscription(
    subscription_id: str,
    target_plan_id: str,
    db_path: str,
    session_id: str,
    effective_date: str = "",
    prorate: bool = True,
    **kwargs,
) -> dict:
    target_plan = await get_plan(target_plan_id, db_path, session_id)
    if "error" in target_plan:
        return target_plan

    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                """
                UPDATE subscriptions
                SET plan_id = ?, monthly_cost = ?, migration_date = ?
                WHERE id = ?
                """,
                [
                    target_plan_id,
                    target_plan.get("monthly_cost", 0.0),
                    effective_date or "immediate",
                    subscription_id,
                ],
            )
            await db.commit()
        except Exception:
            pass

    return {
        "success": True,
        "subscription_id": subscription_id,
        "previous_plan_id": None,
        "new_plan_id": target_plan_id,
        "effective_date": effective_date or "immediate",
        "prorate": prorate,
        "new_monthly_cost": target_plan.get("monthly_cost", 0.0),
        "status": "migrated",
    }
