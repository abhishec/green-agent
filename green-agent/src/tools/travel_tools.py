from __future__ import annotations

import aiosqlite
from typing import Any

# Mock travel booking fixture
_BOOKING_FIXTURE: dict[str, dict[str, Any]] = {
    "BK-001": {
        "id": "BK-001",
        "employee_id": "EMP-101",
        "type": "flight",
        "airline": "Delta",
        "flight_number": "DL1042",
        "origin": "JFK",
        "destination": "SFO",
        "departure": "2026-03-10T08:00:00",
        "arrival": "2026-03-10T11:30:00",
        "seat_class": "economy",
        "cost": 450.0,
        "status": "confirmed",
        "loyalty_number": "DL-GOLD-12345",
    },
    "BK-002": {
        "id": "BK-002",
        "employee_id": "EMP-101",
        "type": "hotel",
        "hotel_name": "Marriott SFO",
        "check_in": "2026-03-10",
        "check_out": "2026-03-12",
        "room_type": "standard",
        "cost_per_night": 189.0,
        "total_cost": 378.0,
        "status": "confirmed",
    },
    "BK-003": {
        "id": "BK-003",
        "employee_id": "EMP-202",
        "type": "flight",
        "airline": "United",
        "flight_number": "UA558",
        "origin": "ORD",
        "destination": "LAX",
        "departure": "2026-03-15T14:00:00",
        "arrival": "2026-03-15T16:45:00",
        "seat_class": "business",
        "cost": 1200.0,
        "status": "confirmed",
    },
}

# Policy tier by employee level
_POLICY_TIERS: dict[str, str] = {
    "L1": "standard",
    "L2": "standard",
    "L3": "standard",
    "L4": "premium",
    "L5": "premium",
    "L6": "executive",
    "L7": "executive",
    "VP": "executive",
    "SVP": "executive",
    "C-level": "executive",
}

# Loyalty points mock
_LOYALTY_POINTS: dict[str, dict[str, Any]] = {
    "EMP-101": {"airline_miles": 45000, "hotel_points": 12000, "program": "Delta SkyMiles"},
    "EMP-202": {"airline_miles": 82000, "hotel_points": 35000, "program": "United MileagePlus"},
    "EMP-303": {"airline_miles": 10000, "hotel_points": 5000, "program": "American AAdvantage"},
}

TOOL_DESCRIPTORS = [
    {
        "name": "get_booking",
        "description": "Retrieve a travel booking by ID",
        "input_schema": {
            "type": "object",
            "properties": {"booking_id": {"type": "string", "description": "The booking ID"}},
            "required": ["booking_id"],
        },
    },
    {
        "name": "get_policy_tier",
        "description": "Get the travel policy tier for an employee based on their level",
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "The employee ID"},
                "employee_level": {"type": "string", "description": "Employee level (e.g. L3, L5, VP)"},
            },
            "required": ["employee_id"],
        },
    },
    {
        "name": "search_alternatives",
        "description": "Search for alternative flights or hotels for a given route/destination",
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_type": {"type": "string", "description": "Type: 'flight' or 'hotel'"},
                "origin": {"type": "string", "description": "Origin city or airport code (for flights)"},
                "destination": {"type": "string", "description": "Destination city or airport code"},
                "date": {"type": "string", "description": "Travel date (YYYY-MM-DD)"},
                "max_cost": {"type": "number", "description": "Maximum cost filter"},
            },
            "required": ["booking_type", "destination", "date"],
        },
    },
    {
        "name": "rebook_flight",
        "description": "Rebook an existing flight booking to a new flight",
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_id": {"type": "string", "description": "The existing booking ID"},
                "new_flight_number": {"type": "string", "description": "New flight number"},
                "new_departure": {"type": "string", "description": "New departure datetime (ISO format)"},
                "new_cost": {"type": "number", "description": "New ticket cost"},
                "reason": {"type": "string", "description": "Reason for rebooking"},
            },
            "required": ["booking_id", "new_flight_number", "new_departure"],
        },
    },
    {
        "name": "rebook_hotel",
        "description": "Rebook an existing hotel booking to new dates or property",
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_id": {"type": "string", "description": "The existing booking ID"},
                "new_hotel_name": {"type": "string", "description": "New hotel name"},
                "new_check_in": {"type": "string", "description": "New check-in date (YYYY-MM-DD)"},
                "new_check_out": {"type": "string", "description": "New check-out date (YYYY-MM-DD)"},
                "new_cost_per_night": {"type": "number", "description": "New nightly rate"},
            },
            "required": ["booking_id"],
        },
    },
    {
        "name": "get_loyalty_points",
        "description": "Get the loyalty points balance for an employee",
        "input_schema": {
            "type": "object",
            "properties": {"employee_id": {"type": "string", "description": "The employee ID"}},
            "required": ["employee_id"],
        },
    },
]


async def get_booking(booking_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute("SELECT * FROM bookings WHERE id = ?", [booking_id]) as cur:
                row = await cur.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
    fixture = _BOOKING_FIXTURE.get(booking_id)
    if fixture:
        return fixture
    return {"error": f"Booking {booking_id} not found"}


async def get_policy_tier(
    employee_id: str,
    db_path: str,
    session_id: str,
    employee_level: str = "",
    **kwargs,
) -> dict:
    # Try to get level from DB if not provided
    level = employee_level
    if not level:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            try:
                async with db.execute(
                    "SELECT level FROM employees WHERE id = ?", [employee_id]
                ) as cur:
                    row = await cur.fetchone()
                if row:
                    level = str(row["level"] or "")
            except Exception:
                pass

    tier = _POLICY_TIERS.get(level, "standard")
    tier_rules: dict[str, dict[str, Any]] = {
        "standard": {
            "max_flight_cost": 800.0,
            "flight_class": "economy",
            "max_hotel_per_night": 150.0,
            "advance_booking_days": 14,
        },
        "premium": {
            "max_flight_cost": 1500.0,
            "flight_class": "economy_plus",
            "max_hotel_per_night": 250.0,
            "advance_booking_days": 7,
        },
        "executive": {
            "max_flight_cost": 5000.0,
            "flight_class": "business",
            "max_hotel_per_night": 500.0,
            "advance_booking_days": 3,
        },
    }
    return {
        "employee_id": employee_id,
        "employee_level": level,
        "policy_tier": tier,
        "rules": tier_rules.get(tier, tier_rules["standard"]),
    }


async def search_alternatives(
    booking_type: str,
    destination: str,
    date: str,
    db_path: str,
    session_id: str,
    origin: str = "",
    max_cost: float = 0.0,
    **kwargs,
) -> dict:
    # Mock alternatives based on type
    if booking_type == "flight":
        alternatives = [
            {"flight_number": "AA100", "airline": "American", "departure": f"{date}T06:00:00", "cost": 380.0, "seat_class": "economy"},
            {"flight_number": "UA200", "airline": "United", "departure": f"{date}T09:30:00", "cost": 420.0, "seat_class": "economy"},
            {"flight_number": "DL300", "airline": "Delta", "departure": f"{date}T13:00:00", "cost": 395.0, "seat_class": "economy"},
            {"flight_number": "SW400", "airline": "Southwest", "departure": f"{date}T16:00:00", "cost": 299.0, "seat_class": "economy"},
        ]
    else:
        alternatives = [
            {"hotel_name": "Marriott", "check_in": date, "cost_per_night": 189.0, "rating": 4.2},
            {"hotel_name": "Hilton Garden Inn", "check_in": date, "cost_per_night": 145.0, "rating": 3.9},
            {"hotel_name": "Courtyard by Marriott", "check_in": date, "cost_per_night": 129.0, "rating": 3.8},
        ]
    if max_cost:
        key = "cost" if booking_type == "flight" else "cost_per_night"
        alternatives = [a for a in alternatives if a.get(key, 0) <= max_cost]
    return {
        "booking_type": booking_type,
        "destination": destination,
        "date": date,
        "origin": origin,
        "alternatives": alternatives,
        "count": len(alternatives),
    }


async def rebook_flight(
    booking_id: str,
    new_flight_number: str,
    new_departure: str,
    db_path: str,
    session_id: str,
    new_cost: float = 0.0,
    reason: str = "",
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute(
                """
                UPDATE bookings
                SET flight_number = ?, departure = ?, cost = ?, status = 'rebooked', rebook_reason = ?
                WHERE id = ?
                """,
                [new_flight_number, new_departure, new_cost, reason, booking_id],
            )
            await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "booking_id": booking_id,
        "new_flight_number": new_flight_number,
        "new_departure": new_departure,
        "new_cost": new_cost,
        "reason": reason,
        "status": "rebooked",
    }


async def rebook_hotel(
    booking_id: str,
    db_path: str,
    session_id: str,
    new_hotel_name: str = "",
    new_check_in: str = "",
    new_check_out: str = "",
    new_cost_per_night: float = 0.0,
    **kwargs,
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        try:
            fields: list[str] = []
            vals: list[Any] = []
            if new_hotel_name:
                fields.append("hotel_name = ?"); vals.append(new_hotel_name)
            if new_check_in:
                fields.append("check_in = ?"); vals.append(new_check_in)
            if new_check_out:
                fields.append("check_out = ?"); vals.append(new_check_out)
            if new_cost_per_night:
                fields.append("cost_per_night = ?"); vals.append(new_cost_per_night)
            fields.append("status = ?"); vals.append("rebooked")
            vals.append(booking_id)
            if len(fields) > 1:
                await db.execute(
                    f"UPDATE bookings SET {', '.join(fields)} WHERE id = ?", vals
                )
                await db.commit()
        except Exception:
            pass
    return {
        "success": True,
        "booking_id": booking_id,
        "new_hotel_name": new_hotel_name,
        "new_check_in": new_check_in,
        "new_check_out": new_check_out,
        "new_cost_per_night": new_cost_per_night,
        "status": "rebooked",
    }


async def get_loyalty_points(employee_id: str, db_path: str, session_id: str, **kwargs) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            async with db.execute(
                "SELECT * FROM loyalty_accounts WHERE employee_id = ?", [employee_id]
            ) as cur:
                row = await cur.fetchone()
            if row:
                return dict(row)
        except Exception:
            pass
    fixture = _LOYALTY_POINTS.get(employee_id)
    if fixture:
        return {"employee_id": employee_id, **fixture}
    return {
        "employee_id": employee_id,
        "airline_miles": 0,
        "hotel_points": 0,
        "program": "none",
        "source": "default",
    }
