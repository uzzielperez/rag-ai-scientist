"""Terminal show for rag-ai-scientist — watch the harness work end to end.

Three ways to run the same show::

    ras demo                            # animated, ~60 s
    python -m rag_ai_scientist.demo     # identical, via the module
    python scripts/demo.py --keep       # repo wrapper; keeps the temp project

The show creates a temporary project, writes a four-file demo corpus and a
golden question set, then drives the real ``ras`` CLI exactly as a user would:

    ras init-project -> ras index -> ras run -> ras eval -> ras skills -> ras report

Everything runs offline (the index is lexical: no model, no network) and
nothing outside the temp directory is touched.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"


class Show:
    """Tiny presentation layer: typewriter narration, banners, streamed output."""

    def __init__(self, animate: bool, color: bool) -> None:
        self.animate = animate
        self.color = color

    def paint(self, text: str, code: str) -> str:
        return f"{code}{text}{RESET}" if (code and self.color) else text

    def sleep(self, seconds: float) -> None:
        if self.animate:
            time.sleep(seconds)

    def line(self, text: str = "", code: str = "") -> None:
        print(self.paint(text, code), flush=True)

    def type(self, text: str, code: str = "", cps: float = 110) -> None:
        """Narration: type the characters, then settle the line in color."""
        if not self.animate:
            self.line(text, code)
            return
        for char in text:
            print(char, end="", flush=True)
            time.sleep(1 / cps)
        print(f"\r\033[2K{self.paint(text, code)}", flush=True)

    def chapter(self, number: str, title: str, *paragraphs: str) -> None:
        self.sleep(0.5)
        rule = "─" * 60
        self.line()
        self.line(rule, DIM)
        self.line(f"  ACT {number} · {title}", BOLD + MAGENTA)
        self.line(rule, DIM)
        self.sleep(0.3)
        for text in paragraphs:
            self.line()
            self.type(f"  ▸ {text}", CYAN)
            self.sleep(0.45)

    def pause(self, seconds: float = 0.8) -> None:
        self.sleep(seconds)

    def command(self, ras_args: list[str], *, max_lines: int | None = None) -> tuple[int, str | None]:
        """Run `ras <args>` as a subprocess and stream its output, colored."""
        display = "ras " + " ".join(ras_args)
        self.line()
        self.line(f"  $ {display}", BOLD + YELLOW)
        self.sleep(0.25)
        proc = subprocess.Popen(
            [sys.executable, "-m", "rag_ai_scientist.ras_cli", *ras_args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        run_id: str | None = None
        shown = 0
        assert proc.stdout is not None
        for raw in proc.stdout:
            text = raw.rstrip("\n")
            if max_lines is not None and shown >= max_lines:
                continue
            self.line(f"  {text}", _classify(text))
            match = re.match(r"run (\S+): outcome=", text)
            if match:
                run_id = match.group(1)
            shown += 1
            if self.animate:
                time.sleep(0.03)
        rc = proc.wait()
        if max_lines is not None and shown >= max_lines:
            self.line(f"  … output truncated ({shown} lines shown)", DIM)
        self.line(
            f"  [{ 'ok' if rc == 0 else f'exit {rc}' }]",
            BOLD + GREEN if rc == 0 else BOLD + RED,
        )
        return rc, run_id


# --------------------------------------------------------------------------- #
# Demo content: four short notes + a golden set with a negative control.
# Each fact lives in exactly one file, so every distinctive term appears in
# 1/4 of the chunks (<= 50%) and counts as informative for retrieval.min_terms.
# --------------------------------------------------------------------------- #

CORPUS_FILES: dict[str, str] = {
    "luminosity.md": (
        "# Aurora run 2025 — data summary\n\n"
        "The Aurora detector recorded an integrated luminosity of 9 fb-1 "
        "in the 2025 physics run.\n"
        "Accumulated data were quality-assured every week by the data-quality group.\n"
    ),
    "selection.md": (
        "# Candidate selection\n\n"
        "B-meson candidates are selected in a mass window from 5260 to 5300 MeV.\n"
        "Only candidates with two identified muons are retained for the amplitude fit.\n"
    ),
    "calibration.md": (
        "# Momentum-scale calibration\n\n"
        "The momentum-scale calibration constant is 3.1416, fixed during the "
        "commissioning run.\n"
        "A residual alignment correction is applied to the tracking detector.\n"
    ),
    "performance.md": (
        "# Particle-identification performance\n\n"
        "The particle-identification efficiency for muons above 10 GeV is 94.2 percent.\n"
        "The readout bandwidth caps the trigger rate at 1.2 kHz.\n"
    ),
}

GOLDEN_SET = {
    "name": "aurora-demo",
    "questions": [
        {
            "id": "Q01",
            "tier": 1,
            "question": "What integrated luminosity did the Aurora detector record?",
            "expect": "supported",
            "expect_keywords": ["9 fb", "luminosity"],
        },
        {
            "id": "Q02",
            "tier": 1,
            "question": "What mass window from 5260 to 5300 MeV is used for candidates?",
            "expect": "supported",
            "expect_keywords": ["5260", "5300"],
        },
        {
            "id": "Q03",
            "tier": 2,
            "question": "What particle-identification efficiency for muons is quoted?",
            "expect": "supported",
            "expect_keywords": ["94.2"],
        },
        {
            "id": "Q04",
            "tier": 2,
            "question": "What is the magnetic field strength of the Aurora solenoid?",
            "expect": "unresolved",
            "expect_keywords": ["magnetic field"],
        },
    ],
}


def write_demo_content(project: Path) -> None:
    papers = project / "docs" / "references" / "papers"
    papers.mkdir(parents=True, exist_ok=True)
    for name, text in CORPUS_FILES.items():
        (papers / name).write_text(text, encoding="utf-8")
    golden_dir = project / "evals" / "golden"
    golden_dir.mkdir(parents=True, exist_ok=True)
    import json

    (golden_dir / "aurora.json").write_text(
        json.dumps(GOLDEN_SET, indent=2) + "\n", encoding="utf-8"
    )


def show_file(show: Show, path: Path, *, max_lines: int = 24) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    show.line()
    show.line(f"  ── {path.name} {'─' * max(4, 42 - len(path.name))}", DIM)
    for number, text in enumerate(lines[:max_lines], 1):
        show.line(f"  {number:>3} │ {text}", DIM)
    if len(lines) > max_lines:
        show.line(f"      … {len(lines) - max_lines} more lines", DIM)
    show.pause(0.6)


def show_tree(show: Show, root: Path, *, limit: int = 40) -> None:
    show.line()
    show.line(f"  ── {root.name}/ {'─' * max(4, 44 - len(root.name))}", DIM)
    entries = sorted(root.rglob("*"))
    for path in entries[:limit]:
        rel = path.relative_to(root)
        if path.is_dir():
            show.line(f"  {rel}/", DIM)
        else:
            show.line(f"  {rel}  ({path.stat().st_size} B)", DIM)
    if len(entries) > limit:
        show.line(f"  … {len(entries) - limit} more entries", DIM)
    show.pause(0.6)



def _classify(text: str) -> str:
    low = text.lower()
    if "all gates passed" in low or "outcome=ok" in low:
        return BOLD + GREEN
    if "fail" in low or "error" in low or "traceback" in low:
        return RED
    if text.startswith("run ") and "outcome=" in text:
        return BOLD + GREEN
    if " pass" in low or low.endswith("pass") or "\tpass" in low:
        return GREEN
    if text.startswith("Wrote:") or "directory:" in text or text.startswith("Corpus"):
        return CYAN
    return DIM



def title_card(show: Show) -> None:
    show.line()
    show.line("  ╭──────────────────────────────────────────────────────╮", BOLD + CYAN)
    show.line("  │   RAG-AI-SCIENTIST  ·  THE HARNESS, LIVE             │", BOLD + CYAN)
    show.line("  │   offline · deterministic · gate by gate             │", BOLD + CYAN)
    show.line("  ╰──────────────────────────────────────────────────────╯", BOLD + CYAN)
    show.line()
    show.type("  A short show: real commands, real output, a throwaway project.", DIM)
    show.type("  Nothing in your repo is touched. Ctrl-C leaves the theater.", DIM)
    show.line()


def must(show: Show, ras_args: list[str], project: Path, *, max_lines: int | None = None) -> str | None:
    rc, run_id = show.command(ras_args, max_lines=max_lines)
    if rc != 0:
        show.line()
        show.line(f"  ✖ the show stopped at: ras {ras_args[0]} (exit {rc})", BOLD + RED)
        raise SystemExit(rc)
    return run_id


def run_show(show: Show, project: Path) -> None:
    root = str(project)

    title_card(show)
    show.line(f"  demo project: {project}", DIM)
    show.line()

    show.chapter(
        "1", "SCAFFOLD",
        "Every project starts the same way: ras init-project writes the harness "
        "config, an empty corpus folder and a golden-set folder.",
    )
    must(show, ["init-project", "--project-root", root], project)
    show_file(show, project / "configs" / "harness.yaml")

    show.chapter(
        "2", "THE CORPUS",
        "Documents go into docs/references/papers. The show drops in four short "
        "notes holding four facts: 9 fb-1, 5260-5300 MeV, 3.1416, 94.2%.",
        "The golden set is the exam: three questions we expect supported, plus a "
        "negative control - the solenoid field - that is deliberately NOT in the "
        "corpus. A harness that invents that answer fails.",
    )
    write_demo_content(project)
    show_file(show, project / "docs" / "references" / "papers" / "selection.md")
    show_file(show, project / "evals" / "golden" / "aurora.json")

    show.chapter(
        "3", "INDEX",
        "ras index chunks the corpus into a local lexical index. No model, no "
        "network, no API keys - this is why the whole show runs offline.",
    )
    must(show, ["index", "--project-root", root], project)

    show.chapter(
        "4", "THE LOOP",
        "Now the main act: ras run plans the work (PLAN), executes each step "
        "(EXECUTE) and lets gates decide whether the output is acceptable "
        "(VALIDATE). Gates are the only thing allowed to say \"this is fine\".",
        "If a gate fails, the loop CORRECTs with a pre-declared remedy - e.g. "
        "lowering the score threshold - and retries, up to run.max_attempts.",
    )
    run_id = must(show, ["run", "--project-root", root], project)
    if not run_id:
        raise SystemExit("ras run did not report a run id")
    show.pause(0.6)
    show.line(f"  ★ ALL GATES PASSED - run {run_id}", BOLD + GREEN)
    show_tree(show, project / "runs" / run_id)

    show.chapter(
        "5", "THE SCORE",
        "ras eval grades the run against the golden set: tier-1 questions must "
        "resolve (1.0), tier-2/3 must reach 0.8, every citation must point at "
        "retrieved text, and the negative control must stay unresolved.",
    )
    must(show, ["eval", "--project-root", root, "--run", run_id], project)

    show.chapter(
        "6", "THE SKILL",
        "A passing run leaves a skill behind: SKILL.md plus one file per planned "
        "step, generated from plan.json. ras skills promote moves it into the "
        "project so later runs (and your IDE) can reuse it.",
    )
    must(show, ["skills", "list", "--project-root", root, "--run", run_id], project)
    must(
        show,
        ["skills", "show", "retrieval-verification", "--project-root", root, "--run", run_id],
        project,
        max_lines=30,
    )

    show.chapter(
        "7", "THE REPORT",
        "Last: report.md - a reproducible one-pager with the config hash, the "
        "gate results and the exact commands to re-run everything.",
    )
    must(show, ["report", "--project-root", root, "--run", run_id], project)
    show_file(show, project / "runs" / run_id / "report.md", max_lines=28)

    show.line()
    show.line("  " + "─" * 58, DIM)
    show.line("  FINALE - WHAT YOU JUST WATCHED", BOLD + MAGENTA)
    show.line("  " + "─" * 58, DIM)
    for text in (
        "scaffold -> corpus -> index -> loop -> gates -> score -> skill -> report",
        "every claim carries a citation into retrieved text; nothing is trusted",
        "the run directory journals everything: manifest, state, trace, events",
    ):
        show.line()
        show.type(f"  ✓ {text}", GREEN)
    show.line()
    show.line("  YOUR TURN", BOLD + YELLOW)
    show.line("    ras init-project --project-root ~/my-paper")
    show.line("    # drop PDFs into   ~/my-paper/docs/references/papers/")
    show.line("    # add questions to ~/my-paper/evals/golden/*.json")
    show.line("    ras run  --project-root ~/my-paper")
    show.line("    ras eval --project-root ~/my-paper")
    show.line()
    show.line("  reference: docs/harness.md  ·  every command: ras --help", DIM)
    show.line()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ras demo",
        description="Watch rag-ai-scientist work: a terminal show driving the real ras CLI.",
    )
    parser.add_argument("--fast", action="store_true", help="No animation or delays (CI mode).")
    parser.add_argument("--keep", action="store_true", help="Keep the temp demo project afterwards.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    tty = sys.stdout.isatty()
    show = Show(animate=tty and not args.fast, color=tty and "NO_COLOR" not in os.environ)

    probe = subprocess.run(
        [sys.executable, "-m", "rag_ai_scientist.ras_cli", "--help"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if probe.returncode != 0:
        print("rag-ai-scientist is not importable. Install it first:", file=sys.stderr)
        print("  pip install rag-ai-scientist", file=sys.stderr)
        return 2

    project = Path(tempfile.mkdtemp(prefix="ras-demo-")).resolve()
    code = 0
    try:
        run_show(show, project)
    except KeyboardInterrupt:
        show.line()
        show.line("  curtain call - demo interrupted", BOLD + YELLOW)
        code = 130
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) and exc.code != 0 else 1
    finally:
        if args.keep or code:
            show.line(f"  demo project kept at: {project}", YELLOW)
        else:
            shutil.rmtree(project, ignore_errors=True)
            show.line(f"  demo project removed ({project})", DIM)
        show.line()
    return code


if __name__ == "__main__":
    raise SystemExit(main())

