from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task21AirlineBookingScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_21",
        task_text=(
            "Customer Mia Li (user ID: mia_li_3668, email: mia.li3668@example.com) wants to book "
            "a one-way economy flight from New York (JFK) to Seattle (SEA) on May 20, 2026, "
            "departing after 11am EST. She prefers direct flights and lowest price. "
            "Passenger: Mia Li, DOB 1990-04-05. She has 2 checked bags and declines travel insurance. "
            "Payment: travel certificate CERT-2501 ($250) plus credit card CC-3311 for the remainder. "
            "First call get_user_details to confirm mia_li_3668 exists and retrieve payment methods. "
            "Call search_direct_flights for JFK->SEA on 2026-05-20 after 11:00 EST. "
            "Select the cheapest direct flight that departs after 11am. "
            "Call calculate_fare to compute total: base fare + baggage fees ($50 per extra bag; "
            "economy gets 1 free bag so 1 extra bag = $50). "
            "Confirm booking details with customer. "
            "Call book_flight to create the reservation with CERT-2501 ($250) and CC-3311 for remainder."
        ),
        policy_doc=(
            "AIRLINE BOOKING POLICY:\n"
            "1. Agent must obtain user ID first, then collect trip and passenger details.\n"
            "2. All passengers must travel in the same cabin class.\n"
            "3. Payment: one travel certificate + one credit card + up to three gift cards allowed.\n"
            "4. Baggage: Economy class - 1 free checked bag; each extra bag costs $50.\n"
            "5. Travel insurance costs $30 per passenger; must be selected at booking time.\n"
            "6. Silver members: 1-3 free bags; Gold members: 2-3 free bags (by cabin).\n"
            "7. Agent must confirm all booking details with customer before finalizing.\n"
            "8. Agent must not recommend specific flights based on personal preference."
        ),
        tools_available=[
            "get_user_details",
            "search_direct_flights",
            "search_onestop_flights",
            "calculate_fare",
            "book_flight",
            "confirm_with_user",
            "list_airports",
            "get_flight_details",
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_21_fixture.json"),
        expected_state={
            "reservations": [{"status": "confirmed", "route": "JFK->SEA", "cabin": "economy", "bags": 2}],
            "payment": {"certificate": "CERT-2501", "amount_cert": 250.00},
        },
        dependency_graph={
            "book_flight": ["get_user_details", "search_direct_flights", "calculate_fare", "confirm_with_user"],
            "calculate_fare": ["search_direct_flights"],
        },
        irreversible_actions=["book_flight"],
        escalation_required=False,
    )

    def score(
        self,
        initial_db: dict,
        final_db: dict,
        actions_log: list[dict],
        agent_output: str,
    ) -> dict[str, float]:
        scores = {}

        # functional (30%): reservation created with correct details
        func_points = 0
        reservations = final_db.get("reservations", [])
        res = next((r for r in reservations if r.get("route") == "JFK->SEA"), {})
        if res.get("status") == "confirmed":
            func_points += 35
        if res.get("cabin") == "economy":
            func_points += 20
        if res.get("bags") == 2:
            func_points += 20
        if self._action_called(actions_log, "search_direct_flights"):
            func_points += 15
        if self._action_called(actions_log, "get_user_details"):
            func_points += 10
        scores["functional"] = min(100.0, float(func_points))

        # policy_compliance (20%): identity verified, confirm before booking, no insurance added
        violations = 0
        if not self._action_called(actions_log, "get_user_details"):
            violations += 1
        confirm_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "confirm_with_user"),
            None,
        )
        book_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "book_flight"),
            None,
        )
        if confirm_idx is None or book_idx is None or confirm_idx >= book_idx:
            violations += 1
        output_str = agent_output + str(actions_log)
        # Insurance should be declined, not added
        if "insurance" in output_str.lower() and "30" in output_str and "added" in output_str.lower():
            violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 33.0)

        # escalation (15%): not required
        scores["escalation"] = 100.0

        # sequence (15%): get_user -> search -> calculate -> confirm -> book
        seq_ok = True
        user_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_user_details"),
            None,
        )
        search_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) in ("search_direct_flights", "search_onestop_flights")),
            None,
        )
        if user_idx is None or search_idx is None or book_idx is None:
            seq_ok = False
        elif user_idx >= book_idx or search_idx >= book_idx:
            seq_ok = False
        scores["sequence"] = 100.0 if seq_ok else 0.0

        # arithmetic (10%): baggage fee = $50 for 1 extra bag; certificate covers $250
        output_str = agent_output + str(actions_log)
        arith = 0
        if "50" in output_str and ("bag" in output_str.lower() or "baggage" in output_str.lower()):
            arith += 40
        if "250" in output_str and ("cert" in output_str.lower() or "certificate" in output_str.lower()):
            arith += 40
        if self._action_called(actions_log, "calculate_fare"):
            arith += 20
        scores["arithmetic"] = min(100.0, float(arith))

        scores["hallucination"] = 100.0

        # communication (5%)
        scores["communication"] = (
            100.0
            if (confirm_idx is not None and book_idx is not None and confirm_idx < book_idx)
            else 0.0
        )

        return scores
