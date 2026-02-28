from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task19RetailModifyScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_19",
        task_text=(
            "Customer Diego Alvarez (name: Diego Alvarez, zip: 77002) has a pending order #W5512887 "
            "for two t-shirts. He wants to change both shirts from size 'large' to size 'medium'. "
            "First call find_user_by_name_zip to verify identity, then get_order_details to confirm "
            "order #W5512887 is 'pending'. "
            "Order contains: ITEM-TS01 (blue t-shirt, large, $25.99) and ITEM-TS02 (green t-shirt, large, $25.99). "
            "Call get_product_details for PROD-TS001 and PROD-TS002 to verify medium variants exist "
            "and confirm pricing ($24.99 each for medium - $1.00 cheaper per shirt). "
            "The price difference is -$2.00 total (refund). Refund goes to original payment CC-5571. "
            "Modify via modify_pending_order_items: change both items to medium size. "
            "Confirm changes with customer before submitting. "
            "modify_pending_order_items can only be called ONCE. "
            "After modification, order status becomes 'pending (items modified)'."
        ),
        policy_doc=(
            "RETAIL ORDER MODIFICATION POLICY:\n"
            "1. Items can only be modified in 'pending' orders.\n"
            "2. Agent must verify customer identity before any modification.\n"
            "3. modify_pending_order_items can only be called ONCE per session.\n"
            "4. Items must remain within same product type after modification.\n"
            "5. After successful modification, status becomes 'pending (items modified)' - no further changes allowed.\n"
            "6. Payment method for price differences must be selected by customer.\n"
            "7. Agent must check product details to confirm target variant availability.\n"
            "8. Agent must confirm all modifications with customer before submitting.\n"
            "9. Price decreases result in refund to original payment method."
        ),
        tools_available=[
            "find_user_by_email",
            "find_user_by_name_zip",
            "get_order_details",
            "get_product_details",
            "modify_pending_order_items",
            "get_user_details",
            "confirm_with_user",
            "list_product_types",
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_19_fixture.json"),
        expected_state={
            "orders": [{"id": "W5512887", "status": "pending (items modified)", "total": 49.98}],
            "order_items": [
                {"item_id": "ITEM-TS01", "size": "medium", "unit_price": 24.99},
                {"item_id": "ITEM-TS02", "size": "medium", "unit_price": 24.99},
            ],
            "price_difference": -2.00,
        },
        dependency_graph={
            "modify_pending_order_items": ["find_user_by_name_zip", "get_order_details", "get_product_details", "confirm_with_user"],
            "get_order_details": ["find_user_by_name_zip"],
        },
        irreversible_actions=["modify_pending_order_items"],
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

        # functional (30%): both items changed to medium, order total correct
        func_points = 0
        order = next(
            (o for o in final_db.get("orders", []) if o["id"] == "W5512887"), {}
        )
        if order.get("status") == "pending (items modified)":
            func_points += 30
        if self._float_eq(order.get("total", 0), 49.98, tol=0.10):
            func_points += 20
        items = {i["item_id"]: i for i in final_db.get("order_items", [])}
        ts01 = items.get("ITEM-TS01", {})
        ts02 = items.get("ITEM-TS02", {})
        if ts01.get("size") == "medium":
            func_points += 20
        if ts02.get("size") == "medium":
            func_points += 20
        if self._float_eq(ts01.get("unit_price", 0), 24.99, tol=0.10):
            func_points += 5
        if self._float_eq(ts02.get("unit_price", 0), 24.99, tol=0.10):
            func_points += 5
        scores["functional"] = min(100.0, float(func_points))

        # policy_compliance (20%): single modify call, confirm before modify, product checked
        violations = 0
        modify_calls = [a for a in actions_log if (a.get("tool") or a.get("action")) == "modify_pending_order_items"]
        if len(modify_calls) > 1:
            violations += 1
        confirm_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "confirm_with_user"),
            None,
        )
        modify_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "modify_pending_order_items"),
            None,
        )
        if confirm_idx is None or modify_idx is None or confirm_idx >= modify_idx:
            violations += 1
        if not self._action_called(actions_log, "get_product_details"):
            violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 33.0)

        # escalation (15%): not required
        scores["escalation"] = 100.0

        # sequence (15%): verify -> get_order -> get_product -> confirm -> modify
        seq_ok = True
        verify_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) in ("find_user_by_name_zip", "find_user_by_email")),
            None,
        )
        order_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_order_details"),
            None,
        )
        if verify_idx is None or order_idx is None or modify_idx is None:
            seq_ok = False
        elif verify_idx >= modify_idx or order_idx >= modify_idx:
            seq_ok = False
        scores["sequence"] = 100.0 if seq_ok else 0.0

        # arithmetic (10%): -$2.00 price difference, new total $49.98
        output_str = agent_output + str(actions_log)
        arith = 0
        if "49.98" in output_str:
            arith += 40
        if "24.99" in output_str:
            arith += 30
        if "-2" in output_str or "2.00" in output_str:
            arith += 30
        scores["arithmetic"] = min(100.0, float(arith))

        scores["hallucination"] = 100.0

        # communication (5%)
        scores["communication"] = (
            100.0
            if (confirm_idx is not None and modify_idx is not None and confirm_idx < modify_idx)
            else 0.0
        )

        return scores
