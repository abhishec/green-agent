from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task20RetailAddressScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_20",
        task_text=(
            "Customer Sophia Kim (email: sophia.kim7734@example.com, zip: 98101) needs to: "
            "(1) update shipping address on pending order #W8841623 to her new address: "
            "'500 Pine Street, Apt 8A, Seattle, WA 98101, USA', and "
            "(2) change the payment method on order #W8841623 from PayPal PP-6634 to "
            "her gift card GC-1129 which has a $200.00 balance (order total is $87.50). "
            "First call find_user_by_email to verify identity, then get_order_details to confirm "
            "order #W8841623 is 'pending'. "
            "Then call get_user_details to verify GC-1129 exists and has sufficient balance ($200 >= $87.50). "
            "Call modify_pending_order_address to update the shipping address. "
            "Then call modify_pending_order_payment to switch payment to GC-1129. "
            "Confirm each change with the customer before applying. "
            "These are two separate modification steps."
        ),
        policy_doc=(
            "RETAIL ORDER MODIFICATION POLICY:\n"
            "1. Address and payment changes only allowed on 'pending' orders.\n"
            "2. Agent must verify customer identity before any change.\n"
            "3. For payment method change: new method must be different from current method.\n"
            "4. Gift card must have sufficient balance to cover entire order total.\n"
            "5. Agent must verify gift card balance before switching payment.\n"
            "6. Agent must confirm each change with customer before applying.\n"
            "7. Address and payment modifications can each be made independently.\n"
            "8. Customer must provide new address details explicitly."
        ),
        tools_available=[
            "find_user_by_email",
            "find_user_by_name_zip",
            "get_order_details",
            "get_user_details",
            "modify_pending_order_address",
            "modify_pending_order_payment",
            "confirm_with_user",
            "get_product_details",
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_20_fixture.json"),
        expected_state={
            "orders": [{
                "id": "W8841623",
                "status": "pending",
                "shipping_address": "500 Pine Street, Apt 8A, Seattle, WA 98101, USA",
                "payment_method": "GC-1129",
            }],
        },
        dependency_graph={
            "modify_pending_order_address": ["find_user_by_email", "get_order_details", "confirm_with_user"],
            "modify_pending_order_payment": ["find_user_by_email", "get_order_details", "get_user_details", "confirm_with_user"],
            "get_order_details": ["find_user_by_email"],
        },
        irreversible_actions=["modify_pending_order_address", "modify_pending_order_payment"],
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

        # functional (30%): address updated, payment switched
        func_points = 0
        order = next(
            (o for o in final_db.get("orders", []) if o["id"] == "W8841623"), {}
        )
        if "500 Pine Street" in order.get("shipping_address", ""):
            func_points += 35
        if order.get("payment_method") == "GC-1129":
            func_points += 35
        if self._action_called(actions_log, "get_user_details"):
            func_points += 15
        if self._action_called(actions_log, "get_order_details"):
            func_points += 15
        scores["functional"] = min(100.0, float(func_points))

        # policy_compliance (20%): identity verified, balance checked, confirm before each action
        violations = 0
        identity_ok = (
            self._action_called(actions_log, "find_user_by_email")
            or self._action_called(actions_log, "find_user_by_name_zip")
        )
        if not identity_ok:
            violations += 1
        if not self._action_called(actions_log, "get_user_details"):
            violations += 1  # balance check required
        # confirm_with_user should be called at some point before changes
        if not self._action_called(actions_log, "confirm_with_user"):
            violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 33.0)

        # escalation (15%): not required
        scores["escalation"] = 100.0

        # sequence (15%): verify -> get_order -> get_user -> modifications
        seq_ok = True
        verify_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) in ("find_user_by_email", "find_user_by_name_zip")),
            None,
        )
        addr_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "modify_pending_order_address"),
            None,
        )
        pay_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "modify_pending_order_payment"),
            None,
        )
        if verify_idx is None:
            seq_ok = False
        elif addr_idx is not None and verify_idx >= addr_idx:
            seq_ok = False
        elif pay_idx is not None and verify_idx >= pay_idx:
            seq_ok = False
        scores["sequence"] = 100.0 if seq_ok else 0.0

        # arithmetic (10%): verify GC balance sufficient
        output_str = agent_output + str(actions_log)
        arith = 0
        if "200" in output_str:
            arith += 40
        if "87.50" in output_str or "87.5" in output_str:
            arith += 40
        if "sufficient" in output_str.lower() or "enough" in output_str.lower():
            arith += 20
        scores["arithmetic"] = min(100.0, float(arith))

        scores["hallucination"] = 100.0

        # communication (5%)
        scores["communication"] = 100.0 if self._action_called(actions_log, "confirm_with_user") else 0.0

        return scores
