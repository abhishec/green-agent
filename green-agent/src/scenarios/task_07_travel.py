from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task07TravelScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_07",
        task_text="Rebook James Whitfield's trip after UA288 cancellation.",
        policy_doc=(
            "POLICY:\n"
            "1. Domestic economy cap: $500. Economy tickets over $500 violate policy.\n"
            "2. Business class allowed for international flights only.\n"
            "3. Domestic rebook cap: $1,500 total.\n"
            "4. Hotel cap: $200/night domestic. Anything over requires VP exception or rebooking.\n"
            "5. Gold tier loyalty: free same-day changes, upgrade priority.\n"
            "6. International connection buffer: verify arrival time allows for connection.\n"
            "7. Traveler must be notified of rebooking details including mileage credit."
        ),
        tools_available=[
            "get_booking", "search_alternatives", "rebook_flight",
            "check_policy_compliance", "flag_hotel_policy_violation",
            "request_vp_exception", "notify_traveler", "cancel_booking"
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_07_fixture.json"),
        expected_state={
            "bookings": [
                {"id": "BK-001", "status": "cancelled"},
                {"id": "BK-004", "flight": "AA1043", "status": "confirmed", "cost": 1100.00},
                {"id": "BK-002", "status": "flagged_policy_violation"},
                {"id": "BK-003", "status": "active"},
            ]
        },
        dependency_graph={
            "rebook_flight": ["search_alternatives", "check_policy_compliance"],
            "flag_hotel_policy_violation": ["get_booking"],
            "notify_traveler": ["rebook_flight"],
        },
        irreversible_actions=["rebook_flight", "cancel_booking"],
        escalation_required=True,
        escalation_trigger="Hotel $289/night > $200 domestic cap — requires VP exception or rebooking",
    )

    def score(self, initial_db, final_db, actions_log, agent_output):
        scores = {}

        # functional: AA1043 booked, hotel violation flagged, NYC-LON unchanged, traveler notified
        func = 0
        rebooking = [a for a in actions_log if (a.get("tool") or a.get("action")) == "rebook_flight"]
        if any("AA1043" in str(a) or "1043" in str(a) for a in rebooking): func += 35
        if self._action_called(actions_log, "flag_hotel_policy_violation"): func += 25
        # BK-003 NYC-LON must remain untouched
        nyc_lon_cancelled = any("BK-003" in str(a) and "cancel" in str(a.get("tool","")).lower() for a in actions_log)
        if not nyc_lon_cancelled: func += 20
        if self._action_called(actions_log, "notify_traveler"): func += 20
        scores["functional"] = min(100.0, float(func))

        # policy_compliance: no economy over $500 booked, no cap violations
        violations = 0
        for a in rebooking:
            cost = a.get("params", {}).get("cost", 0) or a.get("cost", 0)
            flight_class = a.get("params", {}).get("class", "") or a.get("class", "")
            if "economy" in str(flight_class).lower() and float(cost or 0) > 500: violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 50.0)

        # escalation: hotel violation flagged + VP exception requested or hotel rebooked
        esc = self._action_called(actions_log, "flag_hotel_policy_violation") or self._action_called(actions_log, "request_vp_exception")
        scores["escalation"] = 100.0 if esc else 0.0

        # sequence: search before rebook, check policy before rebook
        search_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "search_alternatives"), None)
        rebook_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "rebook_flight"), None)
        scores["sequence"] = 100.0 if (search_idx is not None and rebook_idx is not None and search_idx < rebook_idx) else 50.0

        # arithmetic: AA1043 $1100 < $1500 cap (valid), hotel $289 > $200 cap (violation)
        arith = 50
        if any("1100" in str(a) for a in rebooking): arith += 25
        if self._action_called(actions_log, "flag_hotel_policy_violation"): arith += 25
        scores["arithmetic"] = float(arith)

        scores["hallucination"] = 100.0
        scores["communication"] = 100.0 if self._action_called(actions_log, "notify_traveler") else 0.0

        return scores
