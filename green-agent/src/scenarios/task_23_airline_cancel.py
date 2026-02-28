from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task23AirlineCancelScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_23",
        task_text=(
            "Customer Olivia Gonzalez (user ID: olivia_gonzalez_2305, email: olivia.gonzalez2305@example.com) "
            "has reservation Z7GOZK (a round-trip from Texas (DAL) to Newark (EWR)). "
            "She wants to change the return flight to a later same-day departure or next-day earliest flight. "
            "The current return flight departs at 3:00pm. "
            "First call get_user_details to confirm user olivia_gonzalez_2305. "
            "Call get_reservation_details for Z7GOZK to see current flights and cabin class (basic economy). "
            "Important: basic economy flights CANNOT be changed. Since the return flight cannot be changed, "
            "check if the customer has travel insurance by reviewing reservation details. "
            "If the customer has travel insurance, offer to cancel the full reservation for a full refund. "
            "The customer will agree to cancel if basic economy cannot be changed. "
            "Confirm with the customer that cancellation will be done. "
            "Call cancel_reservation to cancel Z7GOZK. "
            "Refund processes in 5-7 business days."
        ),
        policy_doc=(
            "AIRLINE CANCELLATION POLICY:\n"
            "1. Basic economy flights cannot be changed - only full cancellation allowed.\n"
            "2. Cancellations allowed: within 24 hours of booking, or if airline cancelled.\n"
            "3. Travel insurance covers full refund for health or weather-related cancellations.\n"
            "4. Refunds process in 5-7 business days to original payment methods.\n"
            "5. Agent must verify user identity before any cancellation.\n"
            "6. Agent must confirm the cancellation with customer before executing.\n"
            "7. Agent must check if ticket type allows changes before attempting change.\n"
            "8. Agent must offer alternatives (cancellation if changes not possible) to assist customer."
        ),
        tools_available=[
            "get_user_details",
            "get_reservation_details",
            "cancel_reservation",
            "update_reservation_flights",
            "search_direct_flights",
            "search_onestop_flights",
            "confirm_with_user",
            "list_airports",
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_23_fixture.json"),
        expected_state={
            "reservations": [{"id": "Z7GOZK", "status": "cancelled"}],
            "refund_amount": 387.50,
        },
        dependency_graph={
            "cancel_reservation": ["get_user_details", "get_reservation_details", "confirm_with_user"],
            "get_reservation_details": ["get_user_details"],
        },
        irreversible_actions=["cancel_reservation"],
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

        # functional (30%): reservation cancelled, policy understood
        func_points = 0
        reservations = {r["id"]: r for r in final_db.get("reservations", [])}
        if reservations.get("Z7GOZK", {}).get("status") == "cancelled":
            func_points += 50
        if self._action_called(actions_log, "get_reservation_details"):
            func_points += 20
        output_str = agent_output + str(actions_log)
        if "basic economy" in output_str.lower() or "cannot be changed" in output_str.lower():
            func_points += 30
        scores["functional"] = min(100.0, float(func_points))

        # policy_compliance (20%): identity verified, recognized basic economy constraint,
        #   confirmed before cancellation
        violations = 0
        if not self._action_called(actions_log, "get_user_details"):
            violations += 1
        confirm_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "confirm_with_user"),
            None,
        )
        cancel_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "cancel_reservation"),
            None,
        )
        if confirm_idx is None or cancel_idx is None or confirm_idx >= cancel_idx:
            violations += 1
        # Should NOT have attempted update_reservation_flights on basic economy
        update_calls = [a for a in actions_log if (a.get("tool") or a.get("action")) == "update_reservation_flights"]
        if len(update_calls) > 0:
            violations += 1  # should know basic economy cannot be changed
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 33.0)

        # escalation (15%): not required
        scores["escalation"] = 100.0

        # sequence (15%): get_user -> get_reservation -> inform customer -> confirm -> cancel
        seq_ok = True
        user_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_user_details"),
            None,
        )
        res_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_reservation_details"),
            None,
        )
        if user_idx is None or res_idx is None or cancel_idx is None:
            seq_ok = False
        elif user_idx >= cancel_idx or res_idx >= cancel_idx:
            seq_ok = False
        scores["sequence"] = 100.0 if seq_ok else 0.0

        # arithmetic (10%): refund amount
        arith = 0
        if "387.50" in output_str or "387.5" in output_str:
            arith += 60
        if "5" in output_str and "7" in output_str and "business day" in output_str.lower():
            arith += 40
        scores["arithmetic"] = min(100.0, float(arith))

        scores["hallucination"] = 100.0

        # communication (5%)
        scores["communication"] = (
            100.0
            if (confirm_idx is not None and cancel_idx is not None and confirm_idx < cancel_idx)
            else 0.0
        )

        return scores
