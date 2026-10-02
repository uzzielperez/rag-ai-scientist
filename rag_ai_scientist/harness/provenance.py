from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git(root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return None
    return result.stdout.strip()


def capture_source_state(project_root: Path) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    submodules = _git(root, "submodule", "status", "--recursive")
    return {
        "repository": root.name,
        "branch": _git(root, "branch", "--show-current") or None,
        "commit": _git(root, "rev-parse", "HEAD"),
        "dirty": bool(status),
        "submodules": (submodules or "").splitlines(),
    }


def _fingerprint(path_value: str | Path, project_root: Path) -> dict[str, Any]:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = project_root / path
    if path.is_symlink():
        raise ValueError(f"Input or artifact is missing or unsafe: {path_value}")
    path = path.resolve()
    if not path.exists():
        raise ValueError(f"Input or artifact is missing or unsafe: {path_value}")

    digest = hashlib.sha256()
    total_bytes = 0
    file_count = 0
    if path.is_file():
        candidates = [(path.name, path)]
    elif path.is_dir():
        candidates = [
            (item.relative_to(path).as_posix(), item)
            for item in sorted(path.rglob("*"))
            if item.is_file() and not item.is_symlink()
        ]
    else:
        raise ValueError(f"Input or artifact is not a regular file or directory: {path_value}")

    for relative_name, candidate in candidates:
        digest.update(relative_name.encode("utf-8"))
        digest.update(b"\0")
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                total_bytes += len(chunk)
        digest.update(b"\0")
        file_count += 1

    try:
        label = path.relative_to(project_root).as_posix()
    except ValueError:
        label = str(path)
    return {
        "path": label,
        "sha256": digest.hexdigest(),
        "size_bytes": total_bytes,
        "file_count": file_count,
    }


def build_run_manifest(
    *,
    project_root: Path,
    run_id: str,
    task_id: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    status: str = "unknown",
    command: Sequence[str] | None = None,
    seed: int | None = None,
    config_paths: Sequence[str | Path] = (),
    input_paths: Sequence[str | Path] = (),
    dataset_ids: Sequence[str] = (),
    metrics: Mapping[str, Any] | None = None,
    stages: Sequence[Mapping[str, Any]] = (),
    artifact_paths: Sequence[str | Path] = (),
    software_versions: Mapping[str, str] | None = None,
    source_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a workflow-neutral provenance record for a completed or partial run."""

    root = project_root.expanduser().resolve()
    source = dict(source_state) if source_state is not None else capture_source_state(root)
    configs = [_fingerprint(path, root) for path in config_paths]
    inputs = [_fingerprint(path, root) for path in input_paths]
    artifacts = [_fingerprint(path, root) for path in artifact_paths]

    return {
        "schema_version": 1,
        "run": {
            "run_id": run_id,
            "task_id": task_id,
            "started_at": started_at or _utc_now(),
            "finished_at": finished_at or _utc_now(),
            "status": status,
        },
        "source": source,
        "execution": {
            "command": list(command) if command is not None else None,
            "seed": seed,
        },
        "inputs": {
            "configurations": configs,
            "files": inputs,
            "datasets": list(dataset_ids),
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "software_versions": dict(software_versions or {}),
        },
        "results": {
            "metrics": dict(metrics or {}),
            "stages": [dict(stage) for stage in stages],
            "artifacts": artifacts,
        },
    }


def write_run_manifest(path: Path, manifest: Mapping[str, Any]) -> Path:
    destination = path.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination