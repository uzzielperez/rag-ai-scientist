from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence


@dataclass(frozen=True)
class Stage:
    """One step in a challenge loop."""

    name: str
    description: str
    # Shell argv relative to project_root, or None for informational-only stages.
    command: Sequence[str] | None = None
    # Optional callable for Python-side stages (receives project_root Path as str).
    action: Callable[[str], dict] | None = None
    optional: bool = False
    rag_queries: tuple[str, ...] = ()
    skill: str | None = None
    skill_step: str | None = None


@dataclass(frozen=True)
class Profile:
    """Named challenge / research loop definition."""

    name: str
    description: str
    stages: tuple[Stage, ...]
    skill: str
    default_project_hint: str = ""
    notes: str = ""

    def stage_names(self) -> list[str]:
        return [s.name for s in self.stages]

    def index_of(self, name: str) -> int:
        for i, stage in enumerate(self.stages):
            if stage.name == name:
                return i
        raise KeyError(f"Unknown stage {name!r} for profile {self.name!r}. Known: {self.stage_names()}")


@dataclass
class StageResult:
    name: str
    ok: bool
    skipped: bool = False
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "ok": self.ok,
            "skipped": self.skipped,
            "exit_code": self.exit_code,
            "stdout_tail": self.stdout[-2000:],
            "stderr_tail": self.stderr[-2000:],
            "detail": self.detail,
        }
