from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task14IncidentScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_14",
        task_text="Investigate INC-2026-0312, identify root cause, generate RCA document and change request.",
        policy_doc=(
            "POLICY:\n"
            "1. Root cause analysis must trace the full causal chain, not just the symptom.\n"
            "2. Submit both immediate (hotfix) AND permanent (architectural) change requests.\n"
            "3. Post status update to incident ticket as soon as root cause is identified.\n"
            "4. Document all investigated deployments, including those ruled out (with reasoning).\n"
            "5. RCA document must include: root cause, contributing factors, red herrings ruled out, timeline.\n"
            "6. Change requests must specify service, action, and urgency (P1=immediate)."
        ),
        tools_available=[
            "get_incident", "get_deployments", "get_logs", "get_product_history",
            "create_rca_document", "submit_change_request", "post_status_update",
            "rollback_deployment", "flush_cache", "notify_stakeholders"
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_14_fixture.json"),
        expected_state={
            "incident": {"id": "INC-2026-0312", "root_cause_identified": True, "status": "investigating"},
            "rca_created": True,
            "change_requests": [
                {"type": "hotfix", "action": "flush_redis_product_cache"},
                {"type": "architectural", "action": "cache_invalidation_on_price_update"},
            ],
        },
        dependency_graph={
            "create_rca_document": ["get_deployments", "get_logs", "get_product_history"],
            "submit_change_request": ["create_rca_document"],
            "post_status_update": ["create_rca_document"],
        },
        irreversible_actions=["rollback_deployment", "flush_cache"],
        escalation_required=False,
    )

    def score(self, initial_db, final_db, actions_log, agent_output):
        scores = {}

        # functional: RCA created, correct root cause (DEPLOY-B / Redis cache), DEPLOY-A ruled out as red herring, 2 CRs
        func = 0
        if self._action_called(actions_log, "create_rca_document"): func += 20
        rca_actions = [a for a in actions_log if (a.get("tool") or a.get("action")) == "create_rca_document"]
        # Root cause: DEPLOY-B / Redis / stale cache
        rca_str = str(rca_actions) + agent_output
        if "DEPLOY-B" in rca_str and ("cache" in rca_str.lower() or "redis" in rca_str.lower()): func += 25
        # DEPLOY-A correctly ruled out
        if "DEPLOY-A" in rca_str and ("red herring" in rca_str.lower() or "unrelated" in rca_str.lower() or "not" in rca_str.lower()): func += 15
        crs = [a for a in actions_log if (a.get("tool") or a.get("action")) == "submit_change_request"]
        if len(crs) >= 2: func += 20
        if self._action_called(actions_log, "post_status_update"): func += 20
        scores["functional"] = min(100.0, float(func))

        # policy_compliance: both CRs submitted (hotfix + architectural), status posted
        violations = 0
        cr_types = [c.get("params", {}).get("type", "") or c.get("type", "") for c in crs]
        if not any("hotfix" in str(t).lower() or "immediate" in str(t).lower() for t in cr_types): violations += 1
        if not any("arch" in str(t).lower() or "permanent" in str(t).lower() for t in cr_types): violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 50.0)

        scores["escalation"] = 100.0

        # sequence: get logs/deployments before RCA
        log_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_logs"), None)
        rca_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "create_rca_document"), None)
        scores["sequence"] = 100.0 if (log_idx is not None and rca_idx is not None and log_idx < rca_idx) else 50.0

        scores["arithmetic"] = 100.0  # no numeric calculations required

        # hallucination: check for fabricated root cause
        hallucination = 100.0
        # If DEPLOY-C is blamed as root cause (it's contributing, not root), partial penalty
        if "DEPLOY-C" in agent_output and "root cause" in agent_output.lower():
            # DEPLOY-C is a contributing factor, not root cause — partial hallucination
            if "DEPLOY-B" not in agent_output: hallucination -= 30
        # If DEPLOY-A is blamed as root cause (it's a red herring)
        if "DEPLOY-A" in agent_output and "root cause" in agent_output.lower():
            if "unrelated" not in agent_output.lower() and "red herring" not in agent_output.lower():
                hallucination -= 40
        scores["hallucination"] = max(0.0, hallucination)

        scores["communication"] = 100.0 if self._action_called(actions_log, "post_status_update") else 50.0

        return scores
