from __future__ import annotations
from pathlib import Path
from .base import BaseScenario, ScenarioMeta


class Task03OffboardingScenario(BaseScenario):
    meta = ScenarioMeta(
        task_id="task_03",
        task_text="Process full offboarding for Marcus Rodriguez terminating 2026-02-28.",
        policy_doc=(
            "POLICY:\n"
            "1. PTO payout rounds DOWN to nearest half-day (e.g., 11.3 days -> 11.0 days, NOT 11.5).\n"
            "2. PTO payout formula: rounded_days x (annual_salary / 260).\n"
            "3. Access revocation ORDER is mandatory: admin systems first (GitHub admin, AWS PowerUser, Salesforce admin), then communication tools (Slack), then security tools (1Password LAST).\n"
            "4. Physical assets must be returned and documented BEFORE final pay is processed.\n"
            "5. Benefits end on last day of termination month (Feb 28 = Feb month end).\n"
            "6. MacBook book value must be calculated and recorded at termination."
        ),
        tools_available=[
            "get_employee", "get_pto_balance", "revoke_access",
            "transfer_assets", "process_final_pay", "send_offboarding_checklist",
            "calculate_asset_book_value", "confirm_with_user"
        ],
        fixture_path=str(Path(__file__).parent.parent / "fixtures" / "task_03_fixture.json"),
        expected_state={
            "employees": [{"id": "EMP-MR", "status": "offboarded", "pto_payout": 4019.23}],
            "access_records": [
                {"id": "ACC-001", "status": "revoked"},
                {"id": "ACC-002", "status": "revoked"},
                {"id": "ACC-003", "status": "revoked"},
                {"id": "ACC-004", "status": "revoked"},
                {"id": "ACC-005", "status": "revoked"},
            ],
            "assets": [{"id": "ASSET-001", "status": "returned", "book_value_at_termination": 694.64}],
        },
        dependency_graph={
            "process_final_pay": ["transfer_assets", "revoke_access"],
            "revoke_access": ["get_employee"],
        },
        irreversible_actions=["revoke_access", "process_final_pay"],
        escalation_required=False,
    )

    def score(self, initial_db, final_db, actions_log, agent_output):
        scores = {}

        # functional: PTO payout correct (4019.23), correct book value (694.64), all access revoked, assets returned
        func = 0
        emp = next((e for e in final_db.get("employees", []) if e["id"] == "EMP-MR"), {})
        if self._float_eq(emp.get("pto_payout"), 4019.23): func += 30
        assets = {a["id"]: a for a in final_db.get("assets", [])}
        asset_001 = assets.get("ASSET-001", {})
        if self._float_eq(asset_001.get("book_value_at_termination"), 694.64): func += 20
        if asset_001.get("status") == "returned": func += 10
        all_revoked = all(
            next((a for a in final_db.get("access_records", []) if a["id"] == acc_id), {}).get("status") == "revoked"
            for acc_id in ["ACC-001","ACC-002","ACC-003","ACC-004","ACC-005"]
        )
        if all_revoked: func += 40
        scores["functional"] = min(100.0, float(func))

        # policy_compliance: 1Password must be last
        revocations = [a for a in actions_log if (a.get("tool") or a.get("action")) == "revoke_access"]
        violations = 0
        onepassword_idx = None
        github_idx = None
        for i, a in enumerate(actions_log):
            params = a.get("params", {})
            system = params.get("system", "")
            if "1password" in system.lower() or "1pass" in system.lower(): onepassword_idx = i
            if "github" in system.lower(): github_idx = i
        if onepassword_idx is not None and github_idx is not None and onepassword_idx < github_idx:
            violations += 1  # 1Password revoked before GitHub
        # assets before final pay
        asset_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "transfer_assets"), None)
        pay_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "process_final_pay"), None)
        if asset_idx is None or pay_idx is None or asset_idx >= pay_idx: violations += 1
        scores["policy_compliance"] = max(0.0, 100.0 - violations * 40.0)

        scores["escalation"] = 100.0

        # sequence: revoke before final pay
        scores["sequence"] = 100.0 if (asset_idx is not None and pay_idx is not None and asset_idx < pay_idx) else 0.0

        # arithmetic: PTO=11.3->11.0 * (95000/260) = 11.0 * 365.384... = 4019.23
        arith = 0
        if self._float_eq(emp.get("pto_payout"), 4019.23): arith += 60
        if self._float_eq(asset_001.get("book_value_at_termination"), 694.64): arith += 40
        scores["arithmetic"] = float(arith)

        scores["hallucination"] = 100.0

        # communication: confirm before irreversible
        confirm_idx = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "confirm_with_user"), None)
        first_revoke = next((i for i, a in enumerate(actions_log) if (a.get("tool") or a.get("action")) == "revoke_access"), None)
        scores["communication"] = 100.0 if (confirm_idx is not None and first_revoke is not None and confirm_idx < first_revoke) else 50.0

        return scores
