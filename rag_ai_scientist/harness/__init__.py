"""Challenge harness: reusable RAG → skill → validate → score loops.

The ARC WhiteBox Estimation Challenge (``whest``) is the reference profile —
the example loop used to exercise skills, retrieval, and optional Overleaf docs.
"""

from __future__ import annotations

from rag_ai_scientist.harness.base import Profile, Stage, StageResult
from rag_ai_scientist.harness.provenance import (
    build_run_manifest,
    capture_source_state,
    write_run_manifest,
)
from rag_ai_scientist.harness.registry import get_profile, list_profiles, register_profile
from rag_ai_scientist.harness.runner import run_harness

__all__ = [
    "Profile",
    "Stage",
    "StageResult",
    "build_run_manifest",
    "capture_source_state",
    "get_profile",
    "list_profiles",
    "register_profile",
    "run_harness",
    "write_run_manifest",
]
