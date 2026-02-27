#!/usr/bin/env python3
"""Generate observed values file from reference defaults."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with Path(args.reference).open("r", encoding="utf-8") as handle:
        reference = yaml.safe_load(handle)

    observed = {}
    for metric in reference["metrics"]:
        observed[metric["name"]] = metric["reference"]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump({"values": observed}, handle, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
