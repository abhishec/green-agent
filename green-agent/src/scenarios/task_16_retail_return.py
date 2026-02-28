from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task16RetailReturnScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_16",
        task_text=(
            "Customer Ana Ramirez (email: ana.ramirez4471@example.com, zip: 10023) requests "
            "a return of two items from delivered order #W4823901: "
            "(1) headphones ITEM-HP01 ($89.99) and (2) laptop stand ITEM-LS02 ($34.99). "
            "First call find_user_by_email to verify the customer identity, then get_order_details "
            "to confirm order #W4823901 status is 'delivered'. "
            "Process the return via return_order_items with refund going back to the original "
            "payment method credit_card CC-7291. "
            "Total refund = $89.99 + $34.99 = $124.98. "
            "Confirm all items and refund amount with the customer before submitting return. "
            "Return changes order status to 'return requested'."
        ),
        policy_doc=(
            "RETAIL RETURN POLICY:\n"
            "1. Orders can only be returned if status is 'delivered'.\n"
            "2. Agent must verify customer identity by email or name+zip before proceeding.\n"
            "3. Refund goes to original payment method or an existing gift card only.\n"
            "4. Agent must confirm all items and refund amount with customer before submitting.\n"
            "5. Return changes order status to 'return requested'.\n"
            "6. Refund timeline: 5-7 business days for credit card; immediate for gift card.\n"
            "7. Agent must not make up information not provided by tools or user.\n"
            "8. Each item to be returned must be explicitly listed with its item ID."
        ),
        tools_available=[
            "find_user_by_email",
            "find_user_by_name_zip",
            "get_order_details",
            "get_product_details",
            "return_order_items",
            "get_user_details",
            "confirm_with_user",
            "list_product_types",
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_16_fixture.json"),
        expected_state={
            "orders": [{"id": "W4823901", "status": "return requested"}],
            "return_items": ["ITEM-HP01", "ITEM-LS02"],
            "refund_amount": 124.98,
            "refund_method": "CC-7291",
        },
        dependency_graph={
            "return_order_items": ["find_user_by_email", "get_order_details", "confirm_with_user"],
            "get_order_details": ["find_user_by_email"],
        },
        irreversible_actions=["return_order_items"],
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

        # functional (30%): identity verified, order checked, return submitted correctly
        func_points = 0
        order = next(
            (o for o in final_db.get("orders", []) if o["id"] == "W4823901"), {}
        )
        if order.get("status") == "return requested":
            func_points += 40
        returned = final_db.get("return_items", [])
        if "ITEM-HP01" in returned:
            func_points += 20
        if "ITEM-LS02" in returned:
            func_points += 20
        if self._float_eq(final_db.get("refund_amount", 0), 124.98, tol=0.10):
            func_points += 20
        scores["functional"] = min(100.0, float(func_points))

        # policy_compliance (20%): identity verified before action, confirm before return
        violations = 0
        identity_verified = (
            self._action_called(actions_log, "find_user_by_email")
            or self._action_called(actions_log, "find_user_by_name_zip")
        )
        if not identity_verified:
            violations += 1
        confirm_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "confirm_with_user"),
            None,
        )
        return_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "return_order_items"),
            None,
        )
        if confirm_idx is None or return_idx is None or confirm_idx >= return_idx:
            violations += 1
        if not self._action_called(actions_log, "get_order_details"):
            violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 33.0)

        # escalation (15%): not required
        scores["escalation"] = 100.0

        # sequence (15%): verify identity -> get order -> confirm -> return
        seq_ok = True
        verify_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) in ("find_user_by_email", "find_user_by_name_zip")),
            None,
        )
        order_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_order_details"),
            None,
        )
        if verify_idx is None or order_idx is None:
            seq_ok = False
        elif return_idx is not None and verify_idx >= return_idx:
            seq_ok = False
        elif order_idx is not None and return_idx is not None and order_idx >= return_idx:
            seq_ok = False
        scores["sequence"] = 100.0 if seq_ok else 0.0

        # arithmetic (10%): correct refund total
        arith = 0
        output_str = agent_output + str(actions_log)
        if "124.98" in output_str or "124.99" in output_str:
            arith += 60
        if "89.99" in output_str:
            arith += 20
        if "34.99" in output_str:
            arith += 20
        scores["arithmetic"] = min(100.0, float(arith))

        scores["hallucination"] = 100.0

        # communication (5%): confirm before irreversible action
        scores["communication"] = (
            100.0
            if (confirm_idx is not None and return_idx is not None and confirm_idx < return_idx)
            else 0.0
        )

        return scores
