from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path, PurePosixPath


class HandoffError(ValueError):
    pass


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=check,
        capture_output=True,
        text=True,
    )


def _relative_path(value: object) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise HandoffError(f"Invalid bundle path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise HandoffError(f"Unsafe bundle path: {value!r}")
    return Path(*path.parts)


def _contained_file(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise HandoffError(f"Bundle file is missing or not regular: {relative.as_posix()}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise HandoffError(f"Bundle path escapes its directory: {relative.as_posix()}")
    return path


def _load_bundle(bundle: Path) -> tuple[dict, dict[str, Path]]:
    bundle = bundle.expanduser().resolve()
    _contained_file(bundle, Path("HANDOFF.md"))
    manifest_path = _contained_file(bundle, Path("manifest.json"))
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HandoffError(f"Cannot read handoff manifest: {exc}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise HandoffError("Invalid handoff manifest: expected a files list.")

    verified: dict[str, Path] = {}
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            raise HandoffError("Invalid handoff manifest file entry.")
        relative = _relative_path(entry.get("path"))
        name = relative.as_posix()
        if name in verified:
            raise HandoffError(f"Duplicate file in handoff manifest: {name}")
        source = _contained_file(bundle, relative)
        if entry.get("size_bytes") != source.stat().st_size:
            raise HandoffError(f"Size mismatch for handoff file: {name}")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if entry.get("sha256") != digest:
            raise HandoffError(f"Checksum mismatch for handoff file: {name}")
        verified[name] = source

    if "git/working-tree.patch" not in verified:
        raise HandoffError("Handoff bundle does not contain git/working-tree.patch.")
    return manifest, verified


def apply_handoff(repo_root: Path, bundle: Path, *, apply_changes: bool = False) -> str:
    root = repo_root.expanduser().resolve()
    if not root.is_dir() or _git(root, "rev-parse", "--show-toplevel").stdout.strip() != str(root):
        raise HandoffError(f"Not a Git repository root: {root}")

    manifest, files = _load_bundle(bundle)
    base_commit = manifest.get("head_commit")
    if not isinstance(base_commit, str) or not base_commit:
        raise HandoffError("Handoff manifest has no base commit.")
    current_commit = _git(root, "rev-parse", "HEAD").stdout.strip()
    if current_commit != base_commit:
        raise HandoffError(
            f"Checkout is at {current_commit}, but this handoff requires {base_commit}. "
            "Switch to the exact base commit before resuming."
        )

    status = _git(root, "status", "--porcelain", "--untracked-files=all").stdout.strip()
    if status:
        raise HandoffError("Checkout is not clean; commit or move local changes before resuming.")

    patch = files["git/working-tree.patch"]
    check = _git(root, "apply", "--check", "--binary", str(patch), check=False)
    if check.returncode:
        detail = check.stderr.strip() or check.stdout.strip()
        raise HandoffError(f"Working-tree patch does not apply cleanly: {detail}")

    untracked = sorted(
        (name, source)
        for name, source in files.items()
        if name.startswith("untracked/")
    )
    destinations: list[tuple[Path, Path]] = []
    for name, source in untracked:
        relative = _relative_path(name.removeprefix("untracked/"))
        destination = root / relative
        if not destination.parent.resolve().is_relative_to(root):
            raise HandoffError(f"Untracked destination escapes repository: {relative.as_posix()}")
        if destination.exists() or destination.is_symlink():
            raise HandoffError(f"Untracked destination already exists: {relative.as_posix()}")
        destinations.append((source, destination))

    if not apply_changes:
        return (
            f"Handoff verified for {root}. Patch and {len(destinations)} untracked file(s) "
            "are ready; rerun with --apply to make changes."
        )

    _git(root, "apply", "--binary", str(patch))
    for source, destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return (
        f"Applied collaborator handoff to {root}: tracked patch plus "
        f"{len(destinations)} untracked file(s). Review HANDOFF.md and validate the work."
    )