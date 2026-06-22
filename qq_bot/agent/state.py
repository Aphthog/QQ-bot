"""Agent state types: Intent, Step, Plan, AgentState, ReflectResult."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Intent(str, Enum):
    UNKNOWN = "unknown"
    CHAT = "chat"
    TASK = "task"
    COMMAND = "command"
    ADMIN = "admin"


class ReflectResult(str, Enum):
    DONE = "done"
    RETRY = "retry"
    REPLAN = "replan"


@dataclass
class Step:
    id: int
    action: str
    params: dict
    depends_on: list[int] = field(default_factory=list)

    def is_ready(self, completed_step_ids: set[int]) -> bool:
        return all(dep in completed_step_ids for dep in self.depends_on)

    def to_dict(self) -> dict:
        return {"id": self.id, "action": self.action, "params": self.params, "depends_on": self.depends_on}

    @classmethod
    def from_dict(cls, d: dict) -> Step:
        return cls(id=d["id"], action=d["action"], params=d["params"], depends_on=d.get("depends_on", []))


@dataclass
class Plan:
    steps: list[Step]
    condition: str | None = None

    def to_dict(self) -> dict:
        return {"steps": [s.to_dict() for s in self.steps], "condition": self.condition}

    @classmethod
    def from_dict(cls, d: dict) -> Plan:
        return cls(
            steps=[Step.from_dict(s) for s in d.get("steps", [])],
            condition=d.get("condition"),
        )


@dataclass
class AgentState:
    intent: Intent = Intent.UNKNOWN
    plan: Plan | None = None
    tool_results: list[dict] = field(default_factory=list)
    retry_count: int = 0
    final_text: str | None = None

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.value,
            "plan": self.plan.to_dict() if self.plan else None,
            "tool_results": self.tool_results,
            "retry_count": self.retry_count,
            "final_text": self.final_text,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AgentState:
        plan = Plan.from_dict(d["plan"]) if d.get("plan") else None
        return cls(
            intent=Intent(d.get("intent", "unknown")),
            plan=plan,
            tool_results=d.get("tool_results", []),
            retry_count=d.get("retry_count", 0),
            final_text=d.get("final_text"),
        )
