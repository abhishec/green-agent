from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task18RetailExchangeScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_18",
        task_text=(
            "Customer Priya Patel (email: priya.patel2293@example.com, zip: 94102) wants to "
            "exchange an item from delivered order #W6634812. "
            "She purchased a desk lamp ITEM-DL01 (black, $45.99) but wants to exchange it "
            "for the same lamp in white color (PROD-DL01, white variant, also $45.99 - no price difference). "
            "First call find_user_by_email to verify identity, then get_order_details to confirm "
            "order #W6634812 is 'delivered'. "
            "Call get_product_details for PROD-DL01 to confirm the white variant exists and its price. "
            "Process via exchange_order_items: exchange ITEM-DL01 for PROD-DL01 white. "
            "No price difference - no additional payment needed. "
            "Original payment method was gift card GC-8821. "
            "Confirm the exchange with customer before submitting. "
            "Exchange changes order status to 'exchange requested'."
        ),
        policy_doc=(
            "RETAIL EXCHANGE POLICY:\n"
            "1. Orders can only be exchanged if status is 'delivered'.\n"
            "2. Agent must verify customer identity before proceeding.\n"
            "3. Exchange must be within same product type (e.g., lamp for lamp, not lamp for chair).\n"
            "4. Agent must check product details to confirm target variant exists.\n"
            "5. Price differences: customer pays extra if new item costs more; refunded if less.\n"
            "6. Payment for price difference uses original payment method or another on-file method.\n"
            "7. Agent must confirm all exchange details with customer before submitting.\n"
            "8. Exchange changes order status to 'exchange requested'."
        ),
        tools_available=[
            "find_user_by_email",
            "find_user_by_name_zip",
            "get_order_details",
            "get_product_details",
            "exchange_order_items",
            "get_user_details",
            "confirm_with_user",
            "list_product_types",
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_18_fixture.json"),
        expected_state={
            "orders": [{"id": "W6634812", "status": "exchange requested"}],
            "exchanges": [{"item_id": "ITEM-DL01", "new_product_id": "PROD-DL01", "new_variant": "white"}],
            "price_difference": 0.0,
        },
        dependency_graph={
            "exchange_order_items": ["find_user_by_email", "get_order_details", "get_product_details", "confirm_with_user"],
            "get_order_details": ["find_user_by_email"],
            "get_product_details": ["get_order_details"],
        },
        irreversible_actions=["exchange_order_items"],
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

        # functional (30%): identity verified, product checked, exchange submitted
        func_points = 0
        order = next(
            (o for o in final_db.get("orders", []) if o["id"] == "W6634812"), {}
        )
        if order.get("status") == "exchange requested":
            func_points += 40
        exchanges = final_db.get("exchanges", [])
        exchange_ok = any(
            e.get("item_id") == "ITEM-DL01" and "white" in str(e.get("new_variant", "")).lower()
            for e in exchanges
        )
        if exchange_ok:
            func_points += 35
        if self._action_called(actions_log, "get_product_details"):
            func_points += 25
        scores["functional"] = min(100.0, float(func_points))

        # policy_compliance (20%): identity verified, product confirmed, confirm before exchange
        violations = 0
        identity_ok = (
            self._action_called(actions_log, "find_user_by_email")
            or self._action_called(actions_log, "find_user_by_name_zip")
        )
        if not identity_ok:
            violations += 1
        confirm_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "confirm_with_user"),
            None,
        )
        exchange_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "exchange_order_items"),
            None,
        )
        if confirm_idx is None or exchange_idx is None or confirm_idx >= exchange_idx:
            violations += 1
        if not self._action_called(actions_log, "get_product_details"):
            violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 33.0)

        # escalation (15%): not required
        scores["escalation"] = 100.0

        # sequence (15%): verify -> get_order -> get_product -> confirm -> exchange
        seq_ok = True
        verify_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) in ("find_user_by_email", "find_user_by_name_zip")),
            None,
        )
        order_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_order_details"),
            None,
        )
        prod_idx = next(
            (i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_product_details"),
            None,
        )
        if verify_idx is None or order_idx is None:
            seq_ok = False
        elif exchange_idx is not None and (verify_idx >= exchange_idx or order_idx >= exchange_idx):
            seq_ok = False
        scores["sequence"] = 100.0 if seq_ok else 0.0

        # arithmetic (10%): no price difference
        output_str = agent_output + str(actions_log)
        arith = 0
        if "45.99" in output_str:
            arith += 40
        if "0" in output_str and ("difference" in output_str.lower() or "no additional" in output_str.lower()):
            arith += 60
        scores["arithmetic"] = min(100.0, float(arith))

        scores["hallucination"] = 100.0

        # communication (5%)
        scores["communication"] = (
            100.0
            if (confirm_idx is not None and exchange_idx is not None and confirm_idx < exchange_idx)
            else 0.0
        )

        return scores
