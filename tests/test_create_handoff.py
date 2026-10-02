import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "create_handoff.py"


class CreateHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "project"
        self.root.mkdir()
        self.output = Path(self.temp_dir.name) / "bundle"
        self.receiver = Path(self.temp_dir.name) / "receiver"
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "Test")
        (self.root / "tracked.txt").write_text("base\n", encoding="utf-8")
        self._git("add", "tracked.txt")
        self._git("commit", "-qm", "base")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )

    def _run_handoff(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(self.root), "--output", str(self.output), *args],
            capture_output=True,
            text=True,
        )

    def _run_apply(self, *args):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "rag_ai_scientist.cli",
                "handoff",
                "apply",
                str(self.output),
                "--project-root",
                str(self.receiver),
                *args,
            ],
            cwd=SCRIPT.parents[1],
            capture_output=True,
            text=True,
        )

    def _run_packaged_create(self, *args):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "rag_ai_scientist.cli",
                "handoff",
                "create",
                "--repo-root",
                str(self.root),
                "--output",
                str(self.output),
                *args,
            ],
            cwd=SCRIPT.parents[1],
            capture_output=True,
            text=True,
        )

    def _run_lightweight_create(self, *args):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "rag_ai_scientist.handoff_bundle",
                "create",
                "--repo-root",
                str(self.root),
                "--output",
                str(self.output),
                *args,
            ],
            cwd=SCRIPT.parents[1],
            capture_output=True,
            text=True,
        )

    def _prepare_bundle_and_receiver(self):
        subprocess.run(
            ["git", "clone", "-q", str(self.root), str(self.receiver)],
            check=True,
            capture_output=True,
            text=True,
        )
        (self.root / "tracked.txt").write_text("collaborator change\n", encoding="utf-8")
        (self.root / "new.py").write_text("print('new')\n", encoding="utf-8")
        (self.root / "new.py").chmod(0o755)
        result = self._run_handoff("--include-untracked", "--what-changed", "Collaborator changes.")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bundle_captures_patch_log_summary_transcript_and_untracked_files(self):
        (self.root / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (self.root / "new.py").write_text("print('new')\n", encoding="utf-8")
        logs = self.root / "runs" / "run-1" / "logs"
        logs.mkdir(parents=True)
        (logs / "execution.log").write_text(
            "stage output\n"
            + "".join(f"ERROR: fixture unavailable {index}\n" for index in range(10))
            + "finished\n",
            encoding="utf-8",
        )
        (self.root / "runs" / "run-1" / "summary.json").write_text(
            '{"run_id":"run-1","ok":false,"stages":[{"name":"execution","ok":false,"exit_code":1}]}\n',
            encoding="utf-8",
        )
        transcript = Path(self.temp_dir.name) / "session.jsonl"
        transcript.write_text('{"prompt":"continue"}\n', encoding="utf-8")

        result = self._run_handoff(
            "--run-id", "run-1",
            "--prompt-log", str(transcript),
            "--include-untracked",
            "--what-changed", "Implementing the reliability stages.",
            "--next-step", "Run validation and inspect the report.",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("diff --git a/tracked.txt", (self.output / "git/working-tree.patch").read_text())
        self.assertEqual((self.output / "untracked/new.py").read_text(), "print('new')\n")
        log_summary = self.output / "pipeline_logs/run-1/summary.md"
        self.assertTrue(log_summary.is_file())
        self.assertFalse((self.output / "pipeline_logs/run-1/execution.log").exists())
        self.assertFalse((self.output / "pipeline_logs/run-1/summary.json").exists())
        summary_text = log_summary.read_text()
        self.assertIn("ERROR: fixture unavailable", summary_text)
        self.assertIn("12 lines;", summary_text)
        self.assertLessEqual(summary_text.count("- Line "), 5)
        self.assertIn("`execution`: FAILED (exit 1)", summary_text)
        self.assertTrue((self.output / "prompt_logs/session.jsonl").is_file())
        handoff = (self.output / "HANDOFF.md").read_text()
        self.assertIn("Run validation and inspect the report.", handoff)
        self.assertIn("pipeline_logs/run-1/summary.md", handoff)
        self.assertIn("Current HEAD (patch base)", handoff)
        self.assertIn("Agentic IDE summary request", handoff)
        self.assertIn("essential tasks in priority/dependency order", handoff)
        self.assertIn("git/status.txt", handoff)

    def test_refuses_output_inside_repository(self):
        result = self._run_handoff("--output", str(self.root / "bundle"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside the repository", result.stderr)

    def test_refuses_to_overwrite_existing_output(self):
        self.output.mkdir()
        result = self._run_handoff()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to overwrite", result.stderr)

    def test_packaged_cli_creates_handoff_bundle(self):
        logs = self.root / "runs" / "run-2" / "logs"
        logs.mkdir(parents=True)
        (logs / "execution.log").write_text("all done\n", encoding="utf-8")
        result = self._run_packaged_create(
            "--run-id", "run-2",
            "--include-untracked",
            "--what-changed",
            "Packaged CLI handoff.",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.output / "HANDOFF.md").is_file())
        self.assertTrue((self.output / "manifest.json").is_file())
        self.assertTrue((self.output / "git/working-tree.patch").is_file())
        self.assertTrue((self.output / "pipeline_logs/run-2/summary.md").is_file())
        self.assertFalse((self.output / "pipeline_logs/run-2/execution.log").exists())
        self.assertIn("Agentic IDE summary request", (self.output / "HANDOFF.md").read_text())

    def test_lightweight_cli_creates_bundle_without_yaml_cli(self):
        result = self._run_lightweight_create("--what-changed", "Lightweight handoff.")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.output / "manifest.json").is_file())

    def test_apply_defaults_to_preview_and_applies_bundle_on_request(self):
        self._prepare_bundle_and_receiver()

        preview = self._run_apply()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("rerun with --apply", preview.stdout)
        self.assertEqual((self.receiver / "tracked.txt").read_text(), "base\n")
        self.assertFalse((self.receiver / "new.py").exists())

        applied = self._run_apply("--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual((self.receiver / "tracked.txt").read_text(), "collaborator change\n")
        self.assertEqual((self.receiver / "new.py").read_text(), "print('new')\n")
        self.assertTrue((self.receiver / "new.py").stat().st_mode & 0o111)

    def test_apply_rejects_modified_bundle_and_wrong_base(self):
        self._prepare_bundle_and_receiver()
        patch = self.output / "git" / "working-tree.patch"
        original_patch = patch.read_bytes()
        patch.write_bytes(bytes([original_patch[0] ^ 1]) + original_patch[1:])
        result = self._run_apply("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Checksum mismatch", result.stderr)

        patch.write_bytes(original_patch)
        (self.receiver / "other.txt").write_text("advance base\n", encoding="utf-8")
        subprocess.run(["git", "add", "other.txt"], cwd=self.receiver, check=True)
        subprocess.run(["git", "commit", "-qm", "advance base"], cwd=self.receiver, check=True)
        result = self._run_apply("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires", result.stderr)


if __name__ == "__main__":
    unittest.main()
