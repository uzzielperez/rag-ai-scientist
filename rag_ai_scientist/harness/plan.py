"""``artifacts/plan.json``: the machine-readable plan a run executes.

A plan is data, not code. The loop executes it, VALIDATE runs the gates it
declares, and the generated skill (§4c) is the human-readable projection of the
same object. Keeping one source of truth is what lets VALIDATE reject a skill
that claims a gate the harness does not enforce.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PLAN_SCHEMA_VERSION = 1


class PlanError(RuntimeError):
    """Raised when a plan is malformed or inconsistent."""


@dataclass
class GateSpec:
    id: str
    type: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "params": self.params,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GateSpec":
        return cls(
            id=str(data["id"]),
            type=str(data["type"]),
            params=dict(data.get("params") or {}),
            description=str(data.get("description", "")),
        )


@dataclass
class Remedy:
    """A pre-declared correction the CORRECT phase may apply to a failed step."""

    id: str
    description: str
    overrides: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "description": self.description, "overrides": self.overrides}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Remedy":
        return cls(
            id=str(data["id"]),
            description=str(data.get("description", "")),
            overrides=dict(data.get("overrides") or {}),
        )


@dataclass
class PlanStep:
    id: str
    name: str
    kind: str
    description: str
    command: str
    produces: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    gates: list[GateSpec] = field(default_factory=list)
    remedies: list[Remedy] = field(default_factory=list)

    @property
    def gate_ids(self) -> list[str]:
        return [gate.id for gate in self.gates]

    def gate(self, gate_id: str) -> GateSpec | None:
        for gate in self.gates:
            if gate.id == gate_id:
                return gate
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "command": self.command,
            "produces": self.produces,
            "reads": self.reads,
            "gates": [gate.as_dict() for gate in self.gates],
            "remedies": [remedy.as_dict() for remedy in self.remedies],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanStep":
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            kind=str(data["kind"]),
            description=str(data.get("description", "")),
            command=str(data.get("command", "")),
            produces=[str(item) for item in data.get("produces", [])],
            reads=[str(item) for item in data.get("reads", [])],
            gates=[GateSpec.from_dict(item) for item in data.get("gates", [])],
            remedies=[Remedy.from_dict(item) for item in data.get("remedies", [])],
        )


@dataclass
class Plan:
    mode: str
    run_id: str
    name: str
    steps: list[PlanStep]
    revision: int = 1
    planner: str = "deterministic"
    notes: list[str] = field(default_factory=list)

    @property
    def gate_ids(self) -> list[str]:
        return [gate_id for step in self.steps for gate_id in step.gate_ids]

    def step(self, step_id: str) -> PlanStep | None:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def bumped(self, note: str) -> "Plan":
        return Plan(
            mode=self.mode,
            run_id=self.run_id,
            name=self.name,
            steps=list(self.steps),
            revision=self.revision + 1,
            planner=self.planner,
            notes=[*self.notes, note],
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "mode": self.mode,
            "run_id": self.run_id,
            "name": self.name,
            "revision": self.revision,
            "planner": self.planner,
            "notes": self.notes,
            "steps": [step.as_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        return cls(
            mode=str(data["mode"]),
            run_id=str(data["run_id"]),
            name=str(data["name"]),
            steps=[PlanStep.from_dict(item) for item in data.get("steps", [])],
            revision=int(data.get("revision", 1)),
            planner=str(data.get("planner", "deterministic")),
            notes=[str(item) for item in data.get("notes", [])],
        )

    def validate(self) -> None:
        if not self.steps:
            raise PlanError("Plan has no steps.")
        seen_steps: set[str] = set()
        seen_gates: set[str] = set()
        for step in self.steps:
            if step.id in seen_steps:
                raise PlanError(f"Duplicate step id {step.id!r} in plan.")
            seen_steps.add(step.id)
            if not step.gates:
                raise PlanError(f"Step {step.id!r} declares no gate; every step must be gated.")
            for gate in step.gates:
                if gate.id in seen_gates:
                    raise PlanError(f"Duplicate gate id {gate.id!r} in plan.")
                seen_gates.add(gate.id)
                if not gate.type:
                    raise PlanError(f"Gate {gate.id!r} has no type.")

    def save(self, path: Path) -> Path:
        self.validate()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, path: Path) -> "Plan":
        if not Path(path).exists():
            raise PlanError(f"No plan at {path}.")
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
