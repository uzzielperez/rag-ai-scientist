from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml


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
    )

    print(f"Wrote: {config_path}")


def cmd_setup_rag(args: argparse.Namespace) -> None:
    project_root = _project_root(args.project_root)
    config_path = project_root / "configs" / "references.yaml"
    if not config_path.exists():
        raise SystemExit(
            f"Missing config: {config_path}. Run `rag-ai-scientist init-references` first."
        )

    out_dir = project_root / ".cursor" / "rag_db"
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="rag-ai-scientist")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init-references", help="Write configs/references.yaml from a references directory.")
    p_init.add_argument("--project-root", default=".", help="Target analysis repo root.")
    p_init.add_argument("--references-dir", default="", help="Directory containing your reference PDFs/MD/TXT/etc.")
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

    p_setup = sub.add_parser("setup-rag", help="Index references and build .cursor/rag_db.")
    p_setup.add_argument("--project-root", default=".", help="Target analysis repo root.")
    p_setup.add_argument("--force", action="store_true", help="Rebuild rag_db from scratch.")
    p_setup.add_argument("--collection-name", default="", help="Override collection name.")
    p_setup.add_argument("--chunk-size", type=int, default=0)
    p_setup.add_argument("--chunk-overlap", type=int, default=0)
    p_setup.set_defaults(func=cmd_setup_rag)

    p_mcp = sub.add_parser("mcp", help="Start MCP server (stdio). Point Cursor's MCP to this command.")
    p_mcp.add_argument("--project-root", default=".", help="Target analysis repo root.")
    p_mcp.set_defaults(func=cmd_mcp)

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

