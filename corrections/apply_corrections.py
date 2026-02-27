#!/usr/bin/env python3
"""Apply configured corrections and write provenance details."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_sha(path: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(path),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:
        return "unknown"


def apply_scale_corrections(input_payload: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    checks = input_payload.get("checks", [])
    scales = {item["metric"]: float(item["scale"]) for item in registry.get("scale_corrections", [])}
    corrected = []
    for check in checks:
        scale = scales.get(check["name"], 1.0)
        row = dict(check)
        if isinstance(row.get("observed"), (float, int)):
            row["observed"] = float(row["observed"]) * scale
            tolerance = float(row.get("tolerance_abs", 0.0))
            row["pass"] = abs(row["observed"] - float(row["reference"])) <= tolerance
        row["applied_scale"] = scale
        corrected.append(row)
    return {"checks": corrected}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    registry_path = Path(args.registry)
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with registry_path.open("r", encoding="utf-8") as handle:
        registry = yaml.safe_load(handle)
    with input_path.open("r", encoding="utf-8") as handle:
        input_payload = json.load(handle)

    corrected_payload = apply_scale_corrections(input_payload, registry)
    corrected_file = output_dir / "corrected_checks.json"
    corrected_file.write_text(json.dumps(corrected_payload, indent=2, sort_keys=True), encoding="utf-8")

    provenance = {
        "run_id": args.run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "parameters": registry.get("scale_corrections", []),
        "hashes": {
            "input": sha256_file(input_path),
            "registry": sha256_file(registry_path),
            "output": sha256_file(corrected_file),
        },
        "git_sha": git_sha(Path.cwd()),
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
