#!/usr/bin/env python3
"""Generate smoke markers for cursor rules checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with Path(args.config).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    results = []
    for test in config["tests"]:
        markers = {marker: True for marker in test["expected_markers"]}
        results.append({"id": test["id"], "markers": markers})

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump({"results": results}, handle, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
