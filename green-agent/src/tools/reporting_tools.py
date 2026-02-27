from __future__ import annotations

import aiosqlite
from typing import Any

# QBR fixture data: 3 deck versions
_DECK_VERSIONS: list[dict[str, Any]] = [
    {
        "version": "v1",
        "created_at": "2026-02-10T09:00:00Z",
        "author": "alice@example.com",
        "slides": 18,
        "status": "draft",
        "changes": "Initial draft with Q1 revenue data",
    },
    {
        "version": "v2",
        "created_at": "2026-02-18T14:30:00Z",
        "author": "bob@example.com",
        "slides": 22,
        "status": "review",
        "changes": "Added NPS section, updated ARR chart, fixed slide 7 typo",
    },
    {
        "version": "v3",
        "created_at": "2026-02-25T11:00:00Z",
        "author": "carol@example.com",
        "slides": 24,
        "status": "final",
        "changes": "CEO feedback incorporated, added competitive landscape slide",
    },
]

# Revenue sources for reconciliation
_REVENUE_DATA: list[dict[str, Any]] = [
    {"source": "CRM (Salesforce)", "q1_revenue": 1_250_000.0, "q4_revenue": 1_100_000.0, "currency": "USD"},
    {"source": "Finance System (NetSuite)", "q1_revenue": 1_247_500.0, "q4_revenue": 1_098_200.0, "currency": "USD"},
    {"source": "Stripe (Payments)", "q1_revenue": 1_249_000.0, "q4_revenue": 1_099_800.0, "currency": "USD"},
    {"source": "Data Warehouse (Snowflake)", "q1_revenue": 1_248_200.0, "q4_revenue": 1_099_100.0, "currency": "USD"},
]

# NPS scores by segment
_NPS_DATA: list[dict[str, Any]] = [
    {"segment": "Enterprise", "nps_score": 68, "promoters": 45, "passives": 30, "detractors": 25, "responses": 100},
    {"segment": "Mid-Market", "nps_score": 52, "promoters": 38, "passives": 36, "detractors": 26, "responses": 150},
    {"segment": "SMB", "nps_score": 71, "promoters": 55, "passives": 26, "detractors": 19, "responses": 200},
    {"segment": "Overall", "nps_score": 63, "promoters": 46, "passives": 31, "detractors": 23, "responses": 450},
]

TOOL_DESCRIPTORS = [
    {
        "name": "get_deck_versions",
        "description": "Get all versions of the QBR deck",
        "input_schema": {
            "type": "object",
            "properties": {
                "status_filter": {"type": "string", "description": "Filter by status: 'draft', 'review', 'final'"},
            },
            "required": [],
        },
    },
    {
        "name": "get_revenue_data",
        "description": "Get revenue data from various sources for QBR reconciliation",
        "input_schema": {
            "type": "object",
            "properties": {
                "quarter": {"type": "string", "description": "Quarter to get data for (e.g. 'Q1', 'Q4')"},
                "source": {"type": "string", "description": "Specific source to filter by"},
            },
            "required": [],
        },
    },
    {
        "name": "get_nps",
        "description": "Get NPS (Net Promoter Score) data by customer segment",
        "input_schema": {
            "type": "object",
            "properties": {
                "segment": {"type": "string", "description": "Customer segment: 'Enterprise', 'Mid-Market', 'SMB', 'Overall'"},
            },
            "required": [],
        },
    },
    {
        "name": "reconcile_revenue",
        "description": "Reconcile revenue figures across multiple data sources and identify discrepancies",
        "input_schema": {
            "type": "object",
            "properties": {
                "quarter": {"type": "string", "description": "Quarter to reconcile (e.g. 'Q1')"},
                "tolerance_pct": {"type": "number", "description": "Acceptable variance percentage (default 0.5%)"},
            },
            "required": ["quarter"],
        },
    },
    {
        "name": "generate_qbr_summary",
        "description": "Generate an aggregated QBR summary combining revenue, NPS, and deck metadata",
        "input_schema": {
            "type": "object",
            "properties": {
                "quarter": {"type": "string", "description": "Quarter for the QBR"},
                "include_sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Sections to include: 'revenue', 'nps', 'product', 'support'",
                },
            },
            "required": ["quarter"],
        },
    },
]


async def get_deck_versions(
    db_path: str,
    session_id: str,
    status_filter: str = "",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            query = "SELECT * FROM deck_versions WHERE 1=1"
            args: list[Any] = []
            if status_filter:
                query += " AND status = ?"; args.append(status_filter)
            query += " ORDER BY created_at DESC"
            async with db.execute(query, args) as cur:
                rows = await cur.fetchall()
            if rows:
                return {"versions": [dict(r) for r in rows], "count": len(rows)}
        except Exception:
            pass
    versions = list(_DECK_VERSIONS)
    if status_filter:
        versions = [v for v in versions if v.get("status") == status_filter]
    return {
        "versions": versions,
        "count": len(versions),
        "latest_version": versions[-1]["version"] if versions else None,
        "source": "fixture",
    }


async def get_revenue_data(
    db_path: str,
    session_id: str,
    quarter: str = "",
    source: str = "",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute("SELECT * FROM revenue_sources") as cur:
                rows = await cur.fetchall()
            if rows:
                data = [dict(r) for r in rows]
                if source:
                    data = [d for d in data if source.lower() in d.get("source", "").lower()]
                return {"revenue_data": data, "count": len(data)}
        except Exception:
            pass
    data = list(_REVENUE_DATA)
    if source:
        data = [d for d in data if source.lower() in d.get("source", "").lower()]
    # Pick the right quarter column
    qtr = quarter.upper() if quarter else "Q1"
    revenue_key = "q1_revenue" if "Q1" in qtr else "q4_revenue"
    for d in data:
        d["quarter"] = qtr
        d["revenue"] = d.get(revenue_key, 0.0)
    return {"revenue_data": data, "quarter": qtr, "count": len(data), "source": "fixture"}


async def get_nps(
    db_path: str,
    session_id: str,
    segment: str = "",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            query = "SELECT * FROM nps_data WHERE 1=1"
            args: list[Any] = []
            if segment:
                query += " AND segment = ?"; args.append(segment)
            async with db.execute(query, args) as cur:
                rows = await cur.fetchall()
            if rows:
                return {"nps_data": [dict(r) for r in rows]}
        except Exception:
            pass
    data = list(_NPS_DATA)
    if segment:
        data = [d for d in data if d.get("segment", "").lower() == segment.lower()]
    return {"nps_data": data, "count": len(data), "source": "fixture"}


async def reconcile_revenue(
    quarter: str,
    db_path: str,
    session_id: str,
    tolerance_pct: float = 0.5,
    **kwargs,
) -> dict:
    revenue_result = await get_revenue_data(db_path, session_id, quarter=quarter)
    data = revenue_result.get("revenue_data", [])
    if not data:
        return {"error": "No revenue data found for reconciliation"}

    amounts = [d.get("revenue", d.get("q1_revenue", 0.0)) for d in data]
    avg = sum(amounts) / len(amounts) if amounts else 0.0
    max_variance = max(abs(a - avg) / avg * 100 if avg else 0 for a in amounts) if amounts else 0.0
    is_reconciled = max_variance <= tolerance_pct

    discrepancies = []
    for d in data:
        amt = d.get("revenue", d.get("q1_revenue", 0.0))
        variance = abs(amt - avg) / avg * 100 if avg else 0
        if variance > tolerance_pct:
            discrepancies.append({
                "source": d.get("source"),
                "amount": amt,
                "variance_pct": round(variance, 4),
                "expected": round(avg, 2),
            })

    return {
        "quarter": quarter,
        "is_reconciled": is_reconciled,
        "average_revenue": round(avg, 2),
        "max_variance_pct": round(max_variance, 4),
        "tolerance_pct": tolerance_pct,
        "discrepancies": discrepancies,
        "sources_checked": len(data),
        "status": "reconciled" if is_reconciled else "discrepancy_found",
    }


async def generate_qbr_summary(
    quarter: str,
    db_path: str,
    session_id: str,
    include_sections: list[str] | None = None,
    **kwargs,
) -> dict:
    sections = include_sections or ["revenue", "nps", "product", "support"]
    summary: dict[str, Any] = {"quarter": quarter, "sections": {}}

    if "revenue" in sections:
        revenue_result = await get_revenue_data(db_path, session_id, quarter=quarter)
        reconcile_result = await reconcile_revenue(quarter, db_path, session_id)
        data = revenue_result.get("revenue_data", [])
        amounts = [d.get("revenue", d.get("q1_revenue", 0.0)) for d in data]
        avg_revenue = sum(amounts) / len(amounts) if amounts else 0.0
        summary["sections"]["revenue"] = {
            "total_revenue": round(avg_revenue, 2),
            "reconciled": reconcile_result.get("is_reconciled", False),
            "sources": len(data),
        }

    if "nps" in sections:
        nps_result = await get_nps(db_path, session_id)
        nps_data = nps_result.get("nps_data", [])
        overall = next((n for n in nps_data if n.get("segment") == "Overall"), None)
        summary["sections"]["nps"] = {
            "overall_nps": overall.get("nps_score") if overall else None,
            "segments": [{"segment": n["segment"], "nps": n["nps_score"]} for n in nps_data],
        }

    if "product" in sections:
        deck_result = await get_deck_versions(db_path, session_id, status_filter="final")
        summary["sections"]["product"] = {
            "deck_version": deck_result.get("latest_version"),
            "total_versions": len(_DECK_VERSIONS),
        }

    if "support" in sections:
        summary["sections"]["support"] = {
            "tickets_opened": 142,
            "tickets_closed": 138,
            "avg_resolution_hours": 4.2,
            "csat_score": 4.6,
        }

    return {"success": True, "qbr_summary": summary}
