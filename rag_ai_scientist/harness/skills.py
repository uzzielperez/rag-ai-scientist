"""Planner-generated skills (§4c).

A skill is an artifact of a run, not something the package ships for a domain:
PLAN writes ``runs/<run_id>/skills/<name>/`` in the same layout as the reference
skills in the repository's ``.cursor/skills/`` (``SKILL.md`` plus one file per
planned step). The generated text is a projection of ``artifacts/plan.json``,
it embeds no run id or timestamp, and it therefore hashes identically when the
same inputs are planned twice.

Resolution order (§4c.3): run-scoped → project (``.rag-ai-scientist/skills``)
→ IDE mirror (``.cursor/skills``) → packaged (``_template`` only). Nothing is
ever written into ``site-packages``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rag_ai_scientist.harness.plan import Plan, PlanStep
from rag_ai_scientist.harness.rundir import RunDir, utc_now

GENERATOR_NAME = "deterministic-planner"
GENERATOR_VERSION = "1.0.0"
RUN_ID_PLACEHOLDER = "RUN_ID"

GUIDING_PRINCIPLES = [
    "Work in small, verified steps: run one step, read its gate result, then continue.",
    "Stop at the first failed gate and propose a fix instead of pushing on.",
    "Never overwrite an existing artifact silently; a re-run writes a new run directory.",
    "Confirm before long-running, network or publishing actions.",
    "Read the per-step file before running that step; the files carry no state.",
]


class SkillError(RuntimeError):
    """Raised when a skill cannot be generated, resolved or promoted."""


@dataclass
class GeneratedSkill:
    name: str
    version: str
    path: Path
    files: dict[str, str] = field(default_factory=dict)
    gates: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    plan_sha256: str = ""
    plan_revision: int = 1

    def as_dict(self, *, run: RunDir) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "path": run.run_rel(self.path),
            "files": self.files,
            "generated_from": {"plan_sha256": self.plan_sha256, "plan_revision": self.plan_revision},
            "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION, "prompts": []},
            "gates": self.gates,
            "inputs": self.inputs,
        }

    def digest(self) -> str:
        payload = json.dumps(self.files, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _portable(text: str, run_id: str) -> str:
    """Strip run-specific identifiers so generated skills hash reproducibly."""
    return text.replace(run_id, RUN_ID_PLACEHOLDER)


def render_skill_md(*, name: str, description: str, plan: Plan, run_id: str) -> str:
    lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
        "---",
        "",
        f"# {name}",
        "",
        "## Overview",
        "",
        f"This skill is the human-readable projection of `artifacts/plan.json` "
        f"(mode `{plan.mode}`, revision {plan.revision}) for one corpus. It runs "
        f"{len(plan.steps)} gated steps and stops as soon as a gate fails.",
        "",
        "It reads the corpus through the run's index; it never answers from model "
        "memory, and every claim it records carries a resolvable citation.",
        "",
        "## Guiding principles",
        "",
    ]
    lines += [f"{index}. {text}" for index, text in enumerate(GUIDING_PRINCIPLES, start=1)]
    lines += ["", "## Progress checklist", "", "```text"]
    for index, step in enumerate(plan.steps, start=1):
        lines.append(f"- [ ] Step {index}: {step.name} ({step.id})")
    lines += ["```", "", "## Steps", "", "| Step | File | Gates |", "| --- | --- | --- |"]
    for step in plan.steps:
        lines.append(f"| {step.id} | [`{step.id}.md`]({step.id}.md) | {', '.join(step.gate_ids)} |")
    lines += [
        "",
        "## Boundaries",
        "",
        "- Read-only with respect to the corpus and the source documents.",
        "- Writes only inside the run directory (`runs/RUN_ID/`).",
        "- Does not download models, call the network or publish anything.",
        "",
    ]
    return _portable("\n".join(lines), run_id)


def render_step_md(*, skill_name: str, step: PlanStep, run_id: str) -> str:
    lines = [
        f"# {step.name}",
        "",
        f"Skill: `{skill_name}` · step id: `{step.id}` · kind: `{step.kind}`",
        "",
        "## Purpose",
        "",
        step.description or step.name,
        "",
        "## Preconditions",
        "",
    ]
    lines += [f"- `{item}` exists and is readable" for item in step.reads] or ["- none"]
    lines += ["", "## Command", "", "```bash", step.command or "echo 'no command'", "```", ""]
    lines += ["## Expected artifacts", ""]
    lines += [f"- `{item}`" for item in step.produces] or ["- none"]
    lines += ["", "## Gate that decides pass/fail", ""]
    for gate in step.gates:
        lines.append(f"- `{gate.id}` ({gate.type}) — {gate.description}")
    lines += ["", "## If it fails", ""]
    if step.remedies:
        for remedy in step.remedies:
            flat: list[str] = []
            for key, value in remedy.overrides.items():
                if isinstance(value, dict):
                    flat += [f"{key}.{sub}={sub_value}" for sub, sub_value in value.items()]
                else:
                    flat.append(f"{key}={value}")
            overrides = ", ".join(f"`{item}`" for item in flat)
            lines.append(
                f"- Proposed fix `{remedy.id}`: {remedy.description} "
                f"(overrides {overrides or 'none'})"
            )
    else:
        lines.append("- No automatic fix is declared; inspect the gate detail and revise the plan.")
    lines += [
        "",
        "## Reporting",
        "",
        f"- Record the gate result for `{step.id}` in `artifacts/validation.json`.",
        "- Quote the citation (`file`, `page`, `chunk_id`, `hash`) for anything you assert.",
        "",
    ]
    return "\n".join(lines)


def generate_skill(
    *,
    run: RunDir,
    plan: Plan,
    name: str,
    description: str,
    version: str,
    plan_sha256: str,
    inputs: list[str],
) -> GeneratedSkill:
    """Write the run-scoped skill directory for one planned capability."""
    directory = run.skills_dir / name
    directory.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}

    skill_md = render_skill_md(name=name, description=description, plan=plan, run_id=run.run_id)
    (directory / "SKILL.md").write_text(skill_md, encoding="utf-8")
    files["SKILL.md"] = _sha256_text(skill_md)
    for step in plan.steps:
        step_md = render_step_md(skill_name=name, step=step, run_id=run.run_id)
        (directory / f"{step.id}.md").write_text(step_md, encoding="utf-8")
        files[f"{step.id}.md"] = _sha256_text(step_md)

    return GeneratedSkill(
        name=name,
        version=version,
        path=directory,
        files=files,
        gates=plan.gate_ids,
        inputs=inputs,
        plan_sha256=plan_sha256,
        plan_revision=plan.revision,
    )


@dataclass
class ResolvedSkill:
    name: str
    step: str | None
    path: Path
    source: str
    sha256: str
    shadowed: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "step": self.step,
            "path": str(self.path),
            "source": self.source,
            "sha256": self.sha256,
            "shadowed": self.shadowed,
        }


def _skill_filename(step: str | None) -> str:
    return "SKILL.md" if not step else f"{step}.md"


def skill_sources(
    project_root: Path, name: str, step: str | None, *, run: RunDir | None = None
) -> list[tuple[str, Path]]:
    """Candidate locations for a skill, in resolution order."""
    from rag_ai_scientist.project_paths import resolve_project_data_dir

    project_root = Path(project_root).resolve()
    filename = _skill_filename(step)
    candidates: list[tuple[str, Path]] = []
    if run is not None:
        candidates.append(("run", run.skills_dir / name / filename))
    candidates.append(("project", resolve_project_data_dir(project_root) / "skills" / name / filename))
    candidates.append(("cursor", project_root / ".cursor" / "skills" / name / filename))
    candidates.append(("packaged", Path(__file__).resolve().parent.parent / "skills" / name / filename))
    return candidates


def get_skill(
    project_root: Path,
    name: str,
    step: str | None = None,
    *,
    run: RunDir | None = None,
) -> ResolvedSkill:
    """Resolve a skill by name, recording any shadowed copies (§4c.3)."""
    existing: list[dict[str, str]] = []
    for source, path in skill_sources(project_root, name, step, run=run):
        if path.exists():
            if not existing:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                resolved = ResolvedSkill(
                    name=name,
                    step=step,
                    path=path,
                    source=source,
                    sha256=digest,
                    shadowed=[],
                )
            existing.append(
                {
                    "source": source,
                    "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    if not existing:
        raise SkillError(
            f"Skill {name!r} (step={step!r}) not found. Checked: "
            + ", ".join(str(path) for _, path in skill_sources(project_root, name, step, run=run))
        )
    resolved.shadowed = existing[1:]
    return resolved


def read_text(resolved: ResolvedSkill) -> str:
    return resolved.path.read_text(encoding="utf-8")


def list_skills(project_root: Path, *, run: RunDir | None = None) -> list[dict[str, Any]]:
    """List available skills across the resolution order, first source wins."""
    from rag_ai_scientist.project_paths import resolve_project_data_dir

    roots: list[tuple[str, Path]] = []
    if run is not None:
        roots.append(("run", run.skills_dir))
    roots.append(("project", resolve_project_data_dir(project_root) / "skills"))
    roots.append(("cursor", Path(project_root).resolve() / ".cursor" / "skills"))
    roots.append(("packaged", Path(__file__).resolve().parent.parent / "skills"))

    found: dict[str, dict[str, Any]] = {}
    for source, root in roots:
        if not root.is_dir():
            continue
        for directory in sorted(entry for entry in root.iterdir() if entry.is_dir()):
            if directory.name in found:
                continue
            skill_file = directory / "SKILL.md"
            found[directory.name] = {
                "name": directory.name,
                "source": source,
                "path": str(directory),
                "sha256": (
                    hashlib.sha256(skill_file.read_bytes()).hexdigest()
                    if skill_file.exists()
                    else None
                ),
                "steps": sorted(
                    entry.stem for entry in directory.glob("*.md") if entry.name != "SKILL.md"
                ),
            }
    return [found[name] for name in sorted(found)]


def skills_index_path(project_root: Path) -> Path:
    from rag_ai_scientist.project_paths import resolve_project_data_dir

    return resolve_project_data_dir(Path(project_root).resolve()) / "skills" / "index.json"


def read_skills_index(project_root: Path) -> dict[str, Any]:
    path = skills_index_path(project_root)
    if not path.exists():
        return {"schema_version": 1, "skills": []}
    return json.loads(path.read_text(encoding="utf-8"))


def promote_skill(
    *,
    project_root: Path,
    source: Path,
    name: str,
    version: str,
    run_id: str,
    golden_score: float | None = None,
) -> dict[str, Any]:
    """Human promotion gate: copy a run-scoped skill into the project.

    Nothing is written into ``site-packages``; the copy lands in
    ``.rag-ai-scientist/skills/<name>/`` and is registered in ``index.json``.
    """
    import shutil

    source = Path(source)
    if not (source / "SKILL.md").exists():
        raise SkillError(f"{source} does not look like a skill directory (no SKILL.md).")
    destination = skills_index_path(project_root).parent / name
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {}
    for item in sorted(source.iterdir()):
        if item.is_file():
            shutil.copy2(item, destination / item.name)
            files[item.name] = hashlib.sha256((destination / item.name).read_bytes()).hexdigest()

    entry = {
        "name": name,
        "version": version,
        "path": str(destination),
        "sha256": files.get("SKILL.md"),
        "files": files,
        "promoted_at": utc_now(),
        "run_id": run_id,
        "golden_score_at_promotion": golden_score,
    }
    index = read_skills_index(project_root)
    entries = [item for item in index.get("skills", []) if item.get("name") != name]
    entries.append(entry)
    index = {"schema_version": 1, "skills": sorted(entries, key=lambda item: item["name"])}
    path = skills_index_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return entry


def mirror_to_cursor(*, project_root: Path, skill: GeneratedSkill) -> tuple[bool, str]:
    """Opt-in IDE mirror; a hash mismatch is reported instead of hidden."""
    import shutil

    target = Path(project_root).resolve() / ".cursor" / "skills" / skill.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(skill.path, target)
    for relative, expected in skill.files.items():
        candidate = target / relative
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest() if candidate.exists() else None
        if actual != expected:
            return False, f"mirror of {relative!r} diverges (expected {expected}, found {actual})"
    return True, f"mirrored to {target}"
