from __future__ import annotations
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ScenarioMeta:
    task_id: str
    task_text: str
    policy_doc: str
    tools_available: list[str]
    fixture_path: str
    expected_state: dict[str, Any]
    dependency_graph: dict[str, list[str]]   # action -> [must_come_before]
    irreversible_actions: list[str]
    escalation_required: bool
    escalation_trigger: str = ""


class BaseScenario(ABC):
    meta: ScenarioMeta

    # ── Convenience property accessors ──────────────────────────────────────
    @property
    def task_id(self) -> str:
        return self.meta.task_id

    @property
    def task_text(self) -> str:
        return self.meta.task_text

    @property
    def policy_doc(self) -> str:
        return self.meta.policy_doc

    @property
    def tools_available(self) -> list[str]:
        return self.meta.tools_available

    @property
    def fixture_path(self) -> str:
        return self.meta.fixture_path

    def load_fixture(self) -> dict[str, Any]:
        """Load and return the fixture JSON for this scenario."""
        return json.loads(Path(self.meta.fixture_path).read_text())

    @abstractmethod
    def score(
        self,
        initial_db: dict[str, Any],
        final_db: dict[str, Any],
        actions_log: list[dict[str, Any]],
        agent_output: str,
    ) -> dict[str, float]:
        """Return 7 dimension scores each 0.0-100.0."""
        ...

    def _action_called(self, actions_log: list, name: str) -> bool:
        return any(a.get("tool") == name or a.get("action") == name for a in actions_log)

    def _actions_called(self, actions_log: list) -> list[str]:
        return [a.get("tool") or a.get("action") for a in actions_log if a.get("tool") or a.get("action")]

    def _db_value(self, db: dict, table: str, id_key: str, id_val: str, col: str):
        rows = db.get(table, [])
        for r in rows:
            if r.get(id_key) == id_val:
                return r.get(col)
        return None

    def _float_eq(self, a, b, tol=0.01) -> bool:
        try:
            return abs(float(a) - float(b)) <= tol
        except (TypeError, ValueError):
            return False
