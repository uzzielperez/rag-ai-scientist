"""Execute a harness profile end-to-end (or a stage window)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from rag_ai_scientist.harness.base import Profile, Stage, StageResult
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
) -> dict:
    """Run selected stages; write a JSON summary under ``runs/<run_id>/``."""

    project_root = project_root.resolve()
    profile = get_profile(profile_name)
    stages = _select_stages(
        profile,
        from_stage=from_stage,
        until_stage=until_stage,
        include_optional=include_optional,
    )

    run_id = run_id or time.strftime("%Y%m%d_%H%M%S")
    run_dir = project_root / "runs" / f"harness_{profile.name}_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[StageResult] = []
    for stage in stages:
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
            continue

        result = _run_command(list(stage.command), cwd=project_root, timeout=timeout_s)
        result.name = stage.name
        result.detail = {
            "command": list(stage.command),
            "skill": stage.skill or profile.skill,
            "skill_step": stage.skill_step,
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
    return summary
