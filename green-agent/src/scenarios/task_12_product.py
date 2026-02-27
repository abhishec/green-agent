from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task12ProductScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_12",
        task_text="Create sprint plan for the OAuth/SSO epic across Sprint 1 and Sprint 2. Generate Jira tickets.",
        policy_doc=(
            "POLICY:\n"
            "1. Story dependencies must be respected — never schedule a story before its dependencies.\n"
            "2. Sprint capacity = raw team capacity adjusted by PTO. Sprint 1: Bob loses 4pts for PTO.\n"
            "3. Use velocity-adjusted capacity: (team_capacity / historical_team_capacity) × velocity_avg.\n"
            "4. Sprint 2 assumes full team availability unless otherwise noted.\n"
            "5. US-447 depends on BOTH US-441 and US-442 — cannot start until both complete.\n"
            "6. Flag risks when a story may not finish within sprint (especially dependencies at end of sprint).\n"
            "7. Each story must become a Jira ticket with: title, estimate, sprint assignment, dependencies, assigned engineer."
        ),
        tools_available=[
            "get_backlog", "get_team_capacity", "calculate_sprint_capacity",
            "create_jira_ticket", "assign_to_sprint", "flag_sprint_risk",
            "document_dependency_graph"
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_12_fixture.json"),
        expected_state={
            "sprint_1": {
                "stories": ["US-441", "US-442", "US-444", "US-445"],
                "total_points": 32,
                "capacity_used": 32,
                "velocity_adjusted_capacity": 35
            },
            "sprint_2": {
                "stories": ["US-443", "US-446", "US-447"],
                "total_points": 18
            },
            "risks_flagged": ["Bob PTO reduces Sprint 1 capacity", "US-446 may slip if US-442 not done by Mar 10"],
            "jira_tickets_created": 7,
        },
        dependency_graph={
            "assign_to_sprint": ["create_jira_ticket", "calculate_sprint_capacity"],
            "create_jira_ticket": ["get_backlog", "document_dependency_graph"],
        },
        irreversible_actions=["create_jira_ticket"],
        escalation_required=False,
    )

    def score(self, initial_db, final_db, actions_log, agent_output):
        scores = {}

        tickets = [a for a in actions_log if (a.get("tool") or a.get("action")) == "create_jira_ticket"]
        assignments = [a for a in actions_log if (a.get("tool") or a.get("action")) == "assign_to_sprint"]
        risks = [a for a in actions_log if (a.get("tool") or a.get("action")) == "flag_sprint_risk"]

        # functional: 7 tickets, correct sprint assignments, US-447 in sprint 2
        func = 0
        if len(tickets) >= 7: func += 25
        # US-441 in sprint 1
        if any("US-441" in str(a) and "sprint_1" in str(a).lower() for a in assignments): func += 15
        # US-447 in sprint 2 (depends on both US-441 AND US-442)
        if any("US-447" in str(a) and "sprint_2" in str(a).lower() for a in assignments): func += 20
        # US-443, US-446 in sprint 2 (depend on US-442)
        sprint2_correct = sum(1 for story in ["US-443", "US-446"] if any(story in str(a) and "sprint_2" in str(a).lower() for a in assignments))
        func += sprint2_correct * 10
        if len(risks) >= 1: func += 20
        scores["functional"] = min(100.0, float(func))

        # policy_compliance: no dependency violations
        violations = 0
        # US-442 assigned before US-441 = violation
        us441_sprint = None
        us442_sprint = None
        for a in assignments:
            a_str = str(a)
            if "US-441" in a_str:
                us441_sprint = "sprint_1" if "sprint_1" in a_str.lower() else "sprint_2"
            if "US-442" in a_str:
                us442_sprint = "sprint_1" if "sprint_1" in a_str.lower() else "sprint_2"
        if us442_sprint == "sprint_1" and us441_sprint != "sprint_1": violations += 1
        # US-447 in sprint 1 = violation
        if any("US-447" in str(a) and "sprint_1" in str(a).lower() for a in assignments): violations += 2
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 33.0)

        scores["escalation"] = 100.0

        # sequence: get backlog before create tickets
        get_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "get_backlog"), None)
        ticket_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "create_jira_ticket"), None)
        scores["sequence"] = 100.0 if (get_idx is not None and ticket_idx is not None and get_idx < ticket_idx) else 50.0

        # arithmetic: Sprint 1 capacity = (34/38) * 39.5 = 35.3 ≈ 35 pts; Sprint 1 stories = 13+8+8+3 = 32pts
        arith = 0
        output_str = agent_output + str(actions_log)
        if "35" in output_str: arith += 50
        if "32" in output_str: arith += 50
        scores["arithmetic"] = float(arith)

        # hallucination: check for fabricated story assignments or made-up team members
        hallucination = 100.0
        # Any story not in the backlog being created = hallucination
        valid_stories = {"US-441", "US-442", "US-443", "US-444", "US-445", "US-446", "US-447"}
        for t in tickets:
            story_id = t.get("params", {}).get("story_id", "") or t.get("story_id", "")
            if story_id and story_id not in valid_stories: hallucination -= 20
        scores["hallucination"] = max(0.0, hallucination)

        scores["communication"] = 100.0 if len(risks) >= 1 else 50.0

        return scores
