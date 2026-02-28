from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task17RetailCancelScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_17",
        task_text=(
            "Customer Marcus Chen (name: Marcus Chen, zip: 60614) wants to cancel "
            "pending order #W7719302. "
            "The customer says he ordered the item by mistake. "
            "First call find_user_by_name_zip to verify customer identity, then "
            "get_order_details to confirm order #W7719302 is in 'pending' status. "
            "The order total is $157.50 for a coffee maker ITEM-CM01. "
            "Payment was made with gift card GC-3847 ($100) and credit card CC-9034 ($57.50). "
            "Cancel the order via cancel_pending_order with reason 'ordered by mistake'. "
            "Confirm the cancellation with the customer before proceeding. "
            "Gift card refund is immediate; credit card refund takes 5-7 business days."
        ),
        policy_doc=(
            "RETAIL CANCELLATION POLICY:\n"
            "1. Orders can only be cancelled if status is 'pending'.\n"
            "2. Agent must verify customer identity by email or name+zip before proceeding.\n"
            "3. Cancellation reason must be either 'no longer needed' or 'ordered by mistake'.\n"
            "4. Agent must get explicit customer confirmation before cancelling.\n"
            "5. Gift card refunds are immediate; credit card refunds take 5-7 business days.\n"
            "6. Split-payment refunds return each portion to its original payment method.\n"
            "7. Cancelled orders cannot be un-cancelled.\n"
            "8. Agent must check order status before attempting cancellation."
        ),
        tools_available=[
            "find_user_by_email",
            "find_user_by_name_zip",
            "get_order_details",
            "get_user_details",
            "cancel_pending_order",
            "confirm_with_user",
            "get_product_details",
            "list_product_types",
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_17_fixture.json"),
        expected_state={
            "orders": [{"id": "W7719302", "status": "cancelled"}],
            "refunds": [
                {"payment_id": "GC-3847", "amount": 100.00, "timeline": "immediate"},
                {"payment_id": "CC-9034", "amount": 57.50, "timeline": "5-7 days"},
            ],
        },
        dependency_graph={
            "cancel_pending_order": ["find_user_by_name_zip", "get_order_details", "confirm_with_user"],
            "get_order_details": ["find_user_by_name_zip"],
        },
        irreversible_actions=["cancel_pending_order"],
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

        # functional (30%): identity verified, order status confirmed, cancellation done
        func_points = 0
        order = next(
            (o for o in final_db.get("orders", []) if o["id"] == "W7719302"), {}
        )
        if order.get("status") == "cancelled":
            func_points += 50
        if self._action_called(actions_log, "find_user_by_name_zip") or self._action_called(actions_log, "find_user_by_email"):
            func_points += 25
        if self._action_called(actions_log, "get_order_details"):
            func_points += 25
        scores["functional"] = min(100.0, float(func_points))

        # policy_compliance (20%): identity check, order status verified, confirm before cancel
        violations = 0
        identity_ok = (
            self._action_called(actions_log, "find_user_by_name_zip")
            or self._action_called(actions_log, "find_user_by_email")
        )
        if not identity_ok:
            violations += 1
        confirm_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "confirm_with_user"),
            None,
        )
        cancel_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "cancel_pending_order"),
            None,
        )
        if confirm_idx is None or cancel_idx is None or confirm_idx >= cancel_idx:
            violations += 1
        # Check reason is valid
        output_str = agent_output + str(actions_log)
        if "ordered by mistake" not in output_str.lower() and "no longer needed" not in output_str.lower():
            violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 33.0)

        # escalation (15%): not required
        scores["escalation"] = 100.0

        # sequence (15%): verify -> get_order -> confirm -> cancel
        seq_ok = True
        verify_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) in ("find_user_by_name_zip", "find_user_by_email")),
            None,
        )
        order_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_order_details"),
            None,
        )
        if verify_idx is None or order_idx is None or cancel_idx is None:
            seq_ok = False
        elif verify_idx >= cancel_idx or order_idx >= cancel_idx:
            seq_ok = False
        scores["sequence"] = 100.0 if seq_ok else 0.0

        # arithmetic (10%): refund amounts correct
        arith = 0
        if "100" in output_str and "gc" in output_str.lower() or "gift" in output_str.lower():
            arith += 30
        if "57.50" in output_str:
            arith += 30
        if "157.50" in output_str or "157.5" in output_str:
            arith += 40
        scores["arithmetic"] = min(100.0, float(arith))

        scores["hallucination"] = 100.0

        # communication (5%): confirm before irreversible
        scores["communication"] = (
            100.0
            if (confirm_idx is not None and cancel_idx is not None and confirm_idx < cancel_idx)
            else 0.0
        )

        return scores
