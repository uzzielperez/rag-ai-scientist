"""Domain-free retrieval-verification harness: gated PLAN → EXECUTE → VALIDATE → CORRECT loops.

``run_loop`` is the entry point used by ``ras run``; the plan (``Plan``),
gates and run directory (``RunDir``) are the contracts every other part of
the harness reads. The legacy profile registry (``get_profile`` /
``list_profiles`` / ``run_harness``) is still exported for the existing
``rag-ai-scientist harness`` commands.
"""

from __future__ import annotations

from rag_ai_scientist.harness.base import Profile, Stage, StageResult
from rag_ai_scientist.harness.config import HarnessConfig, load_config
from rag_ai_scientist.harness.loop import LoopError, RunResult, run_loop
from rag_ai_scientist.harness.plan import GateSpec, Plan, PlanStep, Remedy
from rag_ai_scientist.harness.registry import get_profile, list_profiles
from rag_ai_scientist.harness.rundir import RunDir, list_runs
from rag_ai_scientist.harness.runner import run_harness

__all__ = [
    "GateSpec",
    "HarnessConfig",
    "LoopError",
    "Plan",
    "PlanStep",
    "Profile",
    "Remedy",
    "RunDir",
    "RunResult",
    "Stage",
    "StageResult",
    "get_profile",
    "list_profiles",
    "list_runs",
    "load_config",
    "run_harness",
    "run_loop",
]
