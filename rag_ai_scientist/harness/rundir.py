"""Run directories: the unit of record for one harness loop.

Everything a run produced lives under ``runs/<run_id>/`` (PRD section 7), so a
finished run can be inspected, diffed and partially replayed without the model
that generated it. Writes go through :meth:`RunDir.write_text` /
:meth:`RunDir.write_json`, which refuse to leave the run directory.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNS_DIRNAME = "runs"
STATE_SCHEMA_VERSION = 1
_SLUG = re.compile(r"[^a-z0-9]+")


class RunDirError(RuntimeError):
    """Raised when a run directory is missing, ambiguous or out of bounds."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str, *, limit: int = 32) -> str:
    cleaned = _SLUG.sub("-", text.strip().lower()).strip("-")
    return (cleaned or "run")[:limit]


def new_run_id(run_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    unique = datetime.now(timezone.utc).strftime("%f")[:4]
    return f"{stamp}-{_slug(run_name)}-{unique}"


@dataclass(frozen=True)
class RunDir:
    project_root: Path
    run_id: str
    root: Path

    @property
    def config_yaml(self) -> Path:
        return self.root / "config.yaml"

    @property
    def manifest_json(self) -> Path:
        return self.root / "manifest.json"

    @property
    def state_json(self) -> Path:
        return self.root / "state.json"

    @property
    def index_dir(self) -> Path:
        return self.root / "index"

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def plan_json(self) -> Path:
        return self.artifacts_dir / "plan.json"

    @property
    def analysis_map_json(self) -> Path:
        return self.artifacts_dir / "analysis_map.json"

    @property
    def validation_json(self) -> Path:
        return self.artifacts_dir / "validation.json"

    @property
    def report_md(self) -> Path:
        return self.root / "report.md"

    @property
    def gap_md(self) -> Path:
        return self.root / "gap.md"

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def rel(self, path: Path) -> str:
        try:
            return str(Path(path).resolve().relative_to(self.project_root))
        except ValueError:
            return str(path)

    def run_rel(self, path: Path) -> str:
        """Path relative to the run directory (falls back to the absolute path)."""
        try:
            return str(Path(path).resolve().relative_to(self.root))
        except ValueError:
            return str(path)

    # -- lifecycle -------------------------------------------------------
    @classmethod
    def create(cls, project_root: Path, run_name: str, run_id: str | None = None) -> "RunDir":
        project_root = Path(project_root).resolve()
        run_id = run_id or new_run_id(run_name)
        root = (project_root / RUNS_DIRNAME / run_id).resolve()
        if root.exists() and any(root.iterdir()):
            raise RunDirError(f"Run directory {root} already exists and is not empty.")
        for directory in (root, root / "index", root / "skills", root / "artifacts", root / "logs"):
            directory.mkdir(parents=True, exist_ok=True)
        return cls(project_root=project_root, run_id=run_id, root=root)

    @classmethod
    def load(cls, project_root: Path, run_id: str) -> "RunDir":
        project_root = Path(project_root).resolve()
        root = (project_root / RUNS_DIRNAME / run_id).resolve()
        if not root.is_dir():
            raise RunDirError(
                f"Run {run_id!r} not found under {project_root / RUNS_DIRNAME}. "
                f"Known runs: {', '.join(list_runs(project_root)) or 'none'}"
            )
        return cls(project_root=project_root, run_id=run_id, root=root)

    @classmethod
    def latest(cls, project_root: Path) -> "RunDir":
        runs = list_runs(Path(project_root))
        if not runs:
            raise RunDirError(f"No runs found under {Path(project_root) / RUNS_DIRNAME}.")
        return cls.load(project_root, runs[-1])

    # -- IO --------------------------------------------------------------
    def _guard(self, path: Path) -> Path:
        target = Path(path)
        if not target.is_absolute():
            target = self.root / target
        resolved = target.resolve()
        inside = resolved == self.root.resolve() or self.root.resolve() in resolved.parents
        if not inside:
            raise RunDirError(f"Refusing to write outside the run directory: {resolved}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def write_text(self, path: str | Path, text: str) -> Path:
        target = self._guard(Path(path))
        target.write_text(text, encoding="utf-8")
        return target

    def write_json(self, path: str | Path, payload: dict[str, Any]) -> Path:
        target = self._guard(Path(path))
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

    def read_json(self, path: str | Path) -> dict[str, Any] | None:
        target = Path(path)
        if not target.is_absolute():
            target = self.root / target
        if not target.exists():
            return None
        return json.loads(target.read_text(encoding="utf-8"))

    def sha256(self, path: str | Path) -> str | None:
        from rag_ai_scientist.core.text import file_hash

        target = Path(path)
        if not target.is_absolute():
            target = self.root / target
        return file_hash(target) if target.exists() else None

    # -- state and manifest ----------------------------------------------
    def read_state(self) -> dict[str, Any]:
        return self.read_json(self.state_json) or {}

    def write_state(self, state: dict[str, Any]) -> Path:
        payload = dict(state)
        payload.setdefault("schema_version", STATE_SCHEMA_VERSION)
        payload["updated_utc"] = utc_now()
        return self.write_json(self.state_json, payload)

    def read_manifest(self) -> dict[str, Any]:
        return self.read_json(self.manifest_json) or {}

    def write_manifest(self, manifest: dict[str, Any]) -> Path:
        return self.write_json(self.manifest_json, manifest)

    def log(self, name: str, message: str) -> None:
        target = self._guard(self.logs_dir / f"{name}.log")
        with target.open("a", encoding="utf-8") as handle:
            handle.write(f"{utc_now()} {message}\n")


def list_runs(project_root: Path) -> list[str]:
    runs_root = Path(project_root).resolve() / RUNS_DIRNAME
    if not runs_root.is_dir():
        return []
    return sorted(entry.name for entry in runs_root.iterdir() if entry.is_dir())
