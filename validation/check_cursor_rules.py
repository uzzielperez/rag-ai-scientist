#!/usr/bin/env python3
"""Smoke-check expected Cursor rule markers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--smoke", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with Path(args.config).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    with Path(args.smoke).open("r", encoding="utf-8") as handle:
        smoke = json.load(handle)

    smoke_map = {item["id"]: item for item in smoke.get("results", [])}
    checks: list[dict[str, Any]] = []
    for test in config["tests"]:
        got = smoke_map.get(test["id"], {"markers": {}})
        missing = [m for m in test["expected_markers"] if not got["markers"].get(m, False)]
        checks.append(
            {
                "id": test["id"],
                "pass": len(missing) == 0,
                "missing_markers": missing,
                "prompt": test["prompt"],
            }
        )

    passed = sum(1 for row in checks if row["pass"])
    payload = {"summary": f"{passed}/{len(checks)} rule checks passed", "checks": checks}

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(payload["summary"])


if __name__ == "__main__":
    main()
