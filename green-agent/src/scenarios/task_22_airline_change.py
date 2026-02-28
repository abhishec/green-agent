from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task22AirlineChangeScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_22",
        task_text=(
            "Customer Omar Davis (user ID: omar_davis_3817, email: omar.davis3817@example.com) "
            "wants to downgrade all business class flights to economy across his reservations "
            "to save money. He has 5 reservations: JG7FMM, 2FBBAH, X7BYG1, EQ1G6C, BOH180. "
            "First call get_user_details to confirm user omar_davis_3817 and retrieve reservation IDs. "
            "Then call get_reservation_details for each of the 5 reservations to see current class and fare. "
            "For each reservation, call update_reservation_flights to downgrade cabin from business to economy "
            "(do NOT change flights or passengers, only the cabin class). "
            "Calculate total savings across all 5 reservations. "
            "Confirm the total savings and all changes with the customer before proceeding. "
            "Provide a summary of total savings at the end."
        ),
        policy_doc=(
            "AIRLINE FLIGHT CHANGE POLICY:\n"
            "1. Basic economy flights cannot be changed.\n"
            "2. Other reservations may switch flights without altering origin/destination/trip type.\n"
            "3. Cabin changes apply uniformly across all segments of a reservation.\n"
            "4. Checked bags can only be added, not removed.\n"
            "5. Travel insurance cannot be added after booking.\n"
            "6. Agent must verify user identity before making any changes.\n"
            "7. Agent must confirm changes with customer before applying.\n"
            "8. Refunds for downgrades process in 5-7 business days to original payment method."
        ),
        tools_available=[
            "get_user_details",
            "get_reservation_details",
            "update_reservation_flights",
            "update_reservation_baggages",
            "confirm_with_user",
            "calculate_fare",
            "search_direct_flights",
            "list_airports",
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_22_fixture.json"),
        expected_state={
            "reservations": [
                {"id": "JG7FMM", "cabin": "economy"},
                {"id": "2FBBAH", "cabin": "economy"},
                {"id": "X7BYG1", "cabin": "economy"},
                {"id": "EQ1G6C", "cabin": "economy"},
                {"id": "BOH180", "cabin": "economy"},
            ],
            "total_savings": 23553.00,
        },
        dependency_graph={
            "update_reservation_flights": ["get_user_details", "get_reservation_details", "confirm_with_user"],
            "get_reservation_details": ["get_user_details"],
        },
        irreversible_actions=["update_reservation_flights"],
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
        reservation_ids = ["JG7FMM", "2FBBAH", "X7BYG1", "EQ1G6C", "BOH180"]

        # functional (30%): all 5 reservations downgraded to economy
        func_points = 0
        reservations = {r["id"]: r for r in final_db.get("reservations", [])}
        downgraded = sum(1 for rid in reservation_ids if reservations.get(rid, {}).get("cabin") == "economy")
        func_points += downgraded * 14  # 14 pts each
        if self._float_eq(final_db.get("total_savings", 0), 23553.00, tol=100.0):
            func_points += 30
        scores["functional"] = min(100.0, float(func_points))

        # policy_compliance (20%): identity verified, confirm before changes, no flight changes
        violations = 0
        if not self._action_called(actions_log, "get_user_details"):
            violations += 1
        if not self._action_called(actions_log, "confirm_with_user"):
            violations += 1
        # All 5 reservations should have been checked
        get_res_calls = [a for a in actions_log if (a.get("tool") or a.get("action")) == "get_reservation_details"]
        if len(get_res_calls) < 5:
            violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 33.0)

        # escalation (15%): not required
        scores["escalation"] = 100.0

        # sequence (15%): get_user -> get_reservations -> confirm -> update
        seq_ok = True
        user_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_user_details"),
            None,
        )
        first_update_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "update_reservation_flights"),
            None,
        )
        if user_idx is None or first_update_idx is None:
            seq_ok = False
        elif user_idx >= first_update_idx:
            seq_ok = False
        scores["sequence"] = 100.0 if seq_ok else 0.0

        # arithmetic (10%): total savings $23,553
        output_str = agent_output + str(actions_log)
        arith = 0
        if "23553" in output_str or "23,553" in output_str:
            arith += 80
        if "economy" in output_str.lower():
            arith += 20
        scores["arithmetic"] = min(100.0, float(arith))

        scores["hallucination"] = 100.0

        # communication (5%): confirm with user
        scores["communication"] = 100.0 if self._action_called(actions_log, "confirm_with_user") else 0.0

        return scores
