from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task04InsuranceScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_04",
        task_text="Process insurance claim CLM-2026-0234 for Eleanor Vasquez.",
        policy_doc=(
            "POLICY:\n"
            "1. Fraud flag (>=3 claims in 18 months) triggers MANDATORY Enhanced Due Diligence (EDD) review -- NOT automatic denial.\n"
            "2. Sewer/drain rider covers sewer backup and drain backup ONLY -- does not apply to burst pipes.\n"
            "3. Deductible must always be subtracted before calculating approved amount.\n"
            "4. Grace period: if premium paid within grace period, policy remains active -- do NOT lapse.\n"
            "5. Claims cannot be approved while EDD is pending -- note 'approved pending EDD clearance'.\n"
            "6. Document reason for all decisions (EDD trigger, rider exclusion)."
        ),
        tools_available=[
            "get_claim", "get_policy", "get_rider", "check_fraud_flag",
            "initiate_edd_review", "approve_claim_partial", "deny_claim",
            "schedule_inspection", "flag_for_review", "document_decision"
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_04_fixture.json"),
        expected_state={
            "claims": [{"id": "CLM-2026-0234", "status": "edd_review", "approved_amount_pending": 11250.00, "rider_applied": False, "edd_initiated": True}]
        },
        dependency_graph={
            "initiate_edd_review": ["check_fraud_flag"],
            "approve_claim_partial": ["get_policy", "get_rider", "initiate_edd_review"],
        },
        irreversible_actions=["approve_claim_partial", "deny_claim"],
        escalation_required=True,
        escalation_trigger="3 claims in 18 months triggers mandatory EDD review",
    )

    def score(self, initial_db, final_db, actions_log, agent_output):
        scores = {}

        # functional: EDD initiated (not denied), correct amount, rider not applied
        func = 0
        claim = next((c for c in final_db.get("claims", []) if c["id"] == "CLM-2026-0234"), {})
        if claim.get("edd_initiated") or self._action_called(actions_log, "initiate_edd_review"): func += 35
        if not self._action_called(actions_log, "deny_claim"): func += 20  # must NOT deny
        if self._float_eq(claim.get("approved_amount_pending"), 11250.00): func += 25  # 12750 - 1500 deductible
        if not claim.get("rider_applied", True): func += 20  # rider must NOT be applied
        scores["functional"] = min(100.0, float(func))

        # policy_compliance: EDD not denial, rider correctly excluded, grace period correctly handled
        violations = 0
        if self._action_called(actions_log, "deny_claim"): violations += 2  # major violation
        rider_applied = claim.get("rider_applied", False)
        if rider_applied: violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 33.0)

        # escalation: EDD initiated
        scores["escalation"] = 100.0 if self._action_called(actions_log, "initiate_edd_review") else 0.0

        # sequence: check_fraud_flag before initiate_edd_review
        fraud_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "check_fraud_flag"), None)
        edd_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "initiate_edd_review"), None)
        scores["sequence"] = 100.0 if (fraud_idx is not None and edd_idx is not None and fraud_idx < edd_idx) else 50.0

        # arithmetic: 12750 - 1500 = 11250
        scores["arithmetic"] = 100.0 if self._float_eq(claim.get("approved_amount_pending"), 11250.00) else 0.0

        scores["hallucination"] = 100.0

        # communication: document_decision called
        scores["communication"] = 100.0 if self._action_called(actions_log, "document_decision") else 50.0

        return scores
