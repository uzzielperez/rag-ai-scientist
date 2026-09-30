"""Gates: the code that decides whether a step passed.

A gate is the only thing in the harness allowed to say "this is fine". Gates
are declared in ``plan.json``, executed here, and their results are written to
``artifacts/validation.json`` and ``manifest.json``. An unknown gate type is a
failure, never a silent pass: that is what makes the §4c.2 coupling real.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rag_ai_scientist.harness.plan import GateSpec, Plan
from rag_ai_scientist.harness.rundir import RunDir

SUPPORTED_STATUS = ("supported", "unresolved")


class GateError(RuntimeError):
    """Raised for malformed gate declarations."""


@dataclass
class GateResult:
    gate_id: str
    step_id: str
    type: str
    passed: bool
    detail: str = ""
    measured: dict[str, Any] = field(default_factory=dict)
    proposed_fix: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "step_id": self.step_id,
            "type": self.type,
            "passed": self.passed,
            "detail": self.detail,
            "measured": self.measured,
            "proposed_fix": self.proposed_fix,
        }


@dataclass
class GateContext:
    run: RunDir
    config: Any
    plan: Plan
    skills: list[dict[str, Any]] = field(default_factory=list)

    def resolve(self, path: str | Path) -> Path:
        """Resolve a run-relative path; absolute paths and escapes are rejected."""
        candidate = Path(path)
        if candidate.is_absolute():
            raise ValueError(f"Gate paths must be relative to the run directory: {candidate}")
        if ".." in candidate.parts:
            raise ValueError(f"Gate paths must not escape the run directory: {candidate}")
        return self.run.root / candidate


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def gate_file_exists(spec: GateSpec, context: GateContext) -> GateResult:
    paths = [str(item) for item in spec.params.get("paths", [])]
    if not paths and spec.params.get("path"):
        paths = [str(spec.params["path"])]
    if not paths:
        raise GateError("file_exists needs `paths`")
    missing: list[str] = []
    empty: list[str] = []
    sizes: dict[str, int] = {}
    for raw in paths:
        target = context.resolve(raw)
        if not target.exists():
            missing.append(raw)
            continue
        size = target.stat().st_size
        sizes[raw] = size
        if size == 0:
            empty.append(raw)
    passed = not missing and not empty
    detail = "all declared artifacts exist"
    if missing:
        detail = f"missing: {', '.join(missing)}"
    elif empty:
        detail = f"empty: {', '.join(empty)}"
    return GateResult(
        gate_id=spec.id,
        step_id="",
        type=spec.type,
        passed=passed,
        detail=detail,
        measured={"sizes": sizes},
    )


def gate_json_keys(spec: GateSpec, context: GateContext) -> GateResult:
    raw_path = str(spec.params.get("path", ""))
    keys = [str(item) for item in spec.params.get("keys", [])]
    target = context.resolve(raw_path)
    if not target.exists():
        return GateResult(spec.id, "", spec.type, False, f"{raw_path} does not exist")
    data = _read_json(target)
    missing = [key for key in keys if key not in data]
    detail = (
        f"{raw_path} is missing {', '.join(missing)}" if missing else f"{raw_path} has all required keys"
    )
    return GateResult(
        gate_id=spec.id,
        step_id="",
        type=spec.type,
        passed=not missing,
        detail=detail,
        measured={"present": sorted(data), "missing": missing},
    )


def gate_json_min_items(spec: GateSpec, context: GateContext) -> GateResult:
    raw_path = str(spec.params.get("path", ""))
    key = str(spec.params.get("key", "items"))
    minimum = int(spec.params.get("min", 1))
    target = context.resolve(raw_path)
    if not target.exists():
        return GateResult(spec.id, "", spec.type, False, f"{raw_path} does not exist")
    data = _read_json(target)
    items = data.get(key)
    if not isinstance(items, list):
        return GateResult(spec.id, "", spec.type, False, f"{raw_path}:{key} is not a list")
    return GateResult(
        gate_id=spec.id,
        step_id="",
        type=spec.type,
        passed=len(items) >= minimum,
        detail=f"{raw_path}:{key} has {len(items)} entries (minimum {minimum})",
        measured={key: len(items), "minimum": minimum},
    )


def gate_index_integrity(spec: GateSpec, context: GateContext) -> GateResult:
    from rag_ai_scientist.core.retrieval import RetrievalError, load_index

    index_dir = context.resolve(str(spec.params.get("index_dir", "index")))
    expect_hash = spec.params.get("expect_hash")
    try:
        index = load_index(index_dir, verify=True)
    except (RetrievalError, OSError, ValueError) as exc:
        return GateResult(spec.id, "", spec.type, False, f"index unusable: {exc}")
    problems: list[str] = []
    if len(index) == 0:
        problems.append("index has no chunks")
    if expect_hash and index.meta.get("chunks_sha256") != expect_hash:
        problems.append(f"chunks_sha256 is {index.meta.get('chunks_sha256')}, expected {expect_hash}")
    return GateResult(
        gate_id=spec.id,
        step_id="",
        type=spec.type,
        passed=not problems,
        detail="; ".join(problems)
        or f"index verified ({len(index)} chunks, docs={index.meta.get('doc_count')})",
        measured={
            "chunks": len(index),
            "docs": index.meta.get("doc_count"),
            "chunks_sha256": index.meta.get("chunks_sha256"),
        },
    )


def gate_index_deterministic(spec: GateSpec, context: GateContext) -> GateResult:
    """Re-index the same corpus into a scratch directory and compare fingerprints."""
    from rag_ai_scientist.core.retrieval import RetrievalError, build_index, load_index

    index_dir = context.resolve(str(spec.params.get("index_dir", "index")))
    try:
        original = load_index(index_dir, verify=True)
    except (RetrievalError, OSError, ValueError) as exc:
        return GateResult(spec.id, "", spec.type, False, f"index unusable: {exc}")
    with tempfile.TemporaryDirectory(prefix="ras-determinism-") as scratch:
        try:
            rebuilt = build_index(
                project_root=context.config.project_root,
                paths=context.config.corpus_paths,
                index_dir=Path(scratch),
                extensions=context.config.corpus_extensions,
                chunk_chars=context.config.chunk_chars,
                chunk_overlap=context.config.chunk_overlap,
            )
        except (RetrievalError, OSError, ValueError) as exc:
            return GateResult(spec.id, "", spec.type, False, f"rebuild failed: {exc}")
    same_hash = original.meta.get("chunks_sha256") == rebuilt.meta.get("chunks_sha256")
    same_ids = [chunk.chunk_id for chunk in original.chunks] == [
        chunk.chunk_id for chunk in rebuilt.chunks
    ]
    return GateResult(
        gate_id=spec.id,
        step_id="",
        type=spec.type,
        passed=same_hash and same_ids,
        detail=(
            "rebuild produced identical chunks and identifiers"
            if same_hash and same_ids
            else f"rebuild diverged (hash_equal={same_hash}, ids_equal={same_ids})"
        ),
        measured={
            "chunks_sha256": original.meta.get("chunks_sha256"),
            "rebuilt_sha256": rebuilt.meta.get("chunks_sha256"),
        },
    )


def _load_items(spec: GateSpec, context: GateContext) -> tuple[list[dict[str, Any]], str]:
    raw_path = str(spec.params.get("path", "artifacts/analysis_map.json"))
    key = str(spec.params.get("items_key", "items"))
    target = context.resolve(raw_path)
    if not target.exists():
        return [], f"{raw_path} does not exist"
    data = _read_json(target)
    items = data.get(key)
    if not isinstance(items, list):
        return [], f"{raw_path}:{key} is not a list"
    return items, ""


def gate_citations_resolve(spec: GateSpec, context: GateContext) -> GateResult:
    """Every cited chunk must exist in the index with matching file, page and hash."""
    from rag_ai_scientist.core.retrieval import RetrievalError, load_index

    index_dir = context.resolve(str(spec.params.get("index_dir", "index")))
    items, problem = _load_items(spec, context)
    if problem:
        return GateResult(spec.id, "", spec.type, False, problem)
    try:
        index = load_index(index_dir, verify=True)
    except (RetrievalError, OSError, ValueError) as exc:
        return GateResult(spec.id, "", spec.type, False, f"index unusable: {exc}")

    failures: list[str] = []
    checked = 0
    for item in items:
        for citation in item.get("evidence", []) or []:
            checked += 1
            ok, reason = index.resolve_citation(citation)
            if not ok:
                failures.append(f"{item.get('id')}: {reason}")
            for required in ("file", "page", "chunk_id", "hash"):
                if citation.get(required) in (None, ""):
                    failures.append(f"{item.get('id')}: citation lacks {required}")
    if not items:
        failures.append("no items to check")
    elif checked == 0:
        failures.append("no citations to check")
    return GateResult(
        gate_id=spec.id,
        step_id="",
        type=spec.type,
        passed=not failures,
        detail="; ".join(failures[:5]) if failures else f"{checked} citations resolve",
        measured={"citations_checked": checked, "failures": len(failures)},
    )


def gate_claim_status_valid(spec: GateSpec, context: GateContext) -> GateResult:
    """Claims must be supported by citations or declared unresolved — never guessed."""
    items, problem = _load_items(spec, context)
    if problem:
        return GateResult(spec.id, "", spec.type, False, problem)
    problems: list[str] = []
    unsupported = 0
    for item in items:
        status = item.get("status")
        evidence = item.get("evidence", []) or []
        if status not in SUPPORTED_STATUS:
            problems.append(f"{item.get('id')}: unknown status {status!r}")
            continue
        if status == "supported" and not evidence:
            unsupported += 1
            problems.append(f"{item.get('id')}: supported with no citation")
        if status == "unresolved":
            if evidence:
                problems.append(f"{item.get('id')}: unresolved but cites {len(evidence)} chunks")
            if not item.get("reason"):
                problems.append(f"{item.get('id')}: unresolved without a reason")
    return GateResult(
        gate_id=spec.id,
        step_id="",
        type=spec.type,
        passed=not problems,
        detail="; ".join(problems[:5]) if problems else f"{len(items)} claims carry a valid status",
        measured={"items": len(items), "unsupported_claims": unsupported},
    )


def gate_golden_tiers(spec: GateSpec, context: GateContext) -> GateResult:
    items, problem = _load_items(spec, context)
    if problem:
        return GateResult(spec.id, "", spec.type, False, problem)
    tier1_min = float(spec.params.get("tier1_min", context.config.get("questions.tier1_min", 1.0)))
    tier23_min = float(spec.params.get("tier23_min", context.config.get("questions.tier23_min", 0.8)))

    def ratio(tiers: tuple[int, ...]) -> tuple[float, int, int]:
        selected = [item for item in items if int(item.get("tier", 0)) in tiers]
        passed = [item for item in selected if item.get("result") == "pass"]
        if not selected:
            return 0.0, 0, 0
        return len(passed) / len(selected), len(passed), len(selected)

    tier1, tier1_passed, tier1_total = ratio((1,))
    tier23, tier23_passed, tier23_total = ratio((2, 3))
    unsupported = sum(
        1
        for item in items
        if item.get("status") == "supported" and not (item.get("evidence") or [])
    )
    failures: list[str] = []
    if tier1_total == 0:
        failures.append("golden set has no Tier 1 items")
    elif tier1 < tier1_min:
        failures.append(
            f"Tier 1 pass rate {tier1:.2f} < {tier1_min:.2f} ({tier1_passed}/{tier1_total})"
        )
    if tier23_total == 0:
        failures.append("golden set has no Tier 2/3 items")
    elif tier23 < tier23_min:
        failures.append(
            f"Tier 2/3 pass rate {tier23:.2f} < {tier23_min:.2f} ({tier23_passed}/{tier23_total})"
        )
    if unsupported:
        failures.append(f"{unsupported} unsupported claim(s)")
    detail = "; ".join(failures) if failures else (
        f"Tier 1 {tier1_passed}/{tier1_total}, Tier 2/3 {tier23_passed}/{tier23_total}, "
        "unsupported claims 0"
    )
    return GateResult(
        gate_id=spec.id,
        step_id="",
        type=spec.type,
        passed=not failures,
        detail=detail,
        measured={
            "tier1": {"passed": tier1_passed, "total": tier1_total, "ratio": round(tier1, 3)},
            "tier23": {"passed": tier23_passed, "total": tier23_total, "ratio": round(tier23, 3)},
            "unsupported_claims": unsupported,
        },
    )


def gate_markdown_sections(spec: GateSpec, context: GateContext) -> GateResult:
    raw_path = str(spec.params.get("path", "report.md"))
    sections = [str(item) for item in spec.params.get("sections", [])]
    target = context.resolve(raw_path)
    if not target.exists():
        return GateResult(spec.id, "", spec.type, False, f"{raw_path} does not exist")
    text = target.read_text(encoding="utf-8")
    missing = [name for name in sections if f"## {name}" not in text]
    return GateResult(
        gate_id=spec.id,
        step_id="",
        type=spec.type,
        passed=not missing,
        detail=f"{raw_path} is missing sections: {', '.join(missing)}" if missing else (
            f"{raw_path} has all {len(sections)} required sections"
        ),
        measured={"missing": missing, "sections": len(sections)},
    )


def gate_skill_gate_consistency(spec: GateSpec, context: GateContext) -> GateResult:
    """Every gate a generated skill names must exist in plan.json (§4c.2)."""
    declared = set(context.plan.gate_ids)
    problems: list[str] = []
    checked = 0
    for record in context.skills:
        for gate_id in record.get("gates", []) or []:
            checked += 1
            if gate_id not in declared:
                problems.append(f"skill {record.get('name')} names unknown gate {gate_id!r}")
    skills_dir = context.run.skills_dir
    if skills_dir.is_dir():
        for skill_file in sorted(skills_dir.rglob("*.md")):
            text = skill_file.read_text(encoding="utf-8")
            for line in text.splitlines():
                for gate_id in declared:
                    if f"`{gate_id}`" in line and f"(`{gate_id}`)" in line:
                        checked += 1
    if checked == 0:
        problems.append("no skill-declared gates found to check")
    return GateResult(
        gate_id=spec.id,
        step_id="",
        type=spec.type,
        passed=not problems,
        detail="; ".join(problems[:5]) if problems else f"{checked} skill gate references are declared in the plan",
        measured={"references_checked": checked, "plan_gates": len(declared)},
    )



def run_gate(spec: GateSpec, context: GateContext, *, step_id: str = "") -> GateResult:
    handler = GATE_TYPES.get(spec.type)
    if handler is None:
        return GateResult(
            gate_id=spec.id,
            step_id=step_id,
            type=spec.type,
            passed=False,
            detail=f"gate type {spec.type!r} is not enforced by this version of the harness",
            proposed_fix="Declare a supported gate type in plan.json; see harness.gates.GATE_TYPES.",
        )
    try:
        result = handler(spec, context)
    except Exception as exc:  # a broken gate is a failed gate, never a pass
        return GateResult(
            gate_id=spec.id,
            step_id=step_id,
            type=spec.type,
            passed=False,
            detail=f"gate raised {type(exc).__name__}: {exc}",
            proposed_fix="Fix the gate declaration or the artifact it inspects.",
        )
    result.step_id = step_id
    return result


def run_step_gates(plan: Plan, step_id: str, context: GateContext) -> list[GateResult]:
    step = plan.step(step_id)
    if step is None:
        raise GateError(f"No step {step_id!r} in plan.")
    results: list[GateResult] = []
    for spec in step.gates:
        result = run_gate(spec, context, step_id=step_id)
        if not result.passed:
            remedy = next((item for item in step.remedies if item.id), None)
            if remedy is not None:
                result.proposed_fix = f"{remedy.description} ({remedy.as_dict()['overrides']})"
        results.append(result)
    return results


def run_all_gates(plan: Plan, context: GateContext, *, only: list[str] | None = None) -> list[GateResult]:
    results: list[GateResult] = []
    for step in plan.steps:
        if only is not None and step.id not in only:
            continue
        results.extend(run_step_gates(plan, step.id, context))
    return results


GATE_TYPES: dict[str, Any] = {
    "file_exists": gate_file_exists,
    "json_keys": gate_json_keys,
    "json_min_items": gate_json_min_items,
    "index_integrity": gate_index_integrity,
    "index_deterministic": gate_index_deterministic,
    "citations_resolve": gate_citations_resolve,
    "claim_status_valid": gate_claim_status_valid,
    "golden_tiers": gate_golden_tiers,
    "markdown_sections": gate_markdown_sections,
    "skill_gate_consistency": gate_skill_gate_consistency,
}
