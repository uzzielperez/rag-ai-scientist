"""Overleaf Git-integration helpers (push bundles + read from a local mirror).

Credentials come from env / YAML / ``OVERLEAF_PROJECTS_CONFIG`` (the same JSON
used by the Node Overleaf MCP). Never commit tokens.
"""

from __future__ import annotations

from rag_ai_scientist.overleaf.client import OverleafClient, OverleafProject
from rag_ai_scientist.overleaf.config import load_projects, resolve_project

__all__ = [
    "OverleafClient",
    "OverleafProject",
    "load_projects",
    "resolve_project",
]
