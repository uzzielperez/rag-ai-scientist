from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from rag_ai_scientist.project_paths import DEFAULT_DATA_DIR, resolve_project_data_dir


DEFAULT_DOC_TYPE_RULES: dict[str, list[str]] = {
    "paper": ["papers", "publication"],
    "analysis_note": ["analysis_notes", "notes"],
    "documentation": ["docs", "readme", "manual"],
}


DEFAULT_EXTENSIONS = [".pdf", ".md", ".txt", ".tex", ".py", ".rst"]


def _project_root(project_root: str | None) -> Path:
    return Path(project_root or os.getcwd()).resolve()


def _write_references_yaml(
    *,
    project_root: Path,
    references_dir: Path,
    force: bool,
    collection_name: str,
    chunk_size: int,
    chunk_overlap: int,
    scientific_chunk_size: int,
    scientific_chunk_overlap: int,
    extensions: list[str],
    data_dir: str,
) -> Path:
    configs_dir = project_root / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    config_path = configs_dir / "references.yaml"

    if config_path.exists() and not force:
        raise SystemExit(
            f"Refusing to overwrite existing config: {config_path}. "
            f"Re-run with --force."
        )

    config = {
        "indexing": {
            "collection_name": collection_name,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "scientific_chunk_size": scientific_chunk_size,
            "scientific_chunk_overlap": scientific_chunk_overlap,
            "data_dir": data_dir,
            "doc_type_rules": DEFAULT_DOC_TYPE_RULES,
        },
        "sources": [
            {
                "name": "user_references",
                "paths": [str(references_dir)],
                "extensions": extensions,
            }
        ],
    }

    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def cmd_init_references(args: argparse.Namespace) -> None:
    project_root = _project_root(args.project_root)
    if args.references_dir:
        references_dir = Path(args.references_dir).expanduser().resolve()
    else:
        prompt = "References directory path (containing PDFs/MD/TXT/etc): "
        references_dir = Path(input(prompt).strip()).expanduser().resolve()

    if not references_dir.exists():
        raise SystemExit(f"References directory does not exist: {references_dir}")

    config_path = _write_references_yaml(
        project_root=project_root,
        references_dir=references_dir,
        force=args.force,
        collection_name=args.collection_name,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        scientific_chunk_size=args.scientific_chunk_size,
        scientific_chunk_overlap=args.scientific_chunk_overlap,
        extensions=args.extensions,
        data_dir=args.data_dir,
    )

    print(f"Wrote: {config_path}")


def cmd_setup_rag(args: argparse.Namespace) -> None:
    project_root = _project_root(args.project_root)
    config_path = project_root / "configs" / "references.yaml"
    if not config_path.exists():
        raise SystemExit(
            f"Missing config: {config_path}. Run `rag-ai-scientist init-references` first."
        )

    out_dir = resolve_project_data_dir(project_root) / "rag_db"
    out_dir.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [
        sys.executable,
        "-m",
        "rag.index_documents",
        "--config",
        str(config_path),
        "--output-dir",
        str(out_dir),
    ]
    if args.force:
        cmd.append("--force")
    if args.collection_name:
        cmd.extend(["--collection-name", args.collection_name])
    if args.chunk_size:
        cmd.extend(["--chunk-size", str(args.chunk_size)])
    if args.chunk_overlap:
        cmd.extend(["--chunk-overlap", str(args.chunk_overlap)])

    subprocess.run(cmd, check=True)
    print(f"Built RAG DB at: {out_dir}")


def cmd_mcp(args: argparse.Namespace) -> None:
    # Import lazily so normal CLI usage doesn't require MCP deps until needed.
    from rag_ai_scientist.mcp_server import run_mcp

    run_mcp(project_root=_project_root(args.project_root))


def cmd_harness_list(_args: argparse.Namespace) -> None:
    from rag_ai_scientist.harness import list_profiles

    for profile in list_profiles():
        print(f"{profile.name}: {profile.description}")
        print(f"  skill: {profile.skill}")
        print(f"  stages: {', '.join(profile.stage_names())}")
        if profile.notes:
            print(f"  notes: {profile.notes}")
        print()


def cmd_harness_run(args: argparse.Namespace) -> None:
    from rag_ai_scientist.harness import run_harness

    summary = run_harness(
        project_root=_project_root(args.project_root),
        profile_name=args.profile,
        from_stage=args.from_stage or None,
        until_stage=args.until_stage or None,
        include_optional=args.include_optional,
        dry_run=args.dry_run,
        timeout_s=args.timeout or None,
        run_id=args.run_id or None,
        task_id=args.task_id or None,
        seed=args.seed,
        config_paths=tuple(args.config),
        input_paths=tuple(args.input),
        dataset_ids=tuple(args.dataset_id),
    )
    print(yaml.safe_dump(summary, sort_keys=False))
    if not summary.get("ok", False):
        raise SystemExit(1)


def cmd_overleaf_list_projects(args: argparse.Namespace) -> None:
    from rag_ai_scientist.overleaf import load_projects

    projects = load_projects(args.config or None)
    if not projects:
        raise SystemExit(
            "No Overleaf projects found. Set OVERLEAF_PROJECTS_CONFIG or "
            "OVERLEAF_PROJECT_ID + OVERLEAF_GIT_TOKEN."
        )
    for key, project in sorted(projects.items()):
        print(f"{key}: {project.name} ({project.project_id})")


def cmd_overleaf_status(args: argparse.Namespace) -> None:
    from rag_ai_scientist.overleaf import resolve_project
    from rag_ai_scientist.overleaf.client import client_for_project

    project_root = _project_root(args.project_root)
    project = resolve_project(args.project or None, config_path=args.config or None)
    client = client_for_project(project, project_root=project_root)
    print(yaml.safe_dump(client.status(), sort_keys=False))


def cmd_overleaf_sync(args: argparse.Namespace) -> None:
    from rag_ai_scientist.overleaf import resolve_project
    from rag_ai_scientist.overleaf.client import client_for_project

    project_root = _project_root(args.project_root)
    project = resolve_project(args.project or None, config_path=args.config or None)
    client = client_for_project(project, project_root=project_root)
    bundle = Path(args.bundle_dir).expanduser()
    if not bundle.is_absolute():
        bundle = (project_root / bundle).resolve()
    result = client.sync_bundle(
        bundle,
        dry_run=args.dry_run,
        main_tex_name=args.main_tex_name,
    )
    print(yaml.safe_dump(result, sort_keys=False))
    if not result.get("ok", False):
        raise SystemExit(1)


def _print_check(ok: bool, label: str, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    suffix = f": {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")
    return ok


def cmd_doctor(args: argparse.Namespace) -> None:
    project_root = _project_root(args.project_root)
    checks: list[bool] = []

    checks.append(
        _print_check(
            sys.version_info >= (3, 10),
            "python-version",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    )

    config_path = project_root / "configs" / "references.yaml"
    checks.append(_print_check(config_path.exists(), "config-exists", str(config_path)))
    if config_path.exists():
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            sources = cfg.get("sources", [])
            has_paths = any(group.get("paths") for group in sources if isinstance(group, dict))
            checks.append(_print_check(bool(sources), "config-has-sources"))
            checks.append(_print_check(bool(has_paths), "config-has-source-paths"))
        except Exception as exc:
            checks.append(_print_check(False, "config-parse", str(exc)))

    rag_parent = resolve_project_data_dir(project_root)
    rag_db = rag_parent / "rag_db"
    try:
        rag_parent.mkdir(parents=True, exist_ok=True)
        rag_db.mkdir(parents=True, exist_ok=True)
        probe = rag_db / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(_print_check(True, "rag-db-writable", str(rag_db)))
    except Exception as exc:
        checks.append(_print_check(False, "rag-db-writable", str(exc)))

    for mod_name in ("yaml", "rag.index_documents", "rag_ai_scientist.mcp_server"):
        try:
            __import__(mod_name)
            checks.append(_print_check(True, f"import-{mod_name}"))
        except Exception as exc:
            checks.append(_print_check(False, f"import-{mod_name}", str(exc)))

    has_groq = bool(os.getenv("GROQ_API_KEY"))
    if has_groq:
        _print_check(True, "env-GROQ_API_KEY")
    else:
        print("[WARN] env-GROQ_API_KEY: not set (required for QA generation paths)")

    if not all(checks):
        raise SystemExit(1)
    print("Doctor checks passed.")


def cmd_self_test(args: argparse.Namespace) -> None:
    checks: list[bool] = []
    with tempfile.TemporaryDirectory(prefix="rag-ai-scientist-selftest-") as tmp:
        tmp_root = Path(tmp)
        refs_dir = tmp_root / "refs"
        refs_dir.mkdir(parents=True, exist_ok=True)
        (refs_dir / "note.md").write_text(
            "# Self test\n\nThis file validates the rag-ai-scientist CLI workflow.\n",
            encoding="utf-8",
        )

        config_path = _write_references_yaml(
            project_root=tmp_root,
            references_dir=refs_dir,
            force=True,
            collection_name="rag-ai-scientist-self-test",
            chunk_size=500,
            chunk_overlap=50,
            scientific_chunk_size=700,
            scientific_chunk_overlap=100,
            extensions=[".md", ".txt"],
            data_dir=DEFAULT_DATA_DIR,
        )
        checks.append(_print_check(config_path.exists(), "selftest-config-written", str(config_path)))

        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            checks.append(_print_check("sources" in cfg, "selftest-config-parse"))
        except Exception as exc:
            checks.append(_print_check(False, "selftest-config-parse", str(exc)))

        for cmd in (
            [sys.executable, "-m", "rag_ai_scientist.cli", "--help"],
            [sys.executable, "-m", "rag_ai_scientist.cli", "init-references", "--help"],
            [sys.executable, "-m", "rag_ai_scientist.cli", "setup-rag", "--help"],
            [sys.executable, "-m", "rag_ai_scientist.cli", "mcp", "--help"],
            [sys.executable, "-m", "rag_ai_scientist.cli", "handoff", "create", "--help"],
            [sys.executable, "-m", "rag_ai_scientist.cli", "handoff", "apply", "--help"],
            [sys.executable, "-m", "rag_ai_scientist.cli", "onboard", "--help"],
            [sys.executable, "-m", "rag.index_documents", "--help"],
        ):
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                checks.append(_print_check(True, "selftest-cli", " ".join(cmd[2:])))
            except Exception as exc:
                checks.append(_print_check(False, "selftest-cli", f"{' '.join(cmd[2:])} -> {exc}"))

    if not all(checks):
        raise SystemExit(1)
    print("Self-test passed.")


def cmd_onboard(args: argparse.Namespace) -> None:
    try:
        import langgraph  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "The onboard command needs langgraph (Python >= 3.10): pip install langgraph"
        ) from exc
    from rag_ai_scientist.dali_onboard import run_interactive

    run_interactive(workspace=args.workspace, thread_id=args.thread_id)


def cmd_handoff_apply(args: argparse.Namespace) -> None:
    from rag_ai_scientist.handoff import apply_handoff

    try:
        print(
            apply_handoff(
                Path(args.project_root),
                Path(args.bundle),
                apply_changes=args.apply,
            )
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"handoff failed: {exc}") from exc


def cmd_handoff_create(args: argparse.Namespace) -> None:
    from rag_ai_scientist.handoff_bundle import create_handoff

    try:
        output = create_handoff(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"handoff failed: {exc}") from exc
    print(f"Created handoff bundle: {output}")
    print(f"Review before sharing: {output / 'HANDOFF.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="rag-ai-scientist")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init-references", help="Write configs/references.yaml from a references directory.")
    p_init.add_argument("--project-root", default=".", help="Target analysis repo root.")
    p_init.add_argument("--references-dir", default="", help="Directory containing your reference PDFs/MD/TXT/etc.")
    p_init.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="Project-local RAG data directory (relative to project root unless absolute).")
    p_init.add_argument("--collection-name", default="rag-ai-scientist")
    p_init.add_argument("--chunk-size", type=int, default=1500)
    p_init.add_argument("--chunk-overlap", type=int, default=200)
    p_init.add_argument("--scientific-chunk-size", type=int, default=2000)
    p_init.add_argument("--scientific-chunk-overlap", type=int, default=300)
    p_init.add_argument(
        "--extensions",
        default=",".join(DEFAULT_EXTENSIONS),
        help="Comma-separated extensions (include leading dots).",
    )
    p_init.add_argument("--force", action="store_true", help="Overwrite configs/references.yaml if it exists.")

    def _parse_exts(s: str) -> list[str]:
        exts = [e.strip() for e in s.split(",") if e.strip()]
        return [e if e.startswith(".") else f".{e}" for e in exts]

    p_init.set_defaults(_parse_exts=_parse_exts, func=cmd_init_references)

    p_setup = sub.add_parser("setup-rag", help="Index references and build the project RAG database.")
    p_setup.add_argument("--project-root", default=".", help="Target analysis repo root.")
    p_setup.add_argument("--force", action="store_true", help="Rebuild rag_db from scratch.")
    p_setup.add_argument("--collection-name", default="", help="Override collection name.")
    p_setup.add_argument("--chunk-size", type=int, default=0)
    p_setup.add_argument("--chunk-overlap", type=int, default=0)
    p_setup.set_defaults(func=cmd_setup_rag)

    p_mcp = sub.add_parser("mcp", help="Start the stdio MCP server for any compatible client.")
    p_mcp.add_argument("--project-root", default=".", help="Target analysis repo root.")
    p_mcp.set_defaults(func=cmd_mcp)

    p_harness = sub.add_parser("harness", help="Run challenge harness profiles (example: whest).")
    harness_sub = p_harness.add_subparsers(dest="harness_cmd", required=True)

    p_harness_list = harness_sub.add_parser("list", help="List available harness profiles.")
    p_harness_list.set_defaults(func=cmd_harness_list)

    p_harness_run = harness_sub.add_parser("run", help="Run a harness profile against a project root.")
    p_harness_run.add_argument("--project-root", default=".", help="Challenge / research repo root.")
    p_harness_run.add_argument("--profile", default="whest", help="Profile name (default: whest).")
    p_harness_run.add_argument("--from-stage", default="", dest="from_stage")
    p_harness_run.add_argument("--until-stage", default="", dest="until_stage")
    p_harness_run.add_argument(
        "--include-optional",
        action="store_true",
        help="Include optional stages (submit, document, …).",
    )
    p_harness_run.add_argument("--dry-run", action="store_true", help="Print stages without executing.")
    p_harness_run.add_argument("--timeout", type=int, default=0, help="Per-stage timeout seconds (0=none).")
    p_harness_run.add_argument("--run-id", default="", help="Optional run id for runs/ artifacts.")
    p_harness_run.add_argument("--task-id", default="", help="Research task identifier recorded in the run manifest.")
    p_harness_run.add_argument("--seed", type=int, help="Random seed recorded in the run manifest.")
    p_harness_run.add_argument("--config", action="append", default=[], help="Config file to fingerprint; may be repeated.")
    p_harness_run.add_argument("--input", action="append", default=[], help="Input file/directory to fingerprint; may be repeated.")
    p_harness_run.add_argument("--dataset-id", action="append", default=[], help="Dataset identifier or URI; may be repeated.")
    p_harness_run.set_defaults(func=cmd_harness_run)

    p_overleaf = sub.add_parser("overleaf", help="Overleaf Git sync / inspect (custom MCP companion).")
    overleaf_sub = p_overleaf.add_subparsers(dest="overleaf_cmd", required=True)

    p_ol_list = overleaf_sub.add_parser("list-projects", help="List configured Overleaf projects.")
    p_ol_list.add_argument("--config", default="", help="Optional projects JSON or YAML path.")
    p_ol_list.set_defaults(func=cmd_overleaf_list_projects)

    p_ol_status = overleaf_sub.add_parser("status", help="Show Overleaf mirror status.")
    p_ol_status.add_argument("--project-root", default=".")
    p_ol_status.add_argument("--project", default="", help="Project key (default: default).")
    p_ol_status.add_argument("--config", default="")
    p_ol_status.set_defaults(func=cmd_overleaf_status)

    p_ol_sync = overleaf_sub.add_parser("sync", help="Push a local LaTeX bundle to Overleaf via Git.")
    p_ol_sync.add_argument("--project-root", default=".")
    p_ol_sync.add_argument("--bundle-dir", required=True, help="Local directory with main.tex (+ figures).")
    p_ol_sync.add_argument("--project", default="", help="Project key from OVERLEAF_PROJECTS_CONFIG.")
    p_ol_sync.add_argument("--config", default="")
    p_ol_sync.add_argument("--main-tex-name", default="main.tex")
    p_ol_sync.add_argument("--dry-run", action="store_true")
    p_ol_sync.set_defaults(func=cmd_overleaf_sync)

    p_doctor = sub.add_parser("doctor", help="Run local environment and project health checks.")
    p_doctor.add_argument("--project-root", default=".", help="Target analysis repo root.")
    p_doctor.set_defaults(func=cmd_doctor)

    p_self_test = sub.add_parser("self-test", help="Run fast CLI/package self-tests.")
    p_self_test.set_defaults(func=cmd_self_test)

    p_onboard = sub.add_parser("onboard", help="Interactive DALI onboarding state machine (LangGraph).")
    p_onboard.add_argument("--workspace", default=".", help="Workspace root where .dali/brain is built.")
    p_onboard.add_argument("--thread-id", default="dali-onboard", help="Checkpoint thread id.")
    p_onboard.set_defaults(func=cmd_onboard)

    p_handoff = sub.add_parser("handoff", help="Inspect and resume collaborator handoff bundles.")
    handoff_sub = p_handoff.add_subparsers(dest="handoff_cmd", required=True)
    p_handoff_create = handoff_sub.add_parser("create", help="Bundle local work for a collaborator.")
    p_handoff_create.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Git repository root (default: current directory).")
    p_handoff_create.add_argument("--output", type=Path, help="New output directory outside the repository.")
    p_handoff_create.add_argument("--run-id", help="Summarize runs/<run-id>/logs and summary.json without copying raw logs.")
    p_handoff_create.add_argument("--prompt-log", type=Path, action="append", default=[], help="Explicit raw transcript to copy; may be repeated.")
    p_handoff_create.add_argument("--include-untracked", action="store_true", help="Copy non-ignored regular untracked files into the bundle.")
    p_handoff_create.add_argument("--max-untracked-mb", type=int, default=50, help="Maximum copied untracked data size (default: 50 MiB).")
    p_handoff_create.add_argument("--what-changed", default="", help="Short summary of the current work.")
    p_handoff_create.add_argument("--next-step", default="", help="Recommended next action or blocker.")
    p_handoff_create.set_defaults(func=cmd_handoff_create)
    p_handoff_apply = handoff_sub.add_parser("apply", help="Validate and apply a handoff bundle.")
    p_handoff_apply.add_argument("bundle", help="Path to the collaborator's handoff bundle.")
    p_handoff_apply.add_argument("--project-root", default=".", help="Target Git checkout (default: current directory).")
    p_handoff_apply.add_argument("--apply", action="store_true", help="Apply changes; without this flag, only validate.")
    p_handoff_apply.set_defaults(func=cmd_handoff_apply)

    args = parser.parse_args()

    if args.cmd == "init-references":
        # Normalize empty string to None-ish
        if not getattr(args, "references_dir", "").strip():
            args.references_dir = ""
        args.extensions = args._parse_exts(args.extensions)
        del args._parse_exts

    if args.cmd == "setup-rag":
        if not args.collection_name.strip():
            args.collection_name = ""
        if args.chunk_size <= 0:
            args.chunk_size = 0
        if args.chunk_overlap <= 0:
            args.chunk_overlap = 0

    args.func(args)


if __name__ == "__main__":
    main()

