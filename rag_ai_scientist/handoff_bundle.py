from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from rag_ai_scientist.handoff import apply_handoff


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return result.stdout


def _copy(source: Path, output: Path, relative: Path, files: list[dict]) -> None:
    destination = output / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    files.append(
        {
            "path": relative.as_posix(),
            "size_bytes": destination.stat().st_size,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        }
    )


def _record_text(output: Path, relative: Path, text: str, files: list[dict]) -> None:
    destination = output / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    files.append(
        {
            "path": relative.as_posix(),
            "size_bytes": destination.stat().st_size,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        }
    )


def create_handoff(args) -> Path:
    root = Path(args.repo_root).expanduser().resolve()
    if not root.is_dir() or _git(root, "rev-parse", "--show-toplevel").strip() != str(root):
        raise ValueError(f"Not a Git repository root: {root}")

    output = Path(args.output).expanduser().resolve() if args.output else None
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = root.parent / f"{root.name}-handoff-{stamp}"
    if output == root or root in output.parents:
        raise ValueError("Choose an output directory outside the repository.")
    if output.exists():
        raise ValueError(f"Output already exists; refusing to overwrite: {output}")
    if args.max_untracked_mb < 0:
        raise ValueError("--max-untracked-mb must be non-negative")

    if args.run_id:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.run_id):
            raise ValueError("Run ID may contain only letters, numbers, dots, underscores, and hyphens.")
        run_dir = root / "runs" / args.run_id
        logs_dir = run_dir / "logs"
        summary = run_dir / "summary.json"
        if not logs_dir.is_dir() or not any(
            path.is_file() and not path.is_symlink() for path in logs_dir.iterdir()
        ) and not (summary.is_file() and not summary.is_symlink()):
            raise ValueError(f"No regular logs or summary found for run {args.run_id!r}.")

    prompt_logs = [Path(path).expanduser().resolve() for path in args.prompt_log]
    if any(not path.is_file() for path in prompt_logs):
        raise ValueError("Every --prompt-log must name a regular file.")

    branch = _git(root, "branch", "--show-current").strip() or "(detached HEAD)"
    head = _git(root, "rev-parse", "HEAD").strip()
    status = _git(root, "status", "--short", "--branch", "--untracked-files=all")
    commits = _git(root, "log", "-5", "--format=%h%x09%ad%x09%s", "--date=short")
    patch = _git(root, "diff", "--binary", "HEAD", "--")
    untracked = [
        Path(path)
        for path in _git(root, "ls-files", "--others", "--exclude-standard").splitlines()
        if path
    ]
    regular_untracked = [
        path for path in untracked if (root / path).is_file() and not (root / path).is_symlink()
    ]
    total_bytes = sum((root / path).stat().st_size for path in regular_untracked)
    max_bytes = args.max_untracked_mb * 1024 * 1024
    if args.include_untracked and total_bytes > max_bytes:
        raise ValueError(
            f"Untracked files total {total_bytes} bytes, exceeding the {max_bytes}-byte limit."
        )

    output.mkdir(parents=True)
    files: list[dict] = []
    _record_text(output, Path("git/status.txt"), status, files)
    _record_text(output, Path("git/recent-commits.txt"), commits, files)
    _record_text(output, Path("git/working-tree.patch"), patch, files)

    copied_untracked: list[str] = []
    if args.include_untracked:
        for relative in regular_untracked:
            _copy(root / relative, output, Path("untracked") / relative, files)
            copied_untracked.append(relative.as_posix())

    pipeline_logs: list[str] = []
    if args.run_id:
        run_dir = root / "runs" / args.run_id
        sources = sorted(path for path in (run_dir / "logs").iterdir() if path.is_file() and not path.is_symlink())
        summary = run_dir / "summary.json"
        if summary.is_file() and not summary.is_symlink():
            sources.append(summary)
        for source in sources:
            relative = Path("pipeline_logs") / args.run_id / source.name
            _copy(source, output, relative, files)
            pipeline_logs.append(relative.as_posix())

    prompt_entries: list[dict] = []
    used_names: set[str] = set()
    for source in prompt_logs:
        name = source.name
        index = 2
        while name in used_names:
            name = f"{source.stem}-{index}{source.suffix}"
            index += 1
        used_names.add(name)
        relative = Path("prompt_logs") / name
        _copy(source, output, relative, files)
        prompt_entries.append({"source_name": source.name, "bundle_path": relative.as_posix()})

    untracked_lines = [
        f"- `{path}`" + ("" if path in copied_untracked else " (contents not copied)")
        for path in (p.as_posix() for p in untracked)
    ] or ["- None"]
    lines = [
        "# Work handoff", "", f"- Repository: `{root.name}`", f"- Branch: `{branch}`",
        f"- Base commit: `{head}`", f"- Created: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"- Pipeline run: `{args.run_id}`" if args.run_id else "- Pipeline run: not selected",
        "", "## Current work", "", args.what_changed.strip() or "_No work summary supplied._",
        "", "## Next step", "", args.next_step.strip() or "_Not supplied; agree on the next action with the author._",
        "", "## Git state", "",
        "The bundle contains `git/working-tree.patch` for tracked modifications relative to the base commit.",
        "Apply only to a clean checkout at the exact base commit above.", "", "Untracked paths:", *untracked_lines,
        "", "## Included pipeline logs", "",
        *([f"- `{path}`" for path in pipeline_logs] or ["- None"]),
        "", "## Included prompt logs", "",
        *([f"- `{entry['bundle_path']}` (source: `{entry['source_name']}`)" for entry in prompt_entries] or ["- None"]),
        "", "## Privacy", "",
        "Review this bundle before sharing; logs and transcripts may contain credentials, private data, or internal paths.", "",
    ]
    (output / "HANDOFF.md").write_text("\n".join(lines), encoding="utf-8")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository_name": root.name,
        "branch": branch,
        "head_commit": head,
        "run_id": args.run_id,
        "untracked_paths": [path.as_posix() for path in untracked],
        "copied_untracked_paths": copied_untracked,
        "pipeline_logs": pipeline_logs,
        "prompt_logs": prompt_entries,
        "files": files,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="rag-ai-scientist-handoff",
        description="Create or apply a collaborator handoff bundle.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Bundle local Git work for a collaborator.")
    create.add_argument("--repo-root", type=Path, default=Path.cwd())
    create.add_argument("--output", type=Path)
    create.add_argument("--run-id")
    create.add_argument("--prompt-log", type=Path, action="append", default=[])
    create.add_argument("--include-untracked", action="store_true")
    create.add_argument("--max-untracked-mb", type=int, default=50)
    create.add_argument("--what-changed", default="")
    create.add_argument("--next-step", default="")

    apply = sub.add_parser("apply", help="Validate and apply a collaborator bundle.")
    apply.add_argument("bundle", type=Path)
    apply.add_argument("--project-root", type=Path, default=Path.cwd())
    apply.add_argument("--apply", action="store_true", dest="apply_changes")

    args = parser.parse_args()
    try:
        if args.command == "create":
            output = create_handoff(args)
            print(f"Created handoff bundle: {output}")
            print(f"Review before sharing: {output / 'HANDOFF.md'}")
        else:
            print(
                apply_handoff(
                    args.project_root,
                    args.bundle,
                    apply_changes=args.apply_changes,
                )
            )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"handoff failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())