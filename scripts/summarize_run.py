#!/usr/bin/env python3
"""Write run summary JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root)
    summary = {
        "run_id": args.run_id,
        "artifacts": {
            "checks": str(root / "validation_out/checks.json"),
            "rules": str(root / f"validation_out/rules/{args.run_id}.json"),
            "report_index": str(root / f"validation_out/reports/{args.run_id}/index.html"),
            "corrections_provenance": str(root / f"runs/{args.run_id}/corrections/provenance.json"),
        },
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
