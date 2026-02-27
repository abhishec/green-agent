from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task06SlaScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_06",
        task_text="TechCorp SLA is breaching. Assess and escalate INC-004.",
        policy_doc=(
            "POLICY:\n"
            "1. Excluded incidents (scheduled maintenance, maintenance windows) do NOT count toward SLA calculation.\n"
            "2. 99.9% uptime = maximum 43.8 minutes downtime per month.\n"
            "3. On-call quiet hours must be respected — check local time before paging.\n"
            "4. Both uptime AND latency SLA breaches must be documented in incident report.\n"
            "5. Client must be notified of SLA breach within 30 minutes of confirmation.\n"
            "6. Create formal incident report including both breach types."
        ),
        tools_available=[
            "get_sla_config", "get_incidents", "calculate_sla_breach",
            "check_oncall_availability", "page_oncall", "create_incident_report",
            "draft_client_notification", "post_status_update"
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_06_fixture.json"),
        expected_state={
            "incidents": [{"id": "INC-004", "status": "escalated", "sla_breach_confirmed": True, "breach_types": ["uptime", "latency"]}],
            "sla_breach": {"month_downtime_min": 131, "threshold_min": 43.8, "breached": True},
            "oncall_paged": "Alice Nguyen",
        },
        dependency_graph={
            "page_oncall": ["calculate_sla_breach", "check_oncall_availability"],
            "create_incident_report": ["calculate_sla_breach"],
            "draft_client_notification": ["create_incident_report"],
        },
        irreversible_actions=["page_oncall", "draft_client_notification"],
        escalation_required=True,
        escalation_trigger="SLA breached: 131 min downtime > 43.8 min threshold",
    )

    def score(self, initial_db, final_db, actions_log, agent_output):
        scores = {}

        # functional: correct downtime calc, Alice paged, both breach types documented
        func = 0
        if self._action_called(actions_log, "calculate_sla_breach"): func += 20
        # Check if correct downtime (37+94=131) was calculated
        for a in actions_log:
            params = a.get("params", {})
            if "131" in str(params) or "131" in str(a.get("result", "")): func += 20; break
        if self._action_called(actions_log, "page_oncall"): func += 20
        if self._action_called(actions_log, "create_incident_report"): func += 20
        if self._action_called(actions_log, "draft_client_notification"): func += 20
        scores["functional"] = min(100.0, float(func))

        # policy_compliance: excluded incidents not counted, alice paged (not in quiet hours at 16:04 UTC)
        violations = 0
        # If INC-001 or INC-003 were counted (excluded), that's a violation
        for a in actions_log:
            params_str = str(a.get("params", ""))
            if "INC-001" in params_str and "calculate" in str(a.get("tool", "")).lower(): violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 50.0)

        # escalation: oncall paged
        scores["escalation"] = 100.0 if self._action_called(actions_log, "page_oncall") else 0.0

        # sequence: calculate before page, create report before client notification
        calc_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "calculate_sla_breach"), None)
        page_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "page_oncall"), None)
        report_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "create_incident_report"), None)
        notify_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "draft_client_notification"), None)
        seq_ok = (calc_idx is not None and page_idx is not None and calc_idx < page_idx)
        if notify_idx and report_idx and report_idx >= notify_idx: seq_ok = False
        scores["sequence"] = 100.0 if seq_ok else 50.0

        # arithmetic: 37 + 94 = 131 min vs 43.8 threshold
        arith = 0
        for a in actions_log:
            full_str = str(a)
            if "131" in full_str: arith = 100; break
            if "43.8" in full_str: arith = max(arith, 50)
        scores["arithmetic"] = float(arith)

        scores["hallucination"] = 100.0

        scores["communication"] = 100.0 if self._action_called(actions_log, "draft_client_notification") else 50.0

        return scores
