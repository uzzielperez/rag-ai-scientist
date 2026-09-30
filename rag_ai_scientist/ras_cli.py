"""The ``ras`` console command: init-project, index, run, skills, report, eval.

Every command runs offline — no network, no model. ``ras run`` is the only
command that writes a new run directory; the others are read-only views over a
finished (or in-progress) run, or reproducible entry points that appear in the
plan's ``command`` fields.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from rag_ai_scientist.harness.config import (
    CONFIG_FILENAME,
    DEFAULTS,
    ConfigError,
    load_config,
    parse_overrides,
)
from rag_ai_scientist.harness.loop import LoopError, run_loop
from rag_ai_scientist.harness.plan import Plan, PlanError
from rag_ai_scientist.harness.rundir import RunDir, RunDirError, list_runs
from rag_ai_scientist.harness.skills import (
    SkillError,
    get_skill,
    list_skills,
    promote_skill,
    read_text,
)

FATAL = (ConfigError, LoopError, RunDirError, PlanError, SkillError)


def _project_root(args: argparse.Namespace) -> Path:
    return Path(args.project_root or Path.cwd()).resolve()


def _overrides(args: argparse.Namespace) -> dict:
    return parse_overrides(list(getattr(args, "set", None) or []))


def _resolve_run(project_root: Path, run_id: str | None) -> RunDir:
    if run_id:
        return RunDir.load(project_root, run_id)
    return RunDir.latest(project_root)


def _maybe_run(project_root: Path, run_id: str | None) -> RunDir | None:
    """Resolve a run when one exists; an explicit --run still fails loudly."""
    try:
        return _resolve_run(project_root, run_id)
    except RunDirError:
        if run_id:
            raise
        return None


def _load(args: argparse.Namespace):
    return load_config(
        project_root=_project_root(args),
        config_path=getattr(args, "config", None),
        overrides=_overrides(args),
    )


def cmd_init_project(args: argparse.Namespace) -> None:
    """Scaffold a project: harness config, corpus dir, golden-set directory."""
    root = _project_root(args)
    config_path = root / CONFIG_FILENAME
    if config_path.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite existing config: {config_path}. Use --force.")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(DEFAULTS, sort_keys=False), encoding="utf-8")

    papers = root / "docs" / "references" / "papers"
    papers.mkdir(parents=True, exist_ok=True)
    golden = root / "evals" / "golden"
    golden.mkdir(parents=True, exist_ok=True)
    readme = golden / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Golden question set\n\n"
            "Exactly one `*.json` / `*.yaml` file in this directory is used by the\n"
            "harness (or point `questions.path` at one explicitly). Each question has:\n\n"
            "- `tier`: 1 (must resolve), 2 or 3 (may miss up to `questions.tier23_min`)\n"
            "- `expect`: `supported` or `unresolved` (negative control)\n"
            "- `expect_keywords`: exact terms that must appear in the retrieved text\n"
            "  for the claim to count as supported\n",
            encoding="utf-8",
        )

    print(f"Wrote: {config_path}")
    print(f"Corpus directory: {papers}")
    print(f"Golden set directory: {golden}")
    print("Next: drop PDFs into the corpus directory, write evals/golden/<set>.json,")
    print("then run `ras run --mode A-retrieval`.")


def cmd_index(args: argparse.Namespace) -> None:
    """Build a deterministic chunk + BM25 index (project-level or for one run)."""
    from rag_ai_scientist.core.retrieval import build_index

    root = _project_root(args)
    config = _load(args)
    if args.run:
        index_dir = RunDir.load(root, args.run).index_dir
    else:
        index_dir = config.data_dir / "index"
    index = build_index(
        project_root=root,
        paths=config.corpus_paths,
        index_dir=index_dir,
        extensions=config.corpus_extensions,
        chunk_chars=config.chunk_chars,
        chunk_overlap=config.chunk_overlap,
    )
    meta = index.meta
    print(
        f"Indexed {meta.get('doc_count')} document(s) into {len(index)} chunk(s) "
        f"at {index_dir}"
    )
    print(f"chunks_sha256: {meta.get('chunks_sha256')}")


def cmd_run(args: argparse.Namespace) -> None:
    """Run the PLAN -> EXECUTE -> VALIDATE -> CORRECT loop for one mode."""
    root = _project_root(args)
    result = run_loop(
        project_root=root,
        config_path=getattr(args, "config", None),
        mode=args.mode,
        overrides=_overrides(args),
        run_id=args.run,
        resume=args.resume,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    else:
        state = "ALL GATES PASSED" if result.ok else "GATES FAILED"
        print(
            f"run {result.run.run_id}: outcome={result.outcome} "
            f"iterations={result.iterations} [{state}]"
        )
        print(f"run directory: {result.run.root}")
        if not result.ok:
            print(f"gap report:    {result.run.gap_md}")
    if not result.ok:
        for gap in result.gaps:
            print(f"gap: {gap}", file=sys.stderr)
        raise SystemExit(1)


def cmd_skills(args: argparse.Namespace) -> None:
    """list / show / promote the skills visible to this project."""
    root = _project_root(args)
    run = _maybe_run(root, args.run)

    if args.skills_command == "list":
        rows = list_skills(root, run=run)
        if not rows:
            print("No skills found.")
            return
        print(f"{'NAME':<32} {'SOURCE':<9} {'SHA256':<14} STEPS")
        for row in rows:
            digest = (row.get("sha256") or "-")[:12]
            steps = ", ".join(row.get("steps") or []) or "-"
            print(f"{row['name']:<32} {row['source']:<9} {digest:<14} {steps}")
        return

    if args.skills_command == "show":
        resolved = get_skill(root, args.name, step=args.step, run=run)
        if args.path:
            print(resolved.path)
        else:
            sys.stdout.write(read_text(resolved))
            if resolved.shadowed:
                print(
                    f"\n# shadowed copies: "
                    + ", ".join(f"{item['source']} ({item['path']})" for item in resolved.shadowed),
                    file=sys.stderr,
                )
        return

    # promote
    if run is None:
        raise SystemExit(
            "No run-scoped skill directory available: run `ras run` first (or pass --run)."
        )
    config = _load(args) if args.config or args.set else load_config(project_root=root)
    source = run.skills_dir / args.name
    entry = promote_skill(
        project_root=root,
        source=source,
        name=args.name,
        version=args.version or str(config.get("skills.version", "0.1.0")),
        run_id=run.run_id,
        golden_score=args.golden_score,
    )
    print(f"Promoted {args.name} -> {entry['path']} (sha256 {entry['sha256']})")


def cmd_report(args: argparse.Namespace) -> None:
    """Re-render report.md for a run from what is on disk."""
    from rag_ai_scientist.harness.report import render_report

    root = _project_root(args)
    run = _resolve_run(root, args.run)
    config = load_config(project_root=root, overrides=_overrides(args))
    plan = Plan.load(run.plan_json) if run.plan_json.exists() else None
    state = run.read_state()
    validation = run.read_json(run.validation_json)
    skills = list_skills(root, run=run)
    text = render_report(
        run=run,
        config=config,
        plan=plan,
        skills=skills,
        validation=validation,
        outcome=str(state.get("outcome") or "ok"),
    )
    run.write_text(run.report_md, text)
    print(f"Report written: {run.report_md} ({len(text.splitlines())} lines)")


def cmd_eval(args: argparse.Namespace) -> None:
    """Score a run's golden-set answers against the configured thresholds."""
    root = _project_root(args)
    run = _resolve_run(root, args.run)
    analysis = run.read_json(run.analysis_map_json)
    if analysis is None:
        raise SystemExit(
            f"Run {run.run_id} has no {run.analysis_map_json.name}. Run `ras run` first."
        )
    config = load_config(project_root=root, overrides=_overrides(args))
    metrics = analysis.get("metrics", {})
    if args.json:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    else:
        print(f"run: {run.run_id}  golden set: {(analysis.get('golden_set') or {}).get('name')}")
        print(f"{'ID':<6} {'TIER':<5} {'EXPECT':<11} {'STATUS':<11} {'RESULT':<6} REASON")
        for item in analysis.get("items", []):
            reason = item.get("reason") or ""
            print(
                f"{item['id']:<6} {item['tier']:<5} {item['expect']['status']:<11} "
                f"{item['status']:<11} {item['result']:<6} {reason}"
            )
        print()
        print(
            f"supported {metrics.get('supported')}/{metrics.get('questions')}  "
            f"unresolved {metrics.get('unresolved')}  "
            f"tier1 {metrics.get('tier1', {}).get('ratio')}  "
            f"tier23 {metrics.get('tier23', {}).get('ratio')}  "
            f"citations_valid {metrics.get('citations_valid')}"
        )
    tier1_min = float(config.get("questions.tier1_min", 1.0))
    tier23_min = float(config.get("questions.tier23_min", 0.8))
    tier1 = float(metrics.get("tier1", {}).get("ratio") or 0.0)
    tier23 = float(metrics.get("tier23", {}).get("ratio") or 0.0)
    if tier1 < tier1_min or tier23 < tier23_min:
        raise SystemExit(
            f"Below threshold: tier1 {tier1} < {tier1_min} or tier23 {tier23} < {tier23_min}"
        )


def cmd_demo(args: argparse.Namespace) -> None:
    """Run the animated end-to-end show inside a throwaway project."""
    from rag_ai_scientist.demo import main as demo_main

    argv = [flag for flag, on in (("--fast", args.fast), ("--keep", args.keep)) if on]
    raise SystemExit(demo_main(argv))


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--project-root",
        default=None,
        help="Project root containing configs/, evals/, runs/ (default: cwd).",
    )

    parser = argparse.ArgumentParser(
        prog="ras",
        description="Offline, gated retrieval-verification harness (PRD v0.4).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser(
        "init-project", parents=[common], help="Scaffold configs/harness.yaml and data directories."
    )
    p_init.add_argument("--force", action="store_true", help="Overwrite an existing config.")
    p_init.set_defaults(func=cmd_init_project)

    p_index = sub.add_parser("index", parents=[common], help="Build the deterministic chunk index.")
    p_index.add_argument("--config", default=None, help="Path to harness.yaml (default: configs/harness.yaml).")
    p_index.add_argument(
        "--run", default=None, help="Build into runs/<id>/index; default is the project-level index."
    )
    p_index.add_argument("--set", action="append", metavar="KEY=VALUE", default=[], help="Config override.")
    p_index.set_defaults(func=cmd_index)

    p_run = sub.add_parser("run", parents=[common], help="Run the PLAN/EXECUTE/VALIDATE/CORRECT loop.")
    p_run.add_argument("--config", default=None, help="Path to harness.yaml.")
    p_run.add_argument("--mode", default="A-retrieval", help="Loop mode (this release: A-retrieval).")
    p_run.add_argument("--run", default=None, help="Explicit run id (default: generated).")
    p_run.add_argument("--resume", action="store_true", help="Resume an existing run (latest if --run omitted).")
    p_run.add_argument("--set", action="append", metavar="KEY=VALUE", default=[], help="Config override.")
    p_run.add_argument("--json", action="store_true", help="Print the run result as JSON.")
    p_run.set_defaults(func=cmd_run)

    p_skills = sub.add_parser("skills", parents=[common], help="List, show or promote skills.")
    skills_sub = p_skills.add_subparsers(dest="skills_command", required=True)

    p_list = skills_sub.add_parser(
        "list", parents=[common], help="List skills across run/project/cursor/packaged sources."
    )
    p_list.add_argument("--run", default=None, help="Run id (default: latest run, if any).")
    p_list.set_defaults(func=cmd_skills)

    p_show = skills_sub.add_parser("show", parents=[common], help="Print a resolved skill file.")
    p_show.add_argument("name", help="Skill name.")
    p_show.add_argument("--step", default=None, help="Show one step file instead of SKILL.md.")
    p_show.add_argument("--path", action="store_true", help="Print only the resolved path.")
    p_show.add_argument("--run", default=None, help="Run id (default: latest run, if any).")
    p_show.set_defaults(func=cmd_skills)

    p_promote = skills_sub.add_parser(
        "promote", parents=[common], help="Copy a run-scoped skill into the project (human gate)."
    )
    p_promote.add_argument("name", help="Skill name.")
    p_promote.add_argument("--run", default=None, help="Run id (default: latest run, if any).")
    p_promote.add_argument("--config", default=None, help="Path to harness.yaml.")
    p_promote.add_argument("--version", default=None, help="Version to record (default: skills.version).")
    p_promote.add_argument(
        "--golden-score", type=float, default=None, help="Golden-set score at promotion time."
    )
    p_promote.add_argument("--set", action="append", metavar="KEY=VALUE", default=[], help="Config override.")
    p_promote.set_defaults(func=cmd_skills)

    p_report = sub.add_parser("report", parents=[common], help="Re-render report.md for a run.")
    p_report.add_argument("--run", default=None, help="Run id (default: latest run).")
    p_report.add_argument("--set", action="append", metavar="KEY=VALUE", default=[], help="Config override.")
    p_report.set_defaults(func=cmd_report)

    p_eval = sub.add_parser("eval", parents=[common], help="Score a run against the golden set.")
    p_eval.add_argument("--run", default=None, help="Run id (default: latest run).")
    p_eval.add_argument("--set", action="append", metavar="KEY=VALUE", default=[], help="Config override.")
    p_eval.add_argument("--json", action="store_true", help="Print metrics as JSON.")
    p_eval.set_defaults(func=cmd_eval)

    p_demo = sub.add_parser(
        "demo", help="Watch the whole harness work end to end in a throwaway project."
    )
    p_demo.add_argument("--fast", action="store_true", help="No animation or delays (CI mode).")
    p_demo.add_argument("--keep", action="store_true", help="Keep the temp demo project afterwards.")
    p_demo.set_defaults(func=cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except FATAL as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":  # pragma: no cover
    main()
