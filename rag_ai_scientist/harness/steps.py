"""Step executors: the EXECUTE phase.

Each executor is a pure function of (config, run directory, resolved plan) and
writes only inside the run directory. Executors never decide whether they
succeeded — they write artifacts and let the declared gates judge them, so the
report can say "this step is fine because gate X measured Y" rather than
"because the code said so".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rag_ai_scientist.core.retrieval import best_quote, build_index, load_index
from rag_ai_scientist.core.text import normalize_text
from rag_ai_scientist.harness.config import HarnessConfig
from rag_ai_scientist.harness.plan import PlanStep
from rag_ai_scientist.harness.rundir import RunDir


class StepError(RuntimeError):
    """Raised when a step cannot run at all (missing input, bad config)."""


@dataclass
class StepOutcome:
    step_id: str
    status: str
    message: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)
    measured: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "status": self.status,
            "message": self.message,
            "artifacts": self.artifacts,
            "measured": self.measured,
        }


@dataclass
class GoldenQuestion:
    id: str
    tier: int
    question: str
    expect: str
    expect_keywords: list[str]
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tier": self.tier,
            "question": self.question,
            "expect": self.expect,
            "expect_keywords": self.expect_keywords,
            "notes": self.notes,
        }


@dataclass
class GoldenSet:
    name: str
    description: str
    questions: list[GoldenQuestion]
    path: Path

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "path": str(self.path),
            "questions": [item.as_dict() for item in self.questions],
        }


def load_golden_set(path: Path) -> GoldenSet:
    """Load and validate a golden question set (.json or .yaml)."""
    path = Path(path)
    if not path.exists():
        raise StepError(f"Golden set not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml

        data = yaml.safe_load(text) or {}
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise StepError(f"{path} must contain a mapping at the top level.")
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise StepError(f"{path} must contain a non-empty `questions` list.")

    seen: set[str] = set()
    questions: list[GoldenQuestion] = []
    for index, item in enumerate(raw_questions, start=1):
        question_id = str(item.get("id") or f"Q{index:02d}")
        if question_id in seen:
            raise StepError(f"{path}: duplicate question id {question_id!r}")
        seen.add(question_id)
        tier = int(item.get("tier", 0))
        if tier not in (1, 2, 3):
            raise StepError(f"{path}:{question_id} has tier {tier!r}; tiers are 1, 2 or 3")
        expect = str(item.get("expect", "supported")).strip().lower()
        if expect not in ("supported", "unresolved"):
            raise StepError(f"{path}:{question_id} expect must be `supported` or `unresolved`")
        keywords = [str(word) for word in item.get("expect_keywords", []) if str(word).strip()]
        if not keywords:
            raise StepError(
                f"{path}:{question_id} needs `expect_keywords`: the exact terms that must appear "
                "in the retrieved text for the claim to count as supported."
            )
        questions.append(
            GoldenQuestion(
                id=question_id,
                tier=tier,
                question=str(item.get("question", "")).strip(),
                expect=expect,
                expect_keywords=keywords,
                notes=str(item.get("notes", "")),
            )
        )
    return GoldenSet(
        name=str(data.get("name", path.stem)),
        description=str(data.get("description", "")),
        questions=questions,
        path=path,
    )


def find_golden_set(config: HarnessConfig) -> Path:
    """Locate the golden set: explicit config path, else the single evals/golden file."""
    explicit = config.questions_path
    if explicit is not None:
        return explicit
    golden_dir = config.project_root / "evals" / "golden"
    candidates = sorted(
        path
        for path in golden_dir.glob("*")
        if path.suffix.lower() in (".json", ".yaml", ".yml")
    ) if golden_dir.is_dir() else []
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise StepError(
            f"No golden set found. Put one in {golden_dir} or set `questions.path` in the config."
        )
    raise StepError(
        "Several golden sets found, refusing to guess: "
        + ", ".join(path.name for path in candidates)
        + ". Set `questions.path` in the config."
    )


def step_index(*, step: PlanStep, run: RunDir, config: HarnessConfig, **_ignored: Any) -> StepOutcome:
    """Build the run's index from the configured corpus."""
    index = build_index(
        project_root=config.project_root,
        paths=config.corpus_paths,
        index_dir=run.index_dir,
        extensions=config.corpus_extensions,
        chunk_chars=config.chunk_chars,
        chunk_overlap=config.chunk_overlap,
    )
    for doc in index.meta.get("docs", []):
        run.log("index", f"indexed {doc['doc_path']} pages={doc['pages']} chunks={doc['chunks']}")
    return StepOutcome(
        step_id=step.id,
        status="ok",
        message=f"indexed {index.meta.get('doc_count')} document(s) into {len(index)} chunks",
        artifacts={
            "chunks": run.run_rel(run.index_dir / "chunks.jsonl"),
            "meta": run.run_rel(run.index_dir / "index.json"),
        },
        measured={
            "chunks": len(index),
            "docs": index.meta.get("doc_count"),
            "total_chars": index.meta.get("total_chars"),
            "chunks_sha256": index.meta.get("chunks_sha256"),
            "chunk_params": index.meta.get("chunk_params"),
        },
    )


def _answer_question(index: Any, question: GoldenQuestion, config: HarnessConfig) -> dict[str, Any]:
    hits = index.search(
        question.question,
        top_k=config.top_k,
        min_score=config.min_score,
        min_terms=config.min_terms,
    )
    evidence: list[dict[str, Any]] = []
    considered: list[dict[str, Any]] = []
    for hit in hits:
        citation = hit.citation()
        citation["quote"] = best_quote(hit.chunk.text, question.question, max_chars=320)
        citation["terms_matched"] = list(hit.matched_terms)
        evidence.append(citation)
        considered.append(
            {"chunk_id": hit.chunk.chunk_id, "file": hit.chunk.file, "page": hit.chunk.page,
             "score": round(hit.score, 3)}
        )

    haystack = normalize_text(" ".join(hit.chunk.text for hit in hits)).lower()
    keywords_found = [word for word in question.expect_keywords if word.lower() in haystack]
    all_keywords = len(keywords_found) == len(question.expect_keywords)
    citation_valid = all(
        index.resolve_citation(citation)[0] for citation in evidence
    ) if evidence else False

    if question.expect == "supported":
        supported = bool(hits) and all_keywords
        status = "supported" if supported else "unresolved"
        result = "pass" if supported else "fail"
        if supported:
            reason = ""
        elif not hits:
            reason = (
                f"no chunk scored above min_score={config.min_score} with min_terms="
                f"{config.min_terms}; the corpus appears silent"
            )
        else:
            missing = [word for word in question.expect_keywords if word not in keywords_found]
            reason = f"retrieved evidence does not state the fact (missing: {', '.join(missing)})"
    else:
        # Negative control: the fact must NOT be in the corpus.
        status = "unresolved" if not all_keywords else "supported"
        result = "pass" if status == "unresolved" else "fail"
        found = ", ".join(keywords_found)
        reason = (
            f"corpus states the fact after all (found: {found}); the golden set expected silence"
            if all_keywords
            else f"no retrieved text states the fact (searched: {question.question})"
        )

    if status == "unresolved":
        payload_evidence: list[dict[str, Any]] = []
    else:
        payload_evidence = evidence
        if not citation_valid:
            result = "fail"
            reason = "a cited chunk does not resolve against the index"

    return {
        "id": question.id,
        "tier": question.tier,
        "question": question.question,
        "status": status,
        "result": result,
        "reason": reason,
        "notes": question.notes,
        "expect": {"status": question.expect, "keywords": question.expect_keywords},
        "keywords_found": keywords_found,
        "citation_valid": citation_valid,
        "evidence": payload_evidence,
        "considered": considered,
    }



def step_answer(*, step: PlanStep, run: RunDir, config: HarnessConfig, **_ignored: Any) -> StepOutcome:
    """Answer the golden set from the index and write artifacts/analysis_map.json."""
    golden_path = find_golden_set(config)
    golden = load_golden_set(golden_path)
    try:
        index = load_index(run.index_dir)
    except Exception as exc:
        raise StepError(f"Step {step.id!r} needs an index: {exc}") from exc

    items = [_answer_question(index, question, config) for question in golden.questions]
    unresolved = [
        {"id": item["id"], "tier": item["tier"], "question": item["question"], "reason": item["reason"]}
        for item in items
        if item["status"] == "unresolved"
    ]

    def tier_stats(tiers: tuple[int, ...]) -> dict[str, Any]:
        selected = [item for item in items if item["tier"] in tiers]
        passed = [item for item in selected if item["result"] == "pass"]
        return {
            "passed": len(passed),
            "total": len(selected),
            "ratio": round(len(passed) / len(selected), 3) if selected else 0.0,
        }

    payload = {
        "schema_version": 1,
        "mode": config.mode,
        "run_id": run.run_id,
        "golden_set": {
            "name": golden.name,
            "path": run.rel(golden.path),
            "description": golden.description,
            "questions": len(golden.questions),
        },
        "retrieval": {
            "provider": index.meta.get("provider"),
            "chunks": len(index),
            "chunks_sha256": index.meta.get("chunks_sha256"),
            "top_k": config.top_k,
            "min_score": config.min_score,
            "min_terms": config.min_terms,
        },
        "items": items,
        "unresolved": unresolved,
        "metrics": {
            "questions": len(items),
            "supported": sum(1 for item in items if item["status"] == "supported"),
            "unresolved": len(unresolved),
            "tier1": tier_stats((1,)),
            "tier23": tier_stats((2, 3)),
            "unsupported_claims": sum(
                1
                for item in items
                if item["status"] == "supported" and not item["evidence"]
            ),
            "citations_valid": all(
                item["citation_valid"] for item in items if item["status"] == "supported"
            ),
        },
    }
    run.write_json(run.analysis_map_json, payload)
    for item in items:
        run.log(
            "answer",
            f"{item['id']} tier={item['tier']} status={item['status']} result={item['result']} "
            f"evidence={len(item['evidence'])}",
        )
    metrics = payload["metrics"]
    return StepOutcome(
        step_id=step.id,
        status="ok",
        message=(
            f"{metrics['supported']} supported, {metrics['unresolved']} unresolved "
            f"(Tier 1 {metrics['tier1']['passed']}/{metrics['tier1']['total']}, "
            f"Tier 2/3 {metrics['tier23']['passed']}/{metrics['tier23']['total']})"
        ),
        artifacts={"analysis_map": run.run_rel(run.analysis_map_json)},
        measured=metrics,
    )


def step_report(
    *,
    step: PlanStep,
    run: RunDir,
    config: HarnessConfig,
    plan: Any = None,
    skills: list[dict[str, Any]] | None = None,
    validation: dict[str, Any] | None = None,
    outcome: str = "ok",
) -> StepOutcome:
    """Render report.md from what is on disk (idempotent)."""
    from rag_ai_scientist.harness.report import render_report

    text = render_report(
        run=run,
        config=config,
        plan=plan,
        skills=skills or [],
        validation=validation,
        outcome=outcome,
    )
    run.write_text(run.report_md, text)
    return StepOutcome(
        step_id=step.id,
        status="ok",
        message=f"report written ({len(text.splitlines())} lines)",
        artifacts={"report": run.run_rel(run.report_md)},
        measured={"bytes": len(text.encode("utf-8"))},
    )


STEP_EXECUTORS = {
    "index": step_index,
    "answer": step_answer,
    "report": step_report,
}


def step_skill(
    *,
    step: PlanStep,
    run: RunDir,
    config: HarnessConfig,
    plan: Any = None,
    **_ignored: Any,
) -> StepOutcome:
    """(Re)generate the run's skill from the plan; deterministic and idempotent."""
    from rag_ai_scientist.harness.planner import skill_inputs, skill_metadata
    from rag_ai_scientist.harness.skills import generate_skill

    if plan is None:
        raise StepError("Step 'skills' needs the plan it projects.")
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
    return StepOutcome(
        step_id=step.id,
        status="ok",
        message=f"skill {name} written with {len(generated.files)} file(s)",
        artifacts={"skill": run.run_rel(generated.path)},
        measured={
            "name": generated.name,
            "version": generated.version,
            "files": generated.files,
            "digest": generated.digest(),
            "gates": generated.gates,
        },
    )


STEP_EXECUTORS["skill"] = step_skill


def execute_step(
    step: PlanStep,
    *,
    run: RunDir,
    config: HarnessConfig,
    plan: Any = None,
    skills: list[dict[str, Any]] | None = None,
    validation: dict[str, Any] | None = None,
    outcome: str = "ok",
) -> StepOutcome:
    executor = STEP_EXECUTORS.get(step.kind)
    if executor is None:
        raise StepError(
            f"Step {step.id!r} has kind {step.kind!r}, which this release cannot execute. "
            f"Known kinds: {', '.join(sorted(STEP_EXECUTORS))}"
        )
    return executor(
        step=step,
        run=run,
        config=config,
        plan=plan,
        skills=skills or [],
        validation=validation,
        outcome=outcome,
    )
