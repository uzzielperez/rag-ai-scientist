"""Execute a harness profile end-to-end (or a stage window)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from rag_ai_scientist.harness.base import Profile, Stage, StageResult
from rag_ai_scientist.harness.provenance import (
    build_run_manifest,
    capture_source_state,
    write_run_manifest,
)
from rag_ai_scientist.harness.registry import get_profile


def _select_stages(
    profile: Profile,
    *,
    from_stage: str | None,
    until_stage: str | None,
    include_optional: bool,
) -> list[Stage]:
    stages = list(profile.stages)
    start = profile.index_of(from_stage) if from_stage else 0
    end = profile.index_of(until_stage) if until_stage else len(stages) - 1
    if start > end:
        raise ValueError(f"--from {from_stage!r} is after --until {until_stage!r}")
    window = stages[start : end + 1]
    if not include_optional:
        window = [s for s in window if not s.optional]
    return window


def _run_command(cmd: list[str], *, cwd: Path, timeout: int | None) -> StageResult:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        return StageResult(
            name="",
            ok=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
    except subprocess.TimeoutExpired as exc:
        return StageResult(
            name="",
            ok=False,
            exit_code=124,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=f"Timed out after {timeout}s",
        )
    except FileNotFoundError as exc:
        return StageResult(name="", ok=False, exit_code=127, stderr=str(exc))


def run_harness(
    *,
    project_root: Path,
    profile_name: str = "whest",
    from_stage: str | None = None,
    until_stage: str | None = None,
    include_optional: bool = False,
    dry_run: bool = False,
    timeout_s: int | None = None,
    run_id: str | None = None,
    task_id: str | None = None,
    seed: int | None = None,
    config_paths: tuple[str, ...] = (),
    input_paths: tuple[str, ...] = (),
    dataset_ids: tuple[str, ...] = (),
    metrics: Mapping[str, Any] | None = None,
    artifact_paths: tuple[str, ...] = (),
    software_versions: Mapping[str, str] | None = None,
) -> dict:
    """Run selected stages and write a summary plus provenance manifest."""

    project_root = project_root.resolve()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    profile = get_profile(profile_name)
    stages = _select_stages(
        profile,
        from_stage=from_stage,
        until_stage=until_stage,
        include_optional=include_optional,
    )

    run_id = run_id or time.strftime("%Y%m%d_%H%M%S")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", run_id):
        raise ValueError("Run ID may contain only letters, numbers, dots, underscores, and hyphens.")
    source_state = capture_source_state(project_root)
    run_dir = project_root / "runs" / f"harness_{profile.name}_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[StageResult] = []
    for stage in stages:
        stage_started = time.perf_counter()
        if dry_run or stage.command is None:
            detail = {
                "command": list(stage.command) if stage.command else None,
                "rag_queries": list(stage.rag_queries),
                "skill": stage.skill or profile.skill,
                "skill_step": stage.skill_step,
                "description": stage.description,
                "dry_run": dry_run,
                "informational": stage.command is None,
            }
            results.append(
                StageResult(
                    name=stage.name,
                    ok=True,
                    skipped=True,
                    detail=detail,
                )
            )
            results[-1].detail["duration_seconds"] = round(time.perf_counter() - stage_started, 6)
            continue

        result = _run_command(list(stage.command), cwd=project_root, timeout=timeout_s)
        result.name = stage.name
        result.detail = {
            "command": list(stage.command),
            "skill": stage.skill or profile.skill,
            "skill_step": stage.skill_step,
            "duration_seconds": round(time.perf_counter() - stage_started, 6),
        }
        results.append(result)
        if not result.ok:
            break

    summary = {
        "profile": profile.name,
        "project_root": str(project_root),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "dry_run": dry_run,
        "include_optional": include_optional,
        "from_stage": from_stage,
        "until_stage": until_stage,
        "skill": profile.skill,
        "notes": profile.notes,
        "ok": all(r.ok for r in results),
        "stages": [r.as_dict() for r in results],
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    manifest = build_run_manifest(
        project_root=project_root,
        run_id=run_id,
        task_id=task_id,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="passed" if summary["ok"] else "failed",
        seed=seed,
        config_paths=config_paths,
        input_paths=input_paths,
        dataset_ids=dataset_ids,
        metrics=metrics,
        stages=summary["stages"],
        artifact_paths=(*artifact_paths, summary_path),
        software_versions=software_versions,
        source_state=source_state,
    )
    manifest_path = write_run_manifest(run_dir / "manifest.json", manifest)
    summary["manifest_path"] = str(manifest_path)
    return summary
