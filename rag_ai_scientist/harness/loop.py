"""The run loop: PLAN → EXECUTE → VALIDATE → CORRECT.

Four properties are the reason this module exists:

1. **Plan before work.** ``artifacts/plan.json`` (steps, commands, gates,
   remedies) is written and validated before any step runs.
2. **Gates decide.** No step reports success; the gates declared for it do.
   A gate type the harness does not implement is a failure, not a pass.
3. **Corrections are pre-declared.** CORRECT may only apply remedies the
   planner listed, and it re-plans (revision + 1) so every change is visible.
4. **Gaps are recorded, never guessed.** When a run cannot satisfy a gate it
   writes ``gap.md`` and stops with a non-zero exit code.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rag_ai_scientist.harness.config import HarnessConfig, load_config, write_config_yaml
from rag_ai_scientist.harness.gates import GateContext, GateResult, run_all_gates, run_step_gates
from rag_ai_scientist.harness.plan import Plan
from rag_ai_scientist.harness.planner import build_plan
from rag_ai_scientist.harness.rundir import RunDir, RunDirError, utc_now
from rag_ai_scientist.harness.steps import execute_step, find_golden_set

LOOP_PHASES = ("PLAN", "EXECUTE", "VALIDATE", "CORRECT", "DONE")


class LoopError(RuntimeError):
    """Raised when the loop cannot even start (bad config, missing corpus)."""


@dataclass
class RunResult:
    run: RunDir
    outcome: str
    iterations: int
    validation: dict[str, Any] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    steps: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.outcome == "ok"

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run.run_id,
            "run_dir": str(self.run.root),
            "outcome": self.outcome,
            "iterations": self.iterations,
            "all_gates_passed": bool(self.validation.get("all_passed")),
            "gaps": self.gaps,
            "steps": self.steps,
        }


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("rag-ai-scientist")
    except Exception:  # pragma: no cover - source checkout without metadata
        return "unknown"


def _git_commit(project_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - git absent
        return None
    commit = result.stdout.strip()
    return commit or None


def _input_files(config: HarnessConfig) -> tuple[list[dict[str, Any]], Path | None]:
    from rag_ai_scientist.core.text import file_hash, iter_corpus_files

    files = iter_corpus_files(config.project_root, config.corpus_paths, config.corpus_extensions)
    records: list[dict[str, Any]] = []
    for path in files:
        records.append(
            {
                "path": str(path),
                "relative_path": str(path.relative_to(config.project_root))
                if config.project_root in path.parents
                else str(path),
                "size": path.stat().st_size,
                "sha256": file_hash(path),
            }
        )
    try:
        golden = find_golden_set(config)
    except Exception:
        golden = None
    if golden is not None:
        records.append(
            {
                "path": str(golden),
                "relative_path": str(golden.relative_to(config.project_root))
                if config.project_root in golden.parents
                else str(golden),
                "size": golden.stat().st_size,
                "sha256": file_hash(golden),
                "role": "golden_set",
            }
        )
    return records, golden


def _manifest(
    *,
    run: RunDir,
    config: HarnessConfig,
    plan: Plan,
    skills: list[dict[str, Any]],
    input_files: list[dict[str, Any]],
    index_meta: dict[str, Any],
    iterations: int,
    outcome: str,
    validation: dict[str, Any] | None,
    state: dict[str, Any],
) -> dict[str, Any]:
    """The run record (PRD section 7). Providers that were not used are null."""
    lockfile = None
    for name in ("uv.lock", "requirements.txt"):
        candidate = config.project_root / name
        if candidate.exists():
            lockfile = {"path": name, "sha256": run.sha256(candidate)}
            break
    unresolved = (run.read_json(run.analysis_map_json) or {}).get("unresolved", [])
    return {
        "schema_version": 1,
        "run_id": run.run_id,
        "created_utc": state.get("started_utc"),
        "updated_utc": utc_now(),
        "package_version": _package_version(),
        "git_commit": _git_commit(config.project_root),
        "mode": config.mode,
        "run_name": config.run_name,
        "input": {
            "corpus_paths": config.corpus_paths,
            "corpus_extensions": config.corpus_extensions,
            "golden_set": next(
                (item["relative_path"] for item in input_files if item.get("role") == "golden_set"),
                None,
            ),
        },
        "input_files": input_files,
        "providers": {
            "embedder": None,
            "llm": None,
            "vector_store": {"name": index_meta.get("provider"), "revision": "1"},
            "executor": None,
        },
        "plan": {
            "path": run.run_rel(run.plan_json),
            "revision": plan.revision,
            "sha256": run.sha256(run.plan_json),
            "gates": plan.gate_ids,
        },
        "skills": skills,
        "prompts": [],
        "datasets": [
            {
                "path": doc.get("doc_path"),
                "sha256": doc.get("doc_hash"),
                "pages": doc.get("pages"),
                "chunks": doc.get("chunks"),
            }
            for doc in index_meta.get("docs", [])
        ],
        "environment": {
            **config.environment(),
            "lockfile": lockfile,
            "container": None,
        },
        "seeds": {"random": None, "note": "the retrieval-verification slice is deterministic"},
        "budgets": config.get("budgets", {}),
        "resource_limits": {"max_iterations": int(config.max_attempts)},
        "index": {
            "path": run.run_rel(run.index_dir),
            "provider": index_meta.get("provider"),
            "chunks": index_meta.get("chunk_count"),
            "docs": index_meta.get("doc_count"),
            "chunks_sha256": index_meta.get("chunks_sha256"),
            "chunk_params": index_meta.get("chunk_params"),
        },
        "validation": {
            "path": run.run_rel(run.validation_json),
            "all_passed": bool((validation or {}).get("all_passed")),
            "gates": [gate.get("gate_id") for gate in (validation or {}).get("gates", [])],
        },
        "report": {
            "path": run.run_rel(run.report_md),
            "sha256": run.sha256(run.report_md),
        },
        "steps": state.get("steps", {}),
        "iterations": iterations,
        "outcome": outcome,
        "unresolved": unresolved,
        "artifacts": {
            name: {"path": run.run_rel(path), "sha256": run.sha256(path)}
            for name, path in (
                ("config", run.config_yaml),
                ("state", run.state_json),
                ("plan", run.plan_json),
                ("index", run.index_dir / "index.json"),
                ("chunks", run.index_dir / "chunks.jsonl"),
                ("analysis_map", run.analysis_map_json),
                ("validation", run.validation_json),
                ("report", run.report_md),
                ("gap", run.gap_md),
            )
            if path.exists()
        },
        "reproduce": [
            f"ras index --config {run.run_rel(run.config_yaml)}",
            f"ras run --mode A-retrieval --config {run.run_rel(run.config_yaml)} --rerun",
        ],
        "applied_remedies": state.get("applied_remedies", []),
    }


def _validation_payload(
    results: list[GateResult],
    *,
    iteration: int,
    plan: Plan,
    report_finalized: bool = False,
) -> dict[str, Any]:
    gates = [result.as_dict() for result in results]
    failures = [gate["gate_id"] for gate in gates if not gate["passed"]]
    return {
        "schema_version": 1,
        "iteration": iteration,
        "plan_revision": plan.revision,
        "all_passed": not failures,
        "failures": failures,
        "gates": gates,
        "report_finalized_after_validation": report_finalized,
    }


def _write_gap(
    *,
    run: RunDir,
    config: HarnessConfig,
    plan: Plan,
    failing: list[GateResult],
    reason: str,
    applied: list[str],
) -> Path:
    lines = [
        f"# Gap report — {run.run_id}",
        "",
        f"Mode `{config.mode}` could not satisfy every gate. **{reason}**",
        "",
        "Nothing is reported as verified: the run stops here rather than guessing.",
        "",
        "## Failing gates",
        "",
        "| Gate | Step | Type | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for result in failing:
        detail = str(result.detail).replace("\n", " ")
        lines.append(
            f"| `{result.gate_id}` | `{result.step_id}` | {result.type} | {detail} |"
        )
    lines += ["", "## Proposed fixes", ""]
    for result in failing:
        step = plan.step(result.step_id)
        remedies = ", ".join(
            f"`{remedy.id}` ({remedy.description})" for remedy in (step.remedies if step else [])
        )
        lines.append(
            f"- `{result.gate_id}`: {result.proposed_fix or 'inspect the gate detail'} "
            f"— declared remedies: {remedies or 'none'}"
        )
    lines += [
        "",
        "## What was already tried",
        "",
        f"- Applied remedies: {', '.join(f'`{item}`' for item in applied) or 'none'}",
        f"- Plan revision: {plan.revision}",
        "",
        "## Next steps for a human",
        "",
        "1. Read the failing gate detail above and the per-step file in "
        f"`skills/{plan.name}/<step>.md`.",
        "2. Either widen the corpus or golden set, or declare a new remedy in the planner.",
        "3. Re-run with `--resume` once the cause is addressed; the run directory keeps the evidence.",
        "",
    ]
    return run.write_text(run.gap_md, "\n".join(lines))


def _index_meta(run: RunDir) -> dict[str, Any]:
    path = run.index_dir / "index.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _step_complete(state: dict[str, Any], step: Any, run: RunDir, plan: Plan) -> bool:
    record = (state.get("steps") or {}).get(step.id) or {}
    if record.get("status") not in ("ok", "resumed"):
        return False
    if int(record.get("plan_revision") or 0) != plan.revision:
        return False
    for produced in step.produces:
        if not (run.root / produced).exists():
            return False
    return True


def _first_failing_step(plan: Plan, results: list[GateResult]) -> str | None:
    failed = {result.step_id for result in results if not result.passed}
    for step in plan.steps:
        if step.id in failed:
            return step.id
    return None


def _choose_remedy(step: Any, applied: list[str]) -> Any | None:
    for remedy in step.remedies:
        if remedy.id not in applied:
            return remedy
    return None


def run_loop(
    *,
    project_root: Path,
    config: HarnessConfig | None = None,
    config_path: Path | None = None,
    mode: str | None = None,
    overrides: dict[str, Any] | None = None,
    run_id: str | None = None,
    resume: bool = False,
    max_iterations: int | None = None,
) -> RunResult:
    """Run one retrieval-verification loop and return its outcome."""
    from rag_ai_scientist.harness.planner import skill_inputs, skill_metadata
    from rag_ai_scientist.harness.skills import generate_skill, mirror_to_cursor

    project_root = Path(project_root).resolve()
    if config is None:
        config = load_config(
            project_root=project_root, config_path=config_path, mode=mode, overrides=overrides
        )

    if resume:
        if not run_id:
            raise LoopError("--resume needs a run id (or pass --run with the latest run).")
        run = RunDir.load(project_root, run_id)
        state = run.read_state()
    else:
        run = RunDir.create(project_root, config.run_name, run_id=run_id)
        state = {}

    applied: list[str] = list(state.get("applied_remedies", []))
    if state.get("config_overrides"):
        config = config.with_overrides(state["config_overrides"])
    if overrides:
        config = config.with_overrides(overrides)

    if not state:
        state = {
            "schema_version": 1,
            "run_id": run.run_id,
            "mode": config.mode,
            "started_utc": utc_now(),
            "config_sha256": config.sha256(),
            "config_overrides": {},
            "applied_remedies": [],
            "steps": {},
            "history": [],
            "phase": "PLAN",
        }
    state["config_overrides"] = config.overrides
    state["applied_remedies"] = applied

    write_config_yaml(config, run.config_yaml)
    input_files, _golden_path = _input_files(config)
    max_iterations = max_iterations or config.max_attempts
    max_steps = int(config.get("budgets.max_steps", 40))
    deadline = time.monotonic() + float(config.get("budgets.max_seconds", 900))

    iteration = int(state.get("iteration", 0))
    validation: dict[str, Any] | None = None
    results: list[GateResult] = []
    plan = build_plan(config, run.run_id)
    skills: list[dict[str, Any]] = []
    outcome = "ok"
    gaps: list[str] = []
    executed = 0

    while True:
        iteration += 1
        state["iteration"] = iteration
        state["phase"] = "PLAN"
        plan = build_plan(config, run.run_id)
        plan.save(run.plan_json)
        name, description = skill_metadata(config)
        generated = generate_skill(
            run=run,
            plan=plan,
            name=name,
            description=description,
            version=str(config.get("skills.version", "0.1.0")),
            plan_sha256=run.sha256(run.plan_json) or "",
            inputs=skill_inputs(config),
        )
        skills = [generated.as_dict(run=run)]
        if config.get("skills.mirror_to_cursor"):
            ok, message = mirror_to_cursor(project_root=project_root, skill=generated)
            run.log("skills", f"mirror_to_cursor ok={ok} message={message}")
            skills[0]["mirror"] = {"ok": ok, "message": message}
        state["skills"] = {
            "generated": skills,
            "resolved": (state.get("skills") or {}).get("resolved", {}),
        }
        run.write_state(state)
        stop = False

        # ---- EXECUTE ---------------------------------------------------
        state["phase"] = "EXECUTE"
        step_records = state.setdefault("steps", {})
        for step in plan.steps:
            if resume and _step_complete(state, step, run, plan):
                record = dict(step_records.get(step.id, {}))
                record["status"] = "resumed"
                step_records[step.id] = record
                run.log("loop", f"step {step.id}: skipped (already complete)")
                continue
            if executed >= max_steps:
                gaps.append(f"budget: more than {max_steps} step executions in one run")
                outcome = "gap"
                stop = True
                break
            if time.monotonic() > deadline:
                gaps.append("budget: wall-clock budget exhausted")
                outcome = "gap"
                stop = True
                break
            outcome_record = execute_step(
                step, run=run, config=config, plan=plan, skills=skills, validation=validation
            )
            executed += 1
            step_records[step.id] = {
                **outcome_record.as_dict(),
                "plan_revision": plan.revision,
                "iteration": iteration,
            }
            run.log("loop", f"step {step.id}: {outcome_record.message}")
            run.write_state(state)
        if stop:
            break

        # ---- VALIDATE --------------------------------------------------
        state["phase"] = "VALIDATE"
        run.write_state(state)
        context = GateContext(run=run, config=config, plan=plan, skills=skills)
        # The report is rendered *after* validation, so its gates are checked
        # once at finalization — failing them here would be a false negative.
        report_later = [step.id for step in plan.steps if step.id != "report"]
        results = run_all_gates(plan, context, only=report_later)
        validation = _validation_payload(results, iteration=iteration, plan=plan)
        run.write_json(run.validation_json, validation)
        for result in results:
            run.log(
                "validate",
                f"{'PASS' if result.passed else 'FAIL'} {result.gate_id} ({result.step_id}): "
                f"{result.detail}",
            )
        if validation["all_passed"]:
            break

        # ---- CORRECT ---------------------------------------------------
        state["phase"] = "CORRECT"
        failing_step_id = _first_failing_step(plan, results)
        failing = [result for result in results if not result.passed]
        failing_step = plan.step(failing_step_id) if failing_step_id else None
        remedy = _choose_remedy(failing_step, applied) if failing_step is not None else None
        state["history"].append(
            {
                "iteration": iteration,
                "plan_revision": plan.revision,
                "failures": [result.gate_id for result in failing],
                "remedy": remedy.id if remedy else None,
            }
        )
        if remedy is None or iteration >= max_iterations:
            gaps.append(
                f"gate(s) {', '.join(result.gate_id for result in failing)} still failing"
                + (" (no unused remedy declared)" if remedy is None else " (retry budget spent)")
            )
            outcome = "gap"
            run.write_state(state)
            break
        applied.append(remedy.id)
        config = config.with_overrides(remedy.overrides)
        state["applied_remedies"] = applied
        state["config_overrides"] = config.overrides
        run.log("correct", f"applying remedy {remedy.id} with {remedy.overrides}; re-planning")
        if any(str(key) == "index" or str(key).startswith("index.") for key in remedy.overrides):
            # The index itself changes, so everything downstream must run again.
            state["steps"] = {}
        else:
            keep: dict[str, Any] = {}
            for candidate in plan.steps:
                if candidate.id == failing_step_id:
                    break
                keep[candidate.id] = step_records.get(candidate.id, {})
            state["steps"] = keep
        run.write_state(state)

    # ---- finalize -----------------------------------------------------
    state["phase"] = "DONE"
    if validation is None:
        context = GateContext(run=run, config=config, plan=plan, skills=skills)
        results = run_all_gates(plan, context)
        validation = _validation_payload(results, iteration=iteration, plan=plan)
        run.write_json(run.validation_json, validation)
    report_step = plan.step("report")
    if report_step is not None:
        execute_step(
            report_step,
            run=run,
            config=config,
            plan=plan,
            skills=skills,
            validation=validation,
            outcome=outcome,
        )
        context = GateContext(run=run, config=config, plan=plan, skills=skills)
        report_results = run_step_gates(plan, "report", context)
        results = [result for result in results if result.step_id != "report"] + report_results
        validation = _validation_payload(
            results, iteration=iteration, plan=plan, report_finalized=True
        )
        if not validation["all_passed"] and outcome == "ok":
            outcome = "gap"
            gaps.append("report gates failed after finalization")
        run.write_json(run.validation_json, validation)

    if outcome == "gap":
        _write_gap(
            run=run,
            config=config,
            plan=plan,
            failing=[result for result in results if not result.passed],
            reason="; ".join(gaps) or "gate failure",
            applied=applied,
        )

    manifest = _manifest(
        run=run,
        config=config,
        plan=plan,
        skills=skills,
        input_files=input_files,
        index_meta=_index_meta(run),
        iterations=iteration,
        outcome=outcome,
        validation=validation,
        state=state,
    )
    state["outcome"] = outcome
    state["gaps"] = gaps
    run.write_state(state)
    manifest["state_sha256"] = run.sha256(run.state_json)
    run.write_manifest(manifest)
    run.log("loop", f"finished: outcome={outcome} iterations={iteration} steps={executed}")

    return RunResult(
        run=run,
        outcome=outcome,
        iterations=iteration,
        validation=validation or {},
        gaps=gaps,
        steps=state.get("steps", {}),
    )
