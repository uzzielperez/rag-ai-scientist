#!/usr/bin/env python3
"""Compatibility wrapper to build .cursor/rag_db from repo configs."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / ".cursor" / "rag_db"

    config_path = Path(args.config) if args.config else repo_root / "configs" / "references.yaml"
    if not config_path.exists():
        config_path = repo_root / "configs" / "references.example.yaml"

    if args.force and out_dir.exists():
        shutil.rmtree(out_dir)

    cmd = [
        sys.executable,
        str(repo_root / "rag" / "index_documents.py"),
        "--config",
        str(config_path),
        "--output-dir",
        str(out_dir),
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
