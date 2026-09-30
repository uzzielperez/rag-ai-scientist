"""The deterministic planner for mode ``A-retrieval``.

v1 plans in code, not with a model: same config in, same ``plan.json`` out. The
plan is the contract — steps, exact commands, one or more gates per step, a
retry policy and pre-declared remedies — and every other part of the loop
(execute, validate, correct, the generated skill, the report) reads it. A model
backed planner can replace :func:`build_plan` later without touching them; the
hook is :func:`plan_with_llm`.
"""

from __future__ import annotations

from rag_ai_scientist.harness.config import HarnessConfig
from rag_ai_scientist.harness.plan import GateSpec, Plan, PlanStep, Remedy
from rag_ai_scientist.harness.report import REQUIRED_SECTIONS

ANALYSIS_MAP_PATH = "artifacts/analysis_map.json"
REPORT_PATH = "report.md"
INDEX_DIR = "index"

# Remedies are declared up front so the CORRECT phase can only apply corrections
# the planner already considered acceptable. Overrides are nested exactly like
# the config file, so `config.with_overrides(...)` deep-merges them unchanged.
REMEDY_WIDEN_CHUNKS = Remedy(
    id="widen_chunk_window",
    description="Index with larger chunk windows so each chunk carries a complete fact.",
    overrides={"index": {"chunk_chars": 2000, "chunk_overlap": 300}},
)
REMEDY_LOWER_MIN_SCORE = Remedy(
    id="lower_min_score",
    description="Accept lower-scoring chunks; the expected keywords still have to appear.",
    overrides={"retrieval": {"min_score": 4.0}},
)
REMEDY_INCREASE_TOP_K = Remedy(
    id="increase_top_k",
    description="Retrieve more chunks per question before deciding.",
    overrides={"retrieval": {"top_k": 8}},
)
REMEDY_LOOSEN_MIN_TERMS = Remedy(
    id="loosen_min_terms",
    description="Require one informative query term instead of two.",
    overrides={"retrieval": {"min_terms": 1}},
)


class PlannerError(RuntimeError):
    """Raised when no plan can be produced for the requested mode."""


def _cli(config: HarnessConfig, command: str) -> str:
    parts = ["ras", command, "--project-root", str(config.project_root)]
    if config.config_path:
        parts += ["--config", str(config.config_path)]
    return " ".join(parts)


def build_plan(config: HarnessConfig, run_id: str) -> Plan:
    """Build the plan for the configured mode."""
    if config.mode != "A-retrieval":
        raise PlannerError(
            f"No planner for mode {config.mode!r}. This release plans `A-retrieval` only."
        )

    index_step = PlanStep(
        id="index",
        name="Build the corpus index",
        kind="index",
        description=(
            "Extract text from every configured corpus document and write a deterministic chunk "
            "table plus a lexical (BM25) index into the run directory."
        ),
        command=_cli(config, "index"),
        reads=[str(path) for path in config.corpus_paths],
        produces=[f"{INDEX_DIR}/index.json", f"{INDEX_DIR}/chunks.jsonl"],
        gates=[
            GateSpec(
                id="index_files",
                type="file_exists",
                params={"paths": [f"{INDEX_DIR}/index.json", f"{INDEX_DIR}/chunks.jsonl"]},
                description="Both index files exist and are non-empty.",
            ),
            GateSpec(
                id="index_integrity",
                type="index_integrity",
                params={"index_dir": INDEX_DIR},
                description="The chunk file hashes to the fingerprint recorded in index.json.",
            ),
            GateSpec(
                id="index_deterministic",
                type="index_deterministic",
                params={"index_dir": INDEX_DIR},
                description="Re-indexing the same corpus reproduces identical chunks and chunk ids.",
            ),
        ],
        remedies=[REMEDY_WIDEN_CHUNKS],
    )

    answer_step = PlanStep(
        id="answer",
        name="Answer the golden set from the index",
        kind="answer",
        description=(
            "For every golden question, retrieve the best-scoring chunks and record either cited "
            "evidence or an explicit unresolved entry. Expected keywords must appear in the "
            "retrieved text for a claim to count as supported."
        ),
        command=_cli(config, "run") + " --mode A-retrieval --resume",
        reads=[f"{INDEX_DIR}/index.json"],
        produces=[ANALYSIS_MAP_PATH],
        gates=[
            GateSpec(
                id="analysis_map_shape",
                type="json_keys",
                params={
                    "path": ANALYSIS_MAP_PATH,
                    "keys": ["items", "unresolved", "metrics", "golden_set", "retrieval"],
                },
                description="The analysis map has the required top-level keys.",
            ),
            GateSpec(
                id="analysis_map_nonempty",
                type="json_min_items",
                params={"path": ANALYSIS_MAP_PATH, "key": "items", "min": 1},
                description="At least one golden question was answered.",
            ),
            GateSpec(
                id="citations_resolve",
                type="citations_resolve",
                params={"path": ANALYSIS_MAP_PATH, "index_dir": INDEX_DIR},
                description="Every cited chunk resolves to (file, page, chunk_id, hash) in the index.",
            ),
            GateSpec(
                id="claim_status_valid",
                type="claim_status_valid",
                params={"path": ANALYSIS_MAP_PATH},
                description="Every claim is either cited or explicitly unresolved; none is guessed.",
            ),
            GateSpec(
                id="golden_tiers",
                type="golden_tiers",
                params={
                    "path": ANALYSIS_MAP_PATH,
                    "tier1_min": config.get("questions.tier1_min", 1.0),
                    "tier23_min": config.get("questions.tier23_min", 0.8),
                },
                description="Tier 1 at 100%, Tier 2/3 at or above the configured threshold.",
            ),
        ],
        remedies=[
            REMEDY_LOWER_MIN_SCORE,
            REMEDY_INCREASE_TOP_K,
            REMEDY_LOOSEN_MIN_TERMS,
        ],
    )

    skills_step = PlanStep(
        id="skills",
        name="Generate the run's skill",
        kind="skill",
        description=(
            "Write runs/<run_id>/skills/<name>/ (SKILL.md plus one file per step) as the "
            "human-readable projection of this plan, and record its file hashes in the manifest."
        ),
        command="ras skills list --run RUN_ID --project-root " + str(config.project_root),
        reads=[ANALYSIS_MAP_PATH],
        produces=[f"skills/{config.run_name}/SKILL.md"],
        gates=[
            GateSpec(
                id="skill_gate_consistency",
                type="skill_gate_consistency",
                params={},
                description="Every gate the skill names exists in this plan (no unenforced claims).",
            ),
        ],
    )

    report_step = PlanStep(
        id="report",
        name="Write the run report",
        kind="report",
        description=(
            "Render report.md from the plan, the analysis map, the validation results and the "
            "generated skills."
        ),
        command="ras report --run RUN_ID --project-root " + str(config.project_root),
        reads=[ANALYSIS_MAP_PATH],
        produces=[REPORT_PATH],
        gates=[
            GateSpec(
                id="report_sections",
                type="markdown_sections",
                params={"path": REPORT_PATH, "sections": list(REQUIRED_SECTIONS)},
                description="The report contains every required section.",
            ),
        ],
    )

    plan = Plan(
        mode=config.mode,
        run_id=run_id,
        name=config.run_name,
        steps=[index_step, answer_step, skills_step, report_step],
        planner="deterministic",
        notes=[
            "Deterministic planner: the plan is a pure function of the resolved config.",
            "Every step is gated; an unenforced gate type is a failure, not a pass.",
        ],
    )
    plan.validate()
    return plan


def skill_metadata(config: HarnessConfig) -> tuple[str, str]:
    """Name and front-matter description of the generated skill."""
    description = (
        "Runs the retrieval-verification loop over one indexed corpus: builds a deterministic "
        "chunk index, answers a hand-checked golden question set, records a resolvable citation "
        "for every claim and reports what stayed unresolved. Use when the user asks to verify "
        "that a paper's analysis steps and numbers can be found in its own text."
    )
    return config.run_name, description


def skill_inputs(config: HarnessConfig) -> list[str]:
    """Run-directory artifacts the generated skill may read."""
    return [ANALYSIS_MAP_PATH, f"{INDEX_DIR}/index.json", "artifacts/plan.json"]


def plan_with_llm(*_args, **_kwargs) -> Plan:  # pragma: no cover - documented M3 hook
    """Model-backed planning hook (not part of v1).

    The loop only needs a ``Plan``; swapping this in later must not change the
    executor, the gates or the report, which is why the deterministic planner is
    kept small and the plan is written to disk before anything runs.
    """
    raise PlannerError(
        "Model-backed planning is not implemented in this release; the deterministic planner "
        "covers mode A-retrieval (see docs/harness.md)."
    )
