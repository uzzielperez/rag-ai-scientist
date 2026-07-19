from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class OverleafProject:
    key: str
    name: str
    project_id: str
    git_token: str

    @property
    def masked(self) -> str:
        return f"{self.name} ({self.project_id[:8]}…)"


def _projects_config_path(explicit: str | Path | None = None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("OVERLEAF_PROJECTS_CONFIG", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    default = Path("~/.config/overleaf-mcp/projects.json").expanduser()
    if default.is_file():
        return default
    return None


def load_projects(config_path: str | Path | None = None) -> dict[str, OverleafProject]:
    """Load projects from OVERLEAF_PROJECTS_CONFIG JSON or a YAML sync config."""

    path = _projects_config_path(config_path)
    projects: dict[str, OverleafProject] = {}

    # Single-project env fallback
    env_id = os.environ.get("OVERLEAF_PROJECT_ID", "").strip()
    env_token = os.environ.get("OVERLEAF_GIT_TOKEN", "").strip()
    if env_id and env_token:
        projects["default"] = OverleafProject(
            key="default",
            name="default",
            project_id=env_id,
            git_token=env_token,
        )

    if path is None or not path.is_file():
        return projects

    text = path.read_text(encoding="utf-8")
    if path.suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(text) or {}
        pid = str(data.get("project_id") or env_id or "")
        token = str(data.get("git_token") or env_token or "")
        if pid and token and token != "REPLACE_WITH_TOKEN":
            projects["default"] = OverleafProject(
                key="default",
                name=str(data.get("name") or "default"),
                project_id=pid,
                git_token=token,
            )
        return projects

    data = json.loads(text)
    # Support both {projects: {...}} and flat {default: {...}} shapes.
    raw = data.get("projects", data)
    if not isinstance(raw, dict):
        return projects

    for key, meta in raw.items():
        if not isinstance(meta, dict):
            continue
        pid = str(meta.get("projectId") or meta.get("project_id") or "")
        token = str(meta.get("gitToken") or meta.get("git_token") or "")
        name = str(meta.get("name") or key)
        if not pid or not token:
            continue
        projects[str(key)] = OverleafProject(
            key=str(key),
            name=name,
            project_id=pid,
            git_token=token,
        )
    return projects


def resolve_project(
    key: str | None = None,
    *,
    config_path: str | Path | None = None,
) -> OverleafProject:
    projects = load_projects(config_path)
    if not projects:
        raise FileNotFoundError(
            "No Overleaf projects configured. Set OVERLEAF_PROJECTS_CONFIG "
            "(JSON used by the Overleaf MCP), or OVERLEAF_PROJECT_ID + "
            "OVERLEAF_GIT_TOKEN, or pass a YAML config path."
        )
    if key is None or key == "":
        if "default" in projects:
            return projects["default"]
        # First key deterministically
        return projects[sorted(projects)[0]]
    if key not in projects:
        raise KeyError(f"Unknown Overleaf project {key!r}. Known: {', '.join(sorted(projects))}")
    return projects[key]
