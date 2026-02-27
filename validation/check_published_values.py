#!/usr/bin/env python3
"""Deterministic checks against published/reference values."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def evaluate(metric: dict[str, Any], observed: float) -> dict[str, Any]:
    reference = float(metric["reference"])
    tolerance = float(metric["tolerance_abs"])
    passed = abs(observed - reference) <= tolerance
    return {
        "name": metric["name"],
        "reference": reference,
        "observed": observed,
        "tolerance_abs": tolerance,
        "pass": passed,
        "message": metric.get("message", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--observed", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with Path(args.reference).open("r", encoding="utf-8") as handle:
        reference_cfg = yaml.safe_load(handle)
    with Path(args.observed).open("r", encoding="utf-8") as handle:
        observed_payload = json.load(handle)

    observed_values = observed_payload.get("values", {})
    checks = []
    for metric in reference_cfg["metrics"]:
        value = observed_values.get(metric["name"])
        if value is None:
            checks.append(
                {
                    "name": metric["name"],
                    "reference": metric["reference"],
                    "observed": None,
                    "tolerance_abs": metric["tolerance_abs"],
                    "pass": False,
                    "message": "Metric missing in observed values.",
                }
            )
            continue
        checks.append(evaluate(metric, float(value)))

    passed = sum(1 for row in checks if row["pass"])
    total = len(checks)
    payload = {
        "summary": f"{passed}/{total} checks passed",
        "passed": passed,
        "failed": total - passed,
        "checks": checks,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    # Print a compact CLI table for manual checks.
    print("metric | reference | observed | status")
    for row in checks:
        status = "PASS" if row["pass"] else "FAIL"
        print(f"{row['name']} | {row['reference']} | {row['observed']} | {status}")


if __name__ == "__main__":
    main()
