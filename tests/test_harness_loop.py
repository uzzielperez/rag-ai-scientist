"""End-to-end and unit tests for the domain-free harness (PRD v0.4).

The corpus is a tiny markdown file so the whole suite runs offline and in
milliseconds — no PDF extraction, no model, no network.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from rag_ai_scientist.harness.config import ConfigError, load_config, parse_overrides
from rag_ai_scientist.harness.gates import GateContext, GateSpec, run_gate
from rag_ai_scientist.harness.loop import run_loop
from rag_ai_scientist.harness.plan import Plan
from rag_ai_scientist.harness.planner import PlannerError, build_plan
from rag_ai_scientist.harness.rundir import RunDir, RunDirError
from rag_ai_scientist.harness.steps import load_golden_set, StepError

CORPUS = (
    "# Alpha detector note\n\n"
    "The experiment used an integrated luminosity of 9 fb-1 with the alpha detector.\n"
    "Candidates are selected in a mass window from 5260 to 5300 MeV.\n"
    "The calibration constant is 3.1416 as measured in the commissioning run.\n"
)

GOLDEN = {
    "name": "mini",
    "questions": [
        {
            "id": "Q01",
            "tier": 1,
            "question": "What integrated luminosity of 9 fb was collected by the alpha detector?",
            "expect": "supported",
            "expect_keywords": ["9 fb", "luminosity"],
        },
        {
            "id": "Q02",
            "tier": 1,
            "question": "What is the mass window in MeV from 5260 to 5300?",
            "expect": "supported",
            "expect_keywords": ["5260", "5300"],
        },
        {
            "id": "Q03",
            "tier": 2,
            "question": "What value of the angle gamma is quoted in this note?",
            "expect": "unresolved",
            "expect_keywords": ["angle gamma"],
        },
    ],
}


def _make_project(root: Path, *, golden: dict | None = None, corpus: str = CORPUS) -> Path:
    docs = root / "docs" / "references" / "papers"
    docs.mkdir(parents=True)
    (docs / "note.md").write_text(corpus, encoding="utf-8")
    golden_dir = root / "evals" / "golden"
    golden_dir.mkdir(parents=True)
    payload = golden if golden is not None else GOLDEN
    (golden_dir / "set.json").write_text(json.dumps(payload), encoding="utf-8")
    # Small chunks (the minimum allowed) so the one-file corpus splits into
    # several chunks; only terms in <=50% of chunks are "informative" for min_terms.
    configs = root / "configs"
    configs.mkdir()
    (configs / "harness.yaml").write_text(
        yaml.safe_dump({"index": {"chunk_chars": 200, "chunk_overlap": 0}}),
        encoding="utf-8",
    )
    return root


def _real_root(tmp: str) -> Path:
    # macOS: /var is a symlink to /private/var; resolve so equality holds.
    return Path(tmp).resolve()


class ConfigTests(unittest.TestCase):
    def test_defaults_load_without_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            config = load_config(project_root=root)
            self.assertEqual(config.mode, "A-retrieval")
            self.assertEqual(config.chunk_chars, 1200)
            self.assertEqual(config.top_k, 5)

    def test_overrides_are_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            with self.assertRaises(ConfigError):
                load_config(project_root=root, overrides=parse_overrides(["retrieval.no_such=1"]))

    def test_dotted_override_applies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            config = load_config(project_root=root, overrides=parse_overrides(["retrieval.top_k=8"]))
            self.assertEqual(config.top_k, 8)
            self.assertEqual(config.get("retrieval.top_k"), 8)

    def test_unknown_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            with self.assertRaises(ConfigError):
                load_config(project_root=root, mode="B")


class GoldenSetTests(unittest.TestCase):
    def test_loads_valid_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _real_root(tmp) / "set.json"
            path.write_text(json.dumps(GOLDEN), encoding="utf-8")
            golden = load_golden_set(path)
            self.assertEqual(len(golden.questions), 3)
            self.assertEqual(golden.questions[0].tier, 1)
            self.assertEqual(golden.questions[2].expect, "unresolved")

    def test_rejects_bad_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _real_root(tmp) / "set.json"
            bad = {"questions": [{"id": "Q", "tier": 9, "question": "?", "expect_keywords": ["x"]}]}
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(StepError):
                load_golden_set(path)

    def test_rejects_missing_keywords(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _real_root(tmp) / "set.json"
            bad = {"questions": [{"id": "Q", "tier": 1, "question": "?"}]}
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(StepError):
                load_golden_set(path)


class PlanTests(unittest.TestCase):
    def test_plan_is_deterministic_and_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            config = load_config(project_root=root)
            plan_a = build_plan(config, "run-1")
            plan_b = build_plan(config, "run-1")
            self.assertEqual(plan_a.as_dict(), plan_b.as_dict())
            self.assertEqual([step.id for step in plan_a.steps], ["index", "answer", "skills", "report"])
            for step in plan_a.steps:
                self.assertTrue(step.gates, f"step {step.id} declares no gates")
                self.assertTrue(step.command.startswith("ras "))

    def test_unknown_mode_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            config = load_config(project_root=root)
            config.raw["run"]["mode"] = "Z"  # bypass loader validation on purpose
            with self.assertRaises(PlannerError):
                build_plan(config, "run-1")

    def test_plan_round_trips_through_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            config = load_config(project_root=root)
            plan = build_plan(config, "run-1")
            target = root / "plan.json"
            plan.save(target)
            loaded = Plan.load(target)
            self.assertEqual(loaded.as_dict(), plan.as_dict())


class GateTests(unittest.TestCase):
    def test_unknown_gate_type_is_a_failure_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            config = load_config(project_root=root)
            run = RunDir.create(root, "t")
            context = GateContext(run=run, config=config, plan=None, skills=[])
            spec = GateSpec(id="mystery", type="no_such_gate", params={}, description="?")
            result = run_gate(spec, context)
            self.assertFalse(result.passed)
            self.assertIn("not enforced", result.detail)

    def test_broken_gate_is_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            config = load_config(project_root=root)
            run = RunDir.create(root, "t")
            context = GateContext(run=run, config=config, plan=None, skills=[])
            spec = GateSpec(
                id="bad",
                type="json_min_items",
                params={"path": "artifacts/analysis_map.json", "key": "items", "min": "not-a-number"},
                description="?",
            )
            result = run_gate(spec, context)
            self.assertFalse(result.passed)
            self.assertIn("gate raised", result.detail)

    def test_file_exists_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            config = load_config(project_root=root)
            run = RunDir.create(root, "t")
            (run.root / "thing.txt").write_text("x", encoding="utf-8")
            context = GateContext(run=run, config=config, plan=None, skills=[])
            spec = GateSpec(
                id="files", type="file_exists", params={"paths": ["thing.txt"]}, description="?"
            )
            self.assertTrue(run_gate(spec, context).passed)
            spec_missing = GateSpec(
                id="missing", type="file_exists", params={"paths": ["nope.txt"]}, description="?"
            )
            self.assertFalse(run_gate(spec_missing, context).passed)


class RunDirTests(unittest.TestCase):
    def test_refuses_to_write_outside_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            run = RunDir.create(root, "t")
            with self.assertRaises(RunDirError):
                run.write_text(root / "escape.txt", "nope")

    def test_run_rel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _real_root(tmp)
            run = RunDir.create(root, "t")
            self.assertEqual(run.run_rel(run.state_json), "state.json")


class EndToEndTests(unittest.TestCase):
    def test_full_loop_passes_on_minimal_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(_real_root(tmp))
            result = run_loop(project_root=root, overrides={"retrieval": {"min_score": 0.5}})
            self.assertTrue(
                result.ok,
                f"outcome={result.outcome} gaps={result.gaps} "
                f"failures={result.validation.get('failures')}",
            )
            self.assertTrue(result.validation["all_passed"])

            report = result.run.report_md.read_text(encoding="utf-8")
            for section in (
                "Summary", "Corpus and index", "Plan", "Golden set coverage",
                "Unresolved", "Validation", "Generated skills", "Reproduce", "Artifacts",
            ):
                self.assertIn(f"## {section}", report)

            analysis = result.run.read_json(result.run.analysis_map_json)
            items = {item["id"]: item for item in analysis["items"]}
            self.assertEqual(items["Q01"]["status"], "supported")
            self.assertTrue(items["Q01"]["evidence"], "supported claim carries no citation")
            self.assertEqual(items["Q03"]["status"], "unresolved")
            self.assertEqual(analysis["metrics"]["tier1"]["ratio"], 1.0)
            self.assertTrue(analysis["metrics"]["citations_valid"])

            manifest = result.run.read_manifest()
            self.assertEqual(manifest["outcome"], "ok")
            self.assertTrue(any(f.get("role") == "golden_set" for f in manifest["input_files"]))

            skill_dir = result.run.skills_dir / "retrieval-verification"
            self.assertTrue((skill_dir / "SKILL.md").exists())

    def test_loop_records_gap_and_remedies_when_corpus_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(_real_root(tmp), corpus="# Empty note\n\nNothing here to retrieve.\n")
            result = run_loop(project_root=root, overrides={"retrieval": {"min_score": 0.5}})
            self.assertFalse(result.ok)
            self.assertEqual(result.outcome, "gap")
            self.assertTrue((result.run.root / "gap.md").exists())
            self.assertFalse(result.validation["all_passed"])
            state = result.run.read_state()
            # CORRECT tried pre-declared remedies before giving up.
            self.assertTrue(state.get("applied_remedies"))

    def test_resume_skips_completed_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_project(_real_root(tmp))
            first = run_loop(project_root=root, overrides={"retrieval": {"min_score": 0.5}})
            self.assertTrue(first.ok)
            resumed = run_loop(
                project_root=root, run_id=first.run.run_id, resume=True
            )
            self.assertTrue(resumed.ok)
            self.assertEqual(resumed.steps["index"]["status"], "resumed")
            self.assertEqual(resumed.steps["answer"]["status"], "resumed")


class RasCliTests(unittest.TestCase):
    def test_run_command_parses(self):
        from rag_ai_scientist.ras_cli import build_parser

        args = build_parser().parse_args(
            ["run", "--mode", "A-retrieval", "--project-root", "/tmp/x",
             "--set", "retrieval.top_k=8"]
        )
        self.assertEqual(args.command, "run")
        self.assertEqual(args.mode, "A-retrieval")
        self.assertEqual(args.set, ["retrieval.top_k=8"])

    def test_skills_show_requires_name(self):
        from rag_ai_scientist.ras_cli import build_parser

        with self.assertRaises(SystemExit):
            build_parser().parse_args(["skills", "show"])

    def test_no_profiles_ship_by_default(self):
        from rag_ai_scientist.harness import list_profiles

        self.assertEqual(list_profiles(), [])


if __name__ == "__main__":
    unittest.main()
