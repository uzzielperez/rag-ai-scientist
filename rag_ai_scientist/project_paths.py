from __future__ import annotations

from pathlib import Path

import yaml


DEFAULT_DATA_DIR = ".rag-ai-scientist"
LEGACY_DATA_DIR = ".cursor"


def resolve_project_data_dir(project_root: Path) -> Path:
    """Resolve project storage, preserving indexes created by older releases."""
    project_root = project_root.resolve()
    config_path = project_root / "configs" / "references.yaml"
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        indexing = config.get("indexing", {})
        configured = indexing.get("data_dir") if isinstance(indexing, dict) else None
        if configured:
            data_dir = Path(configured).expanduser()
            return (project_root / data_dir).resolve() if not data_dir.is_absolute() else data_dir.resolve()

    data_dir = project_root / DEFAULT_DATA_DIR
    legacy_dir = project_root / LEGACY_DATA_DIR
    if (legacy_dir / "rag_db").exists() and not (data_dir / "rag_db").exists():
        return legacy_dir
    return data_dir