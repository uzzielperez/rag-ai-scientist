#!/usr/bin/env python3
"""Update LaTeX draft templates with current run metrics."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def to_placeholder(name: str) -> str:
    return "{{" + name.upper() + "}}"


def render_text(template_text: str, replacements: dict[str, str]) -> str:
    rendered = template_text
    for key, value in replacements.items():
        rendered = rendered.replace(to_placeholder(key), value)
    return rendered


def copy_supporting_files(src_dir: Path, dst_dir: Path, skip: set[str]) -> None:
    for item in src_dir.iterdir():
        if item.name in skip:
            continue
        target = dst_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checks", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--templates-config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    with Path(args.checks).open("r", encoding="utf-8") as handle:
        checks_payload = json.load(handle)
    with Path(args.templates_config).open("r", encoding="utf-8") as handle:
        template_cfg = yaml.safe_load(handle)

    observed_values = {
        check["name"]: str(check["observed"])
        for check in checks_payload.get("checks", [])
        if check.get("observed") is not None
    }
    replacements: dict[str, str] = {
        "run_id": args.run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "checks_summary": checks_payload.get("summary", ""),
    }
    replacements.update(observed_values)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    for draft in template_cfg.get("drafts", []):
        template_dir = Path(draft["template_dir"]).expanduser()
        main_file = draft["main_file"]
        template_main = template_dir / main_file
        if not template_main.exists():
            raise FileNotFoundError(f"Missing template main file: {template_main}")

        draft_dir = output_dir / draft["name"]
        draft_dir.mkdir(parents=True, exist_ok=True)
        template_text = template_main.read_text(encoding="utf-8")
        rendered = render_text(template_text, replacements)
        (draft_dir / main_file).write_text(rendered, encoding="utf-8")

        copy_supporting_files(template_dir, draft_dir, skip={main_file})
        generated.append({"name": draft["name"], "path": str(draft_dir / main_file)})

    manifest: dict[str, Any] = {"run_id": args.run_id, "generated": generated}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Generated {len(generated)} paper draft(s) in {output_dir}")


if __name__ == "__main__":
    main()
