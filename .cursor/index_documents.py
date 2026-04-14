#!/usr/bin/env python3
"""Compatibility wrapper to build .cursor/rag_db from repo configs."""

from __future__ import annotations

import argparse
import errno
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--collection-name", default="")
    parser.add_argument("--chunk-size", type=int, default=1500)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / ".cursor" / "rag_db"

    config_path = Path(args.config) if args.config else repo_root / "configs" / "references.yaml"
    if not config_path.exists():
        config_path = repo_root / "configs" / "references.example.yaml"

    if args.force and out_dir.exists():
        try:
            shutil.rmtree(out_dir)
        except OSError as e:
            if e.errno != errno.EBUSY:
                raise
            # Clear contents so indexing can proceed; directory may be in use (e.g. ChromaDB, AFS).
            for p in sorted(out_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                try:
                    if p.is_file() or p.is_symlink():
                        p.unlink()
                    else:
                        shutil.rmtree(p)
                except OSError:
                    pass

    cmd = [
        sys.executable,
        str(repo_root / "rag" / "index_documents.py"),
        "--config",
        str(config_path),
        "--output-dir",
        str(out_dir),
        "--chunk-size",
        str(args.chunk_size),
        "--chunk-overlap",
        str(args.chunk_overlap),
    ]
    if args.collection_name:
        cmd.extend(["--collection-name", args.collection_name])
    if args.force:
        cmd.append("--force")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
