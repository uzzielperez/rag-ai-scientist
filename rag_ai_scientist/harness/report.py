"""The run report: ``report.md``.

The report is written from what is on disk — the plan, the analysis map, the
validation results, the generated skills — so it can be regenerated from a run
directory alone. It contains no wall-clock timestamps, which keeps a re-run of
the same inputs byte-comparable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rag_ai_scientist.harness.config import HarnessConfig
from rag_ai_scientist.harness.rundir import RunDir

REQUIRED_SECTIONS = (
    "Summary",
    "Corpus and index",
    "Plan",
    "Golden set coverage",
    "Unresolved",
    "Validation",
    "Generated skills",
    "Reproduce",
    "Artifacts",
)


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("rag-ai-scientist")
    except Exception:  # pragma: no cover - only when not installed
        return "unknown"


def _line(text: str) -> str:
    return text.replace("\n", " ").strip()


def _plan_table(plan: Any) -> list[str]:
    if plan is None:
        return ["_No plan recorded._", ""]
    lines = ["| # | Step | Kind | Command | Gates |", "| --- | --- | --- | --- | --- |"]
    for index, step in enumerate(plan.steps, start=1):
        gates = ", ".join(f"`{gate_id}`" for gate_id in step.gate_ids)
        lines.append(
            f"| {index} | `{step.id}` | {step.kind} | `{_line(step.command) or '-'}` | {gates} |"
        )
    lines.append("")
    return lines


def _coverage_table(analysis_map: dict[str, Any]) -> list[str]:
    items = analysis_map.get("items", []) if analysis_map else []
    if not items:
        return ["_No analysis map recorded._", ""]
    lines = [
        "| Question | Tier | Status | Result | Citations |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in items:
        citations = ", ".join(
            f"`{citation['file']}:p{citation['page']}:{citation['chunk_id']}`"
            for citation in item.get("evidence", [])[:2]
        ) or "—"
        lines.append(
            f"| `{item['id']}` {_line(item.get('question', ''))[:70]} | {item.get('tier')} | "
            f"{item.get('status')} | {item.get('result')} | {citations} |"
        )
    lines.append("")
    return lines


def _validation_table(validation: dict[str, Any] | None) -> list[str]:
    if not validation:
        return ["_Validation pending: written by the loop after the gates run._", ""]
    results = validation.get("gates", [])
    lines = ["| Gate | Step | Type | Result | Detail |", "| --- | --- | --- | --- | --- |"]
    for gate in results:
        mark = "PASS" if gate.get("passed") else "FAIL"
        lines.append(
            f"| `{gate.get('gate_id')}` | `{gate.get('step_id')}` | {gate.get('type')} | {mark} | "
            f"{_line(str(gate.get('detail', '')))} |"
        )
    lines += ["", f"All gates passed: **{bool(validation.get('all_passed'))}**", ""]
    return lines


def _skills_table(skills: list[dict[str, Any]], run: RunDir) -> list[str]:
    if not skills:
        return ["_No skill was generated for this run._", ""]
    lines = ["| Skill | Version | Source | Files | Gates |", "| --- | --- | --- | --- | --- |"]
    for record in skills:
        files = ", ".join(f"`{name}`" for name in sorted(record.get("files", {})))
        gates = ", ".join(f"`{gate}`" for gate in record.get("gates", []))
        lines.append(
            f"| `{record.get('name')}` | {record.get('version')} | "
            f"`{record.get('path', '')}` | {files} | {gates} |"
        )
    lines.append("")
    return lines


def render_report(
    *,
    run: RunDir,
    config: HarnessConfig,
    plan: Any = None,
    skills: list[dict[str, Any]] | None = None,
    validation: dict[str, Any] | None = None,
    outcome: str = "ok",
) -> str:
    """Render report.md for one run."""
    analysis_map = run.read_json(run.analysis_map_json) or {}
    manifest = run.read_manifest()
    index_meta: dict[str, Any] = {}
    index_json = run.index_dir / "index.json"
    if index_json.exists():
        try:
            import json

            index_meta = json.loads(index_json.read_text(encoding="utf-8"))
        except ValueError:
            index_meta = {}
    metrics = analysis_map.get("metrics", {}) if analysis_map else {}

    lines: list[str] = [f"# Run report — {run.run_id}", ""]
    lines += ["## Summary", ""]
    lines += [
        f"- Mode: `{config.mode}`",
        f"- Outcome: **{outcome}**",
        f"- Corpus documents: {index_meta.get('doc_count', 0)}",
        f"- Indexed chunks: {index_meta.get('chunk_count', 0)}",
        f"- Golden questions: {metrics.get('questions', 0)} "
        f"({metrics.get('supported', 0)} supported, {metrics.get('unresolved', 0)} unresolved)",
        f"- Unsourced claims: {metrics.get('unsupported_claims', 0)}",
    ]
    tier1 = metrics.get("tier1") or {}
    tier23 = metrics.get("tier23") or {}
    if tier1 or tier23:
        lines.append(
            f"- Tier 1: {tier1.get('passed', 0)}/{tier1.get('total', 0)} · "
            f"Tier 2/3: {tier23.get('passed', 0)}/{tier23.get('total', 0)}"
        )
    lines += ["", "## Corpus and index", ""]
    for doc in index_meta.get("docs", []):
        lines.append(
            f"- `{doc.get('doc_path')}` — {doc.get('pages')} pages, {doc.get('chunks')} chunks, "
            f"sha256 `{str(doc.get('doc_hash'))[:16]}`"
        )
    if not index_meta.get("docs"):
        lines.append("_No corpus documents recorded._")
    params = index_meta.get("chunk_params") or {}
    lines += [
        "",
        f"Retrieval: provider `{index_meta.get('provider', 'unknown')}`, "
        f"chunk_chars={params.get('chunk_chars')}, chunk_overlap={params.get('chunk_overlap')}, "
        f"top_k={config.top_k}, min_score={config.min_score}, min_terms={config.min_terms}.",
        f"Chunk fingerprint: `{index_meta.get('chunks_sha256')}`",
        "",
    ]
    lines += ["## Plan", ""]
    lines += _plan_table(plan)
    lines += ["## Golden set coverage", ""]
    golden = analysis_map.get("golden_set") or {}
    if golden:
        lines += [
            f"Golden set `{golden.get('name')}` ({golden.get('questions')} questions) from "
            f"`{golden.get('path')}`.",
            "",
        ]
    lines += _coverage_table(analysis_map)
    lines += ["## Unresolved", ""]
    unresolved = analysis_map.get("unresolved", []) if analysis_map else []
    if unresolved:
        for item in unresolved:
            lines.append(f"- `{item['id']}` (tier {item['tier']}): {_line(item['question'])} — {item['reason']}")
    else:
        lines.append("Nothing was left unresolved.")
    lines += ["", "## Validation", ""]
    lines += _validation_table(validation)
    lines += ["## Generated skills", ""]
    lines += _skills_table(skills or [], run)
    lines += ["## Reproduce", ""]
    lines += [
        "```bash",
        "# rebuild the index for this corpus",
        f"ras index --project-root {config.project_root}"
        + (f" --config {config.config_path}" if config.config_path else ""),
        "# re-run the loop (add --resume to keep completed steps)",
        f"ras run --mode {config.mode} --project-root {config.project_root}"
        + (f" --config {config.config_path}" if config.config_path else "")
        + " --resume",
        "# re-run the golden suite and store the result",
        f"ras eval --project-root {config.project_root}",
        "```",
        "",
        f"Given only this run directory, the cited chunks can be re-derived: "
        f"`chunks_sha256={index_meta.get('chunks_sha256')}`.",
        "",
    ]
    lines += ["## Artifacts", ""]
    artifacts: list[tuple[str, Path]] = [
        ("config", run.config_yaml),
        ("manifest", run.manifest_json),
        ("state", run.state_json),
        ("plan", run.plan_json),
        ("index", run.index_dir / "index.json"),
        ("chunks", run.index_dir / "chunks.jsonl"),
        ("analysis_map", run.analysis_map_json),
        ("validation", run.validation_json),
        ("report", run.report_md),
    ]
    lines += ["| Artifact | Path | sha256 | Bytes |", "| --- | --- | --- | --- |"]
    for name, path in artifacts:
        if not path.exists():
            continue
        digest = run.sha256(path) or ""
        lines.append(f"| {name} | `{run.run_rel(path)}` | `{digest[:16]}` | {path.stat().st_size} |")
    lines += ["", "## Environment", ""]
    environment = manifest.get("environment", {}) or config.environment()
    lines += [
        f"- rag-ai-scientist: {manifest.get('package_version', _package_version())}",
        f"- Python: {environment.get('python', 'unknown')}",
        f"- Platform: {environment.get('platform', 'unknown')}",
        f"- Retrieval provider: `{index_meta.get('provider', 'lexical-bm25')}` (no external model)",
        f"- Config sha256: `{config.sha256()[:16]}`",
        "",
    ]
    return "\n".join(lines)
