"""WHEST (ARC WhiteBox Estimation Challenge) — reference harness profile.

This is the canonical example loop for rag-ai-scientist: retrieve → skill →
baseline → validate → score → package → (optional) submit / document.
"""

from __future__ import annotations

from rag_ai_scientist.harness.base import Profile, Stage

PUBLIC_DATASET = "hf://aicrowd/arc-whestbench-public-2026@v1-phase1"

WHEST_STAGES: tuple[Stage, ...] = (
    Stage(
        name="doctor",
        description="Check whest + rag-ai-scientist environment health.",
        command=("uv", "run", "whest", "doctor"),
    ),
    Stage(
        name="retrieve",
        description=(
            "Informational: run MCP query_analysis_knowledge with the suggested "
            "queries (requires setup-rag). Agents should call the MCP tool."
        ),
        command=None,
        rag_queries=(
            "low-rank covariance propagation ReLU MLP flopscope",
            "ReLU expectation formula Phi alpha mean propagation",
            "adjusted_final_layer_score FLOP budget multiplier",
        ),
        skill="whest-estimation-challenge",
        skill_step="iterate",
    ),
    Stage(
        name="baseline",
        description="Compare local Monte Carlo table against mean_propagation.",
        command=("uv", "run", "python", "estimator.py", "--baseline", "mean_propagation"),
        skill="whest-estimation-challenge",
        skill_step="iterate",
    ),
    Stage(
        name="validate",
        description="Enforce estimator contract (shapes, types, lifecycle).",
        command=("uv", "run", "whest", "validate", "--estimator", "estimator.py"),
    ),
    Stage(
        name="score_local",
        description="Score on public mini split with in-process runner.",
        command=(
            "uv",
            "run",
            "whest",
            "run",
            "--estimator",
            "estimator.py",
            "--dataset",
            PUBLIC_DATASET,
            "--split",
            "mini",
            "--runner",
            "local",
        ),
        skill="whest-estimation-challenge",
        skill_step="score",
    ),
    Stage(
        name="score_subprocess",
        description="Score with subprocess runner (closer to AIcrowd grader).",
        command=(
            "uv",
            "run",
            "whest",
            "run",
            "--estimator",
            "estimator.py",
            "--dataset",
            PUBLIC_DATASET,
            "--split",
            "mini",
            "--runner",
            "subprocess",
        ),
        optional=True,
    ),
    Stage(
        name="package",
        description="Build submission.tar.gz from estimator.py.",
        command=(
            "uv",
            "run",
            "whest",
            "package",
            "--estimator",
            "estimator.py",
            "--output",
            "submission.tar.gz",
            "--yes",
        ),
    ),
    Stage(
        name="submit",
        description="Upload to AIcrowd (requires whest login). Opt-in.",
        command=("uv", "run", "whest", "submit", "submission.tar.gz", "--yes"),
        optional=True,
    ),
    Stage(
        name="document",
        description=(
            "Optional Overleaf sync of notes/bundle via "
            "`rag-ai-scientist overleaf sync` (see overleaf-paper-sync skill)."
        ),
        command=None,
        optional=True,
        skill="overleaf-paper-sync",
    ),
)

WHEST_PROFILE = Profile(
    name="whest",
    description=(
        "ARC WhiteBox Estimation Challenge 2026 — reference example loop for "
        "rag-ai-scientist (skills + RAG + whestbench + optional Overleaf)."
    ),
    stages=WHEST_STAGES,
    skill="whest-estimation-challenge",
    default_project_hint="/path/to/whest-starterkit",
    notes=(
        "Project root must be a whest-starterkit checkout with `uv sync` done. "
        "Index docs with scripts/setup_rag_references.sh then setup-rag. "
        "Use get_skill(whest-estimation-challenge) before editing estimator.py. "
        "Package uses --output (not -o). Prefer `whest submit --estimator` for one-step."
    ),
)
