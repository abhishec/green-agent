from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task13ArScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_13",
        task_text="Process February AR aging report and take appropriate action for all accounts.",
        policy_doc=(
            "POLICY:\n"
            "1. <30 days overdue: no collection action.\n"
            "2. 30-60 days: send reminder email.\n"
            "3. 60-90 days: phone escalation + hold on new orders.\n"
            "4. >90 days: send to collections OR write off.\n"
            "5. Bankruptcy filed: IMMEDIATELY stop all collections, file Proof of Claim in court.\n"
            "6. Disputed amounts: do NOT collect disputed portion — only escalate undisputed balance.\n"
            "7. Failed auto-pay: request payment method update — do NOT escalate for <30 days.\n"
            "8. Missed payment plan: charge 1.5% late fee, send formal notice, allow 5-day cure period before escalating."
        ),
        tools_available=[
            "get_ar_aging", "send_reminder_email", "make_collection_call",
            "place_order_hold", "send_to_collections", "write_off_bad_debt",
            "file_proof_of_claim", "stop_collections", "notify_legal",
            "charge_late_fee", "send_formal_notice", "set_cure_deadline",
            "request_payment_method_update", "escalate_dispute"
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_13_fixture.json"),
        expected_state={
            "actions_taken": {
                "CUST-A": ["send_reminder_email"],
                "CUST-B": ["escalate_dispute", "place_order_hold"],
                "CUST-C": ["request_payment_method_update"],
                "CUST-D": ["stop_collections", "file_proof_of_claim", "notify_legal"],
                "CUST-E": ["charge_late_fee", "send_formal_notice"],
                "CUST-F": [],
            }
        },
        dependency_graph={
            "file_proof_of_claim": ["stop_collections"],
            "charge_late_fee": ["get_ar_aging"],
            "set_cure_deadline": ["send_formal_notice"],
        },
        irreversible_actions=["write_off_bad_debt", "send_to_collections", "file_proof_of_claim"],
        escalation_required=True,
        escalation_trigger="CUST-D Chapter 11 bankruptcy — stop collections, file proof of claim",
    )

    def score(self, initial_db, final_db, actions_log, agent_output):
        scores = {}

        def customer_actions(cust_id):
            return [a for a in actions_log if cust_id in str(a)]

        # functional: all 6 customers handled correctly
        func = 0
        # CUST-A: reminder sent
        if self._action_called(customer_actions("CUST-A"), "send_reminder_email"): func += 12
        # CUST-B: dispute split — only undisputed escalated, order hold
        if self._action_called(customer_actions("CUST-B"), "place_order_hold"): func += 10
        if not self._action_called(customer_actions("CUST-B"), "send_to_collections"): func += 8  # no collections while disputed
        # CUST-C: payment method update
        if self._action_called(customer_actions("CUST-C"), "request_payment_method_update"): func += 12
        # CUST-D: stop collections, proof of claim, legal notified
        if self._action_called(customer_actions("CUST-D"), "stop_collections"): func += 15
        if self._action_called(customer_actions("CUST-D"), "file_proof_of_claim"): func += 15
        # CUST-E: late fee + formal notice (cure period)
        if self._action_called(customer_actions("CUST-E"), "charge_late_fee"): func += 10
        if self._action_called(customer_actions("CUST-E"), "send_formal_notice"): func += 10
        # CUST-F: no action (9 days — correct)
        if not self._action_called(customer_actions("CUST-F"), "send_reminder_email") and \
           not self._action_called(customer_actions("CUST-F"), "send_to_collections"): func += 8
        scores["functional"] = min(100.0, float(func))

        # policy_compliance
        violations = 0
        if self._action_called(customer_actions("CUST-D"), "make_collection_call"): violations += 2
        if self._action_called(customer_actions("CUST-F"), "send_reminder_email"): violations += 1
        if self._action_called(customer_actions("CUST-C"), "make_collection_call"): violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 25.0)

        # escalation: CUST-D bankruptcy handled
        scores["escalation"] = 100.0 if (self._action_called(customer_actions("CUST-D"), "stop_collections") and
                                          self._action_called(customer_actions("CUST-D"), "file_proof_of_claim")) else 0.0

        # sequence: stop_collections before file_proof_of_claim for CUST-D
        stop_idx = next((i for i, a in enumerate(actions_log) if "CUST-D" in str(a) and (a.get("tool") or a.get("action")) == "stop_collections"), None)
        poc_idx = next((i for i, a in enumerate(actions_log) if "CUST-D" in str(a) and (a.get("tool") or a.get("action")) == "file_proof_of_claim"), None)
        scores["sequence"] = 100.0 if (stop_idx is not None and poc_idx is not None and stop_idx < poc_idx) else 50.0

        # arithmetic: CUST-E late fee = $15,400 * 1.5% = $231.00
        arith = 50
        for a in actions_log:
            if "CUST-E" in str(a) and ("231" in str(a) or "231.00" in str(a)): arith = 100; break
            if "charge_late_fee" in str(a.get("tool", "")) and "CUST-E" in str(a): arith = max(arith, 75)
        scores["arithmetic"] = float(arith)

        # hallucination: check for fabricated customers or amounts
        hallucination = 100.0
        if "CUST-G" in agent_output or "CUST-H" in agent_output: hallucination -= 30
        scores["hallucination"] = hallucination

        # communication: formal notice before escalating CUST-E
        formal_idx = next((i for i, a in enumerate(actions_log) if "CUST-E" in str(a) and (a.get("tool") or a.get("action")) == "send_formal_notice"), None)
        escalate_idx = next((i for i, a in enumerate(actions_log) if "CUST-E" in str(a) and (a.get("tool") or a.get("action")) in ["send_to_collections", "make_collection_call"]), None)
        if escalate_idx is None:
            scores["communication"] = 100.0  # didn't escalate prematurely
        elif formal_idx is not None and formal_idx < escalate_idx:
            scores["communication"] = 100.0
        else:
            scores["communication"] = 50.0

        return scores
