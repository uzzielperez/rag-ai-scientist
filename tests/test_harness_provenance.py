import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rag_ai_scientist.harness import Profile, Stage, register_profile, run_harness


class HarnessProvenanceTests(unittest.TestCase):
    def test_run_writes_generic_manifest_with_git_input_and_stage_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "project"
            root.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Harness Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "harness@example.invalid"], cwd=root, check=True)
            config = root / "configs" / "analysis.yaml"
            config.parent.mkdir()
            config.write_text("threshold: 0.1\n", encoding="utf-8")
            input_file = root / "reference.txt"
            input_file.write_text("reference value\n", encoding="utf-8")
            (root / ".gitignore").write_text("/runs/\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)

            profile = Profile(
                name="fixture_provenance",
                description="Fixture profile",
                stages=(Stage(name="check", description="Run fixture command", command=(
                    sys.executable, "-c", "print('stage passed')",
                )),),
            )
            register_profile(profile)
            summary = run_harness(
                project_root=root,
                profile_name="fixture_provenance",
                run_id="fixture-1",
                task_id="task-14",
                seed=42,
                config_paths=("configs/analysis.yaml",),
                input_paths=("reference.txt",),
                dataset_ids=("fixture://reference-v1",),
                metrics={"closure_pull": 0.02},
                software_versions={"ROOT": "6.32.02"},
            )

            manifest_path = Path(summary["manifest_path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["run"]["task_id"], "task-14")
            self.assertEqual(manifest["run"]["status"], "passed")
            self.assertEqual(manifest["execution"]["seed"], 42)
            self.assertEqual(manifest["inputs"]["datasets"], ["fixture://reference-v1"])
            self.assertEqual(manifest["results"]["metrics"], {"closure_pull": 0.02})
            self.assertEqual(manifest["inputs"]["configurations"][0]["path"], "configs/analysis.yaml")
            self.assertEqual(len(manifest["inputs"]["files"][0]["sha256"]), 64)
            self.assertTrue(manifest["source"]["commit"])
            self.assertFalse(manifest["source"]["dirty"])
            self.assertEqual(manifest["results"]["stages"][0]["name"], "check")
            self.assertTrue(manifest["results"]["stages"][0]["ok"])
            self.assertGreaterEqual(manifest["results"]["stages"][0]["detail"]["duration_seconds"], 0)
            self.assertEqual(manifest["environment"]["software_versions"], {"ROOT": "6.32.02"})
            self.assertEqual(manifest["results"]["artifacts"][0]["path"], "runs/harness_fixture_provenance_fixture-1/summary.json")
            with self.assertRaisesRegex(ValueError, "Run ID may contain only"):
                run_harness(
                    project_root=root,
                    profile_name="fixture_provenance",
                    run_id="../escape",
                )
            self.assertFalse((root.parent / "runs").exists())


if __name__ == "__main__":
    unittest.main()