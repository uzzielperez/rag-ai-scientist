"""The shipped tutorial and the shipped demo must stay wired to the real CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

import rag_ai_scientist
from rag_ai_scientist import ras_cli

_PKG_DIR = Path(rag_ai_scientist.__file__).resolve().parent
REPO_ROOT = _PKG_DIR.parent
SKILL_DIR = _PKG_DIR / "skills" / "harness-tutorial"
TUTORIAL = REPO_ROOT / "docs" / "TUTORIAL.md"


def _subcommand_names() -> list[str]:
    parser = ras_cli.build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return sorted(action.choices)
    raise AssertionError("ras parser exposes no subcommands")


def test_demo_ships_inside_the_package() -> None:
    from rag_ai_scientist import demo

    parsed = demo.build_arg_parser().parse_args(["--fast", "--keep"])
    assert parsed.fast is True and parsed.keep is True
    assert callable(demo.main)


def test_demo_subcommand_is_registered() -> None:
    assert "demo" in _subcommand_names()
    parser = ras_cli.build_parser()
    assert parser.parse_args(["demo", "--fast"]).func is ras_cli.cmd_demo
    assert parser.parse_args(["demo", "--fast"]).fast is True
    assert parser.parse_args(["demo"]).keep is False


def test_packaged_tutorial_skill_resolves_from_any_project(tmp_path: Path) -> None:
    """A pip-installed user with an empty project still reaches the tutorial."""
    from rag_ai_scientist import mcp_server

    assert SKILL_DIR.is_dir()
    text = mcp_server._load_skill_text(tmp_path, skill="harness-tutorial", step=None)
    assert "ras demo" in text
    assert "negative control" in text


def test_tutorial_documents_every_subcommand() -> None:
    if not TUTORIAL.exists():  # pragma: no cover - installed wheels ship no docs/
        pytest.skip("docs/TUTORIAL.md lives in the source tree")
    body = TUTORIAL.read_text(encoding="utf-8")
    undocumented = [name for name in _subcommand_names() if f"ras {name}" not in body]
    assert not undocumented, f"docs/TUTORIAL.md never mentions: {undocumented}"


def test_repo_wrapper_stays_thin() -> None:
    wrapper = REPO_ROOT / "scripts" / "demo.py"
    if not wrapper.exists():  # pragma: no cover - installed wheels ship no scripts/
        pytest.skip("scripts/demo.py lives in the source tree")
    body = wrapper.read_text(encoding="utf-8")
    assert "from rag_ai_scientist.demo import main" in body
    assert len(body.splitlines()) < 40, "scripts/demo.py must stay a thin wrapper"


def test_speed_flag_stretches_every_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """One pace factor must govern pauses, typing and streamed output alike - no stragglers."""
    from rag_ai_scientist import demo

    waits: list[float] = []
    monkeypatch.setattr("time.sleep", lambda seconds: waits.append(seconds))

    slow = demo.Show(animate=True, color=False, pace=3.0)
    slow.sleep(1.0)
    slow.type("ab", cps=100)
    house = demo.Show(animate=True, color=False)
    house.sleep(1.0)
    house.type("ab", cps=100)

    assert waits == [3.0, 0.03, 0.03, 1.0, 0.01, 0.01]


def test_demo_parser_exposes_the_pace() -> None:
    from rag_ai_scientist import demo

    parser = demo.build_arg_parser()
    assert parser.parse_args([]).speed == 1.0
    assert parser.parse_args(["--slow"]).speed == 2.0
    assert parser.parse_args(["--speed", "0.5"]).speed == 0.5
    assert parser.parse_args(["--speed", "3"]).speed == 3.0
    assert demo.main(["--speed", "0"]) == 2, "a pace of 0 or less must be refused"


def test_ras_demo_forwards_the_pace(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ras demo --slow` has to arrive as `--speed 2`, not be silently dropped."""
    from rag_ai_scientist import demo

    seen: list[list[str]] = []
    monkeypatch.setattr(demo, "main", lambda argv: seen.append(argv) or 0)
    args = ras_cli.build_parser().parse_args(["demo", "--slow", "--keep"])

    with pytest.raises(SystemExit):
        ras_cli.cmd_demo(args)

    assert seen == [["--keep", "--speed", "2.0"]]
