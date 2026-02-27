from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task02ProcurementScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_02",
        task_text="Process purchase request PR-2024-0891 for AWS Reserved Instances $47,500.",
        policy_doc=(
            "POLICY:\n"
            "1. Delegation chain must be followed in order — skip-level escalation requires written justification.\n"
            "2. If approver is on PTO, delegation activates automatically (check PTO records).\n"
            "3. Multi-year contracts (>1 year) require legal sign-off BEFORE VP approval.\n"
            "4. VP approvals expire in 48 hours — deadline must be set.\n"
            "5. Requester must be notified of all escalations.\n"
            "6. Budget must be checked before approval."
        ),
        tools_available=[
            "get_purchase_request", "get_approval_chain", "get_budget",
            "check_employee_pto", "escalate_to", "flag_legal_review",
            "set_approval_deadline", "send_notification", "approve_request"
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_02_fixture.json"),
        expected_state={
            "purchase_requests": [{"id": "PR-2024-0891", "status": "pending_vp_approval", "legal_review_flagged": True, "vp_deadline_set": True}]
        },
        dependency_graph={
            "escalate_to": ["check_employee_pto", "get_approval_chain"],
            "flag_legal_review": ["escalate_to"],
            "set_approval_deadline": ["escalate_to"],
            "send_notification": ["escalate_to"],
        },
        irreversible_actions=["escalate_to", "flag_legal_review", "send_notification"],
        escalation_required=True,
        escalation_trigger="Amount $47,500 exceeds Jennifer Walsh's $50,000 limit — must escalate to VP",
    )

    def score(self, initial_db, final_db, actions_log, agent_output):
        scores = {}
        called = self._actions_called(actions_log)

        # functional: correct delegation chain followed
        func = 0
        # must have checked PTO for David Park
        if self._action_called(actions_log, "check_employee_pto"): func += 20
        # must escalate to jennifer_walsh (not david directly or skip to VP)
        escalations = [a for a in actions_log if (a.get("tool") or a.get("action")) == "escalate_to"]
        escalate_targets = [a.get("params", {}).get("to") or a.get("to", "") for a in escalations]
        if any("jennifer" in str(t).lower() or "walsh" in str(t).lower() for t in escalate_targets): func += 20
        if any("vp" in str(t).lower() or "robert" in str(t).lower() or "chen" in str(t).lower() for t in escalate_targets): func += 20
        if self._action_called(actions_log, "flag_legal_review"): func += 20
        if self._action_called(actions_log, "set_approval_deadline"): func += 10
        if self._action_called(actions_log, "send_notification"): func += 10
        scores["functional"] = min(100.0, float(func))

        # policy_compliance: correct chain order
        violations = 0
        jennifer_idx = next((i for i, a in enumerate(actions_log) if "walsh" in str(a).lower() or "jennifer" in str(a).lower()), None)
        vp_idx = next((i for i, a in enumerate(actions_log) if "robert" in str(a).lower() or "vp" in str(a).lower()), None)
        legal_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "flag_legal_review"), None)
        if vp_idx and jennifer_idx and jennifer_idx > vp_idx: violations += 1  # skipped jennifer
        if vp_idx and legal_idx and legal_idx > vp_idx: violations += 1  # legal must precede VP
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 40.0)

        # escalation
        scores["escalation"] = 100.0 if (len(escalations) >= 2) else 0.0

        # sequence
        pto_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "check_employee_pto"), None)
        first_escalate = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "escalate_to"), None)
        scores["sequence"] = 100.0 if (pto_idx is not None and first_escalate is not None and pto_idx < first_escalate) else 50.0

        # arithmetic: $47,500 > David Park's $25K limit. David on PTO → Jennifer Walsh (limit $50K).
        # $47,500 < $50,000 so Jennifer CAN approve. Trap: naive agent escalates to VP but Jennifer can handle it.
        # Correct math: Jennifer approves (47500 < 50000). Score if agent stops at Jennifer.
        scores["arithmetic"] = 100.0 if any("jennifer" in str(t).lower() or "walsh" in str(t).lower() for t in escalate_targets) else 0.0

        scores["hallucination"] = 100.0

        # communication: requester notified
        scores["communication"] = 100.0 if self._action_called(actions_log, "send_notification") else 0.0

        return scores
