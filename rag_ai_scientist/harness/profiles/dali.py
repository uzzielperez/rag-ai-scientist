"""DALI workspace profile: the execute → validate → correct loop over an
LHCb-style workflow (analysis, reconstruction or simulation).

The seven stages mirror the DALI orchestrator prompt. Stages that require
human sign-off or agent judgement are informational (``command=None``): the
runner records them and the agent drives them via the skill. Domain-specific
behaviour lives in ``skills/dali/profiles/<domain>.md``, selected by
``state/domain.yaml``.
"""

from __future__ import annotations

from rag_ai_scientist.harness.base import Profile, Stage
from rag_ai_scientist.harness.registry import register

SKILL = "dali"

DALI_PROFILE = Profile(
    name="dali",
    description=(
        "LHCb workflow orchestrator: index legacy code and papers into an "
        "inspectable pipeline, then run execute → validate → correct per "
        "step and for the whole pipeline."
    ),
    skill=SKILL,
    default_project_hint="A repo with analysis/ (legacy code) and docs/ (papers, notes).",
    notes=(
        "Domain is set once in state/domain.yaml "
        "(analysis | reconstruction | simulation) and selects "
        "skills/dali/profiles/<domain>.md. Stage 'reconcile' is a hard stop: "
        "no Snakefiles until a human approves step boundaries."
    ),
    stages=(
        Stage(
            name="setup",
            description="Create analysis/ docs/ validation/ reports/ state/ scripts/ and skills/dali/SKILL.md.",
            command=None,
            skill=SKILL,
            skill_step="setup",
        ),
        Stage(
            name="index",
            description="Build state/code_graph.json (static) and state/trace_edges.json (strace of a small run).",
            command=None,
            skill=SKILL,
            skill_step="index",
            rag_queries=("how is the analysis code structured",),
        ),
        Stage(
            name="claims",
            description="Extract reference numbers from docs/ into state/claims.yaml; tables explicitly, never semantic search.",
            command=None,
            skill=SKILL,
            skill_step="claims",
            rag_queries=("reference values and uncertainties in the notes",),
        ),
        Stage(
            name="reconcile",
            description=(
                "Group the code graph into steps, match claims to step outputs, "
                "write state/pipeline.yaml and state/open_questions.md. "
                "HARD STOP: requires human review of step boundaries before build."
            ),
            command=None,
            skill=SKILL,
            skill_step="reconcile",
        ),
        Stage(
            name="build",
            description="Mirror pipeline.yaml into per-step Snakefiles; verify with snakemake -n and --dag.",
            command=None,
            skill=SKILL,
            skill_step="build",
        ),
        Stage(
            name="run",
            description="Execute → validate → correct each step; log every attempt in state/log.jsonl.",
            command=None,
            skill=SKILL,
            skill_step="run",
        ),
        Stage(
            name="report",
            description="Regenerate reports/workflow.md and reports/workflow.html from state/ and run results.",
            command=None,
            skill=SKILL,
            skill_step="report",
        ),
    ),
)

register(DALI_PROFILE)
