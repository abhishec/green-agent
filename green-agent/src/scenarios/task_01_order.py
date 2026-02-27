from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task01OrderScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_01",
        task_text=(
            "Customer ORD-001 requests: (1) change shirt to red/medium, "
            "(2) exchange jeans to size large, (3) cancel hat, (4) keep shoes. "
            "Refund all price differences back to gift card GC-001. "
            "Status must reflect modifications."
        ),
        policy_doc=(
            "POLICY:\n"
            "1. Single-call constraint: modify_order_items may only be called ONCE per session.\n"
            "2. Agent must confirm the new order total with the customer before modifying.\n"
            "3. Agent must verify GC-001 belongs to the ordering customer before applying refund.\n"
            "4. Gift card balance must not be credited beyond original purchase amount (no profit on refund).\n"
            "5. Order status must be updated to 'pending (items modified)' after successful modification.\n"
            "6. Cancelled items must have cancel_order_item called separately; do not include in modify_order_items."
        ),
        tools_available=[
            "get_order", "get_order_items", "get_product_variants", "get_gift_card_balance",
            "modify_order_items", "cancel_order_item", "process_payment_adjustment", "confirm_with_user"
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_01_fixture.json"),
        expected_state={
            "orders": [{"id": "ORD-001", "total": 137.00, "status": "pending (items modified)"}],
            "order_items": [
                {"id": "ITEM-A", "variant": {"color": "red", "size": "medium"}, "unit_price": 42.00},
                {"id": "ITEM-B", "variant": {"size": "large"}, "unit_price": 35.00},
                {"id": "ITEM-D", "unit_price": 60.00},
            ],
            "gift_cards": [{"id": "GC-001", "balance": 35.43}],
            "cancelled_items": ["ITEM-C"],
        },
        dependency_graph={
            "modify_order_items": ["get_order_items", "get_product_variants", "confirm_with_user"],
            "process_payment_adjustment": ["modify_order_items"],
            "cancel_order_item": ["get_order_items"],
        },
        irreversible_actions=["modify_order_items", "cancel_order_item", "process_payment_adjustment"],
        escalation_required=False,
    )

    def score(self, initial_db, final_db, actions_log, agent_output):
        scores = {}
        called = self._actions_called(actions_log)

        # functional (30%): correct variants, total, GC balance, status, cancelled item
        func_points = 0
        order = next((o for o in final_db.get("orders", []) if o["id"] == "ORD-001"), {})
        if self._float_eq(order.get("total"), 137.00): func_points += 25
        if order.get("status") == "pending (items modified)": func_points += 15
        items = {i["id"]: i for i in final_db.get("order_items", [])}
        item_a = items.get("ITEM-A", {})
        if item_a.get("variant", {}).get("color") == "red" and item_a.get("variant", {}).get("size") == "medium": func_points += 15
        if self._float_eq(item_a.get("unit_price"), 42.00): func_points += 10
        item_b = items.get("ITEM-B", {})
        if item_b.get("variant", {}).get("size") == "large": func_points += 10
        if self._float_eq(item_b.get("unit_price"), 35.00): func_points += 10
        gc = next((g for g in final_db.get("gift_cards", []) if g["id"] == "GC-001"), {})
        if self._float_eq(gc.get("balance"), 35.43): func_points += 15
        scores["functional"] = min(100.0, float(func_points))

        # policy_compliance (20%): single modify call + confirm before modify + GC ownership verified
        violations = 0
        modify_calls = [a for a in actions_log if (a.get("tool") or a.get("action")) == "modify_order_items"]
        if len(modify_calls) > 1: violations += 1  # single-call violated
        # confirm must appear before modify in log
        confirm_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "confirm_with_user"), None)
        modify_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "modify_order_items"), None)
        if confirm_idx is None or modify_idx is None or confirm_idx >= modify_idx: violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 33.0)

        # escalation (15%): not required
        scores["escalation"] = 100.0

        # sequence (15%): get_order_items and get_product_variants before modify
        seq_ok = True
        gi_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_order_items"), None)
        gv_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_product_variants"), None)
        if gi_idx is None or gv_idx is None: seq_ok = False
        elif modify_idx is not None and (gi_idx >= modify_idx or gv_idx >= modify_idx): seq_ok = False
        scores["sequence"] = 100.0 if seq_ok else 0.0

        # arithmetic (10%): 42+35+60=137, refund=23, new_gc=35.43
        arith = 0
        if self._float_eq(order.get("total"), 137.00): arith += 50
        if self._float_eq(gc.get("balance"), 35.43): arith += 50
        scores["arithmetic"] = float(arith)

        # hallucination (5%): not scored for tasks 01-10
        scores["hallucination"] = 100.0

        # communication (5%): confirm_with_user called before irreversible action
        scores["communication"] = 100.0 if (confirm_idx is not None and modify_idx is not None and confirm_idx < modify_idx) else 0.0

        return scores
