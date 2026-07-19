"""Challenge harness: reusable RAG → skill → validate → score loops.

The ARC WhiteBox Estimation Challenge (``whest``) is the reference profile —
the example loop used to exercise skills, retrieval, and optional Overleaf docs.
"""

from __future__ import annotations

from rag_ai_scientist.harness.base import Profile, Stage, StageResult
from rag_ai_scientist.harness.registry import get_profile, list_profiles
from rag_ai_scientist.harness.runner import run_harness

__all__ = [
    "Profile",
    "Stage",
    "StageResult",
    "get_profile",
    "list_profiles",
    "run_harness",
]
