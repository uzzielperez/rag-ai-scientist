"""Build a SWAN-openable notebook that walks through the DALI onboarding flow.

`dali-create-notebook` reads the live flow definition out of `dali_onboard.py`
(nodes, edges, conditional routers, interrupts, gates) and renders a
step-by-step teaching notebook: every node gets its own section with the
source code embedded from the current file, what it guarantees, and a runnable
cell. The last cells drive the real graph with the offline demo project
(no API keys, no model download) and draw the flow diagram.

The notebook is generated, never hand-edited: re-run this tool after every
change to `dali_onboard.py` (see `dali-notebook-sync`, which tells you when
the two have drifted).

SWAN notes:
  - upload the .ipynb to your SWAN project, select the `py312` kernel (or any
    Python >= 3.10), and pip-install the framework in the first cell;
  - SWAN has no internet for pip, so install from CERN's mirror:
    pip install --index-url https://gitlab.cern.ch/api/v4/projects/
    6480/packages/pypi/simple rag-ai-scientist
  - the notebook writes into `dali-notebook-work/` under the notebook dir.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import nbformat

NOTEBOOK_NAME = "DALI_onboarding_flow.ipynb"
MANIFEST_NAME = "dali_notebook_manifest.json"
WORKDIR = "dali-notebook-work"

MARKER_BEGIN = "<!-- DALI-NOTEBOOK-GENERATED-CELL: {name} -->"
MARKER_END = "<!-- /DALI-NOTEBOOK-GENERATED-CELL -->"


def _marker(name: str) -> str:
    return MARKER_BEGIN.format(name=name)


def md_cell(name: str, source: str) -> "nbformat.NotebookNode":
    cell = nbformat.v4.new_markdown_cell(f"{_marker(name)}\n{source}\n{MARKER_END}")
    cell.metadata["dali_cell"] = name
    return cell


def code_cell(name: str, source: str) -> "nbformat.NotebookNode":
    """Code cells carry the provenance marker in cell metadata, not in the
    source: a markdown comment is not valid python and would break the cell."""
    cell = nbformat.v4.new_code_cell(source)
    cell.metadata["dali_cell"] = name
    cell.metadata["dali_generated_from"] = _marker(name)
    return cell

_INSTALL_HELP = (
    "On SWAN pick the **py312** kernel (Python >= 3.10). SWAN has no general "
    "internet, so pip installs go through CERN's mirror:\n\n"
    "```bash\n"
    "pip install --index-url https://gitlab.cern.ch/api/v4/projects/6480/"
    "packages/pypi/simple rag-ai-scientist\n"
    "```\n\n"
    "If you are inside a checkout of `rag-ai-scientist` instead, the cell "
    "below adds the checkout to `sys.path` and needs no install at all."
)

# One section per node, in flow order: (node, section title, teaching text).
# Teaching text explains *why the node exists* and what it guarantees; the
# generator appends the live source of the function itself.
NODE_SECTIONS: list[tuple[str, str, str]] = [
    ("get_inputs", "Step 1 - get_inputs: what are we working on?",
     "**What it does.** The graph starts by asking a human for two things: a "
     "*paper* (the write-up of the result) and a *codebase* (the code that "
     "produced it). `autonomous` decides whether later loop iterations ask "
     "each time or run on approval-once.\n\n"
     "**Why a gate first?** Everything downstream costs time (embeddings) or "
     "trust (execution), so the human's intent is captured verbatim in "
     "`state[\"checks\"][\"inputs\"]` before anything runs.\n\n"
     "**The mechanism.** `interrupt(payload)` pauses the graph and hands the "
     "payload to the driver (the terminal REPL, or the cell below). Resuming "
     "with `Command(resume=answer)` makes the node return that answer. The "
     "checkpoint saves the pause, so you can close the browser and continue "
     "tomorrow."),
    ("check_agent", "Step 2 - check_agent: is there an agent to hand this to?",
     "**What it does.** Looks for the `dali` agent definition in the known "
     "IDE locations (opencode, claude-code, cursor, codex, copilot). If it is "
     "missing it offers `install` (runs the harness installer), `continue` "
     "(brain only), or `abort`.\n\n"
     "**Why before the expensive work?** The onboarding output is meant to be "
     "handed to `/agent dali`. Discovering at the end that nobody can run the "
     "plan wastes the whole embedding run, so the check is placed early and "
     "its outcome is a routing decision (`after_agent`)."),
    ("fetch_inputs", "Step 3 - fetch_inputs: get the paper and the code locally",
     "**What it does.** Local paths are used as-is; `http(s)` URLs are "
     "downloaded into `.dali/onboard/inbox/`. For `gitlab.cern.ch` it tries "
     "`~/.netrc` credentials, because plain fetches cannot complete CERN "
     "Single Sign-On.\n\n"
     "**Failure is a gate, not a crash.** On any error the node explains the "
     "concrete fix (local clone, PAT in `~/.netrc`, public mirror) and lets "
     "the human retry, give corrected paths, or abort. Nothing is silently "
     "skipped: `checks[\"fetch\"]` records exactly what was fetched."),
    ("choose_embedding_model", "Step 4 - choose_embedding_model: size the brain to the machine",
     "**What it does.** `detect_hardware()` reads cores, RAM and the torch "
     "device, recommends a tier (`small` / `base` / `large`), and a human gate "
     "confirms or overrides the choice.\n\n"
     "**Why it matters.** The embedding model defines the geometry of the "
     "whole brain: build with one model, query with another, and every "
     "similarity score is meaningless. `_get_embeddings()` is therefore the "
     "*single* factory used by build, probe and query - see the next section."),
    ("embed_and_chunk", "Step 5 - embed_and_chunk: turn files into retrievable chunks",
     "**What it does.** Walks the paper tree (`.pdf .md .txt .tex .rst`) and "
     "the code tree (`.py .cxx .yaml .sh ...`), extracts text, and splits it "
     "into overlapping chunks (1500/200, or 2000/300 for scientific text) "
     "tagged with `doc_path`, `source_type` and `doc_category`.\n\n"
     "**Why overlap?** A number or a sentence that straddles a chunk boundary "
     "is lost; overlap keeps it whole in at least one chunk. The `doc_path` "
     "tag is what later makes every benchmark traceable to a file."),
    ("build_brain", "Step 6 - build_brain: the persistent vector store",
     "**What it does.** Embeds the chunks into a Chroma collection "
     "(`dali-brain`) persisted at `.dali/brain/`. That directory *is* the "
     "brain: it survives the session, and any later tool that knows the "
     "workspace can query it.\n\n"
     "**Determinism rule.** `build_brain` re-derives the chunks with the same "
     "`_collect_chunks()` the probe uses, so build-time and query-time "
     "preprocessing cannot drift apart."),
    ("test_brain", "Step 7 - test_brain: the human checks the brain before trusting it",
     "**What it does.** The human types a question whose answer they already "
     "know. `_brain_probe()` returns the top hits with cosine scores and "
     "`doc_path`s, printed verbatim. `approve` continues; `rebuild` routes "
     "back to `build_brain` (usually with a bigger model).\n\n"
     "**Why this gate exists.** Every later LLM proposal is grounded in brain "
     "retrieval. If retrieval is off-topic, the plan will be confidently "
     "wrong, so the cheapest possible human test sits directly on top of it."),
    ("summarize", "Step 8 - summarize: what is this analysis, in plain words",
     "**What it does.** Retrieves from the brain and asks the LLM for exactly "
     "three fields: `goal`, `result` (the headline number a reproduction must "
     "land on), and `plan` (the route back from that number to raw data).\n\n"
     "**Guardrail.** Without a key or without retrievable material the node "
     "does not invent a summary: it writes an explicit placeholder and marks "
     "`checks[\"summary\"].ok = False`, so the human knows the machine did not "
     "read anything."),
    ("approve_summary", "Step 9 - approve_summary: gate on the understanding, not the code",
     "**What it does.** Shows the three blocks and asks: is this what your "
     "analysis is? `rebuild` goes back to `build_brain`.\n\n"
     "**Why gate prose?** The plan is generated *from this summary*. A wrong "
     "goal caught here costs one keystroke; caught after the plan it costs the "
     "whole plan."),
    ("plan_dag", "Step 10 - plan_dag: a DAG of verifiable steps with golden benchmarks",
     "**What it does.** Reverse-engineers 4-10 steps from the result back to "
     "the data. Each step carries `command`, `check`, `depends_on` (earlier "
     "ids only, which is what keeps the graph acyclic) and `benchmarks`.\n\n"
     "**The benchmark rule is the core of the harness.** A benchmark is a "
     "reference number that appears *verbatim* in the retrieved material and "
     "carries the `source` path it was read from. No such number -> empty "
     "list -> a human validates that step. `_normalise_plan()` enforces this "
     "and flags everything `extracted-unverified`."),
    ("render_artifacts", "Step 11 - render_artifacts: the plan as files a human can edit",
     "**What it does.** Writes three artifacts with no LLM involvement, so "
     "re-running on the same plan gives byte-identical files:\n\n"
     "| artifact | role |\n|---|---|\n"
     "| `WORKFLOW.md` | plain-language goal, result, steps and benchmarks |\n"
     "| `state/pipeline.yaml` | machine-readable source of truth |\n"
     "| `reports/pipeline-dag.dot` | the step graph (`dot -Tsvg`) |\n\n"
     "**Why files?** So the human can edit the plan itself. The graph reads "
     "`pipeline.yaml` as truth; the notebook is not where authority lives."),
    ("approve_plan", "Step 12 - approve_plan: last gate before anything runs",
     "**What it does.** Points the human at `WORKFLOW.md`, then `approve` or "
     "`rebuild` (edit `state/pipeline.yaml` first).\n\n"
     "**Why it is the important one.** From here on the graph executes shell "
     "commands. Approval is explicit, and the approval is recorded in "
     "`checks[\"plan_test\"]` with the human's verdict verbatim."),
    ("execute", "Step 13 - execute: run one step, or ask first",
     "**What it does.** Unless `autonomous`, asks `run | skip | stop` per "
     "step. A step with no command is a human-verified step and returns rc=0 "
     "with an explicit note. Commands run in the workspace with a 1 h timeout; "
     "only the last 2000 chars of stdout/stderr are kept, as evidence."),
    ("validate", "Step 14 - validate: mechanical, not negotiable",
     "**What it does.** `returncode == 0 and not stopped`, recorded as "
     "`checks[\"validate_<step>\"]` with the result tail as evidence.\n\n"
     "**Rule.** Validation never edits the output and never edits the "
     "reference value. A failing check sends the flow to `correct`; the "
     "reference number stays untouched."),
    ("correct", "Step 15 - correct: the LLM may propose, the harness decides",
     "**What it does.** On failure, the LLM sees the stderr tail plus brain "
     "context and proposes **one corrected shell command**. The new command "
     "goes back through `execute -> validate`; it is never trusted.\n\n"
     "**Anti-loop guard.** If no new command is proposed, retrying the "
     "identical command cannot change the outcome, so `loops` is pushed to "
     "`MAX_LOOPS` and the step escalates to a human instead of spinning."),
    ("advance", "Step 16 - advance / routing: the loop is the graph",
     "**What it does.** Bumps `step` and resets `loops`. The routers are pure "
     "functions of `state`, which is what makes the flow inspectable:\n\n"
     "| router | condition | goes |\n|---|---|---|\n"
     "| `after_validate` | check ok | `advance` |\n"
     "| `after_validate` | failed, loops < MAX_LOOPS | `correct` |\n"
     "| `after_validate` | stopped or loops exhausted | `smoke_test` |\n"
     "| `after_advance` | steps left | `execute` |\n"
     "| `after_advance` | plan done | `smoke_test` |\n\n"
     "`correct -> execute` is the execute-validate-correct cycle; the gate "
     "routers (`after_brain_test`, `after_summary_test`, `after_plan_test`) "
     "all route back to `build_brain` on `rebuild`."),
    ("smoke_test", "Step 17 - smoke_test: a human confirms the whole thing hangs together",
     "**What it does.** One last interrupt: run the small end-to-end smoke "
     "test yourself, then answer `pass` or `fail`. The answer lands in "
     "`checks[\"smoke_test\"]`, and `run_interactive` exits non-zero if any "
     "check failed - so the session is machine-checkable, not vibes."),
]

SECTIONS: list[tuple[str, str]] = [
    ("overview", "What DALI onboarding is, and how to read this notebook"),
    ("state", "The State: the only thing the nodes share"),
    ("checkpoint", "Checkpoints: why the session is resumable"),
    ("interrupts", "interrupt() and Command(resume=...): how a human gate works"),
    ("graph", "Assembling the graph (build_graph)"),
    ("drivers", "The two drivers: run_interactive and run_demo"),
    ("offline-demo", "Run the real flow, offline, right here"),
    ("diagram", "The flow, drawn"),
    ("gates", "All the gates in one table"),
    ("exercises", "Exercises"),
    ("troubleshooting", "Troubleshooting (SWAN and elsewhere)"),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(path: Path) -> dict:
    def _run(*args: str) -> str:
        try:
            return subprocess.run(["git", "-C", str(path.parent), *args],
                                  capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            return ""

    return {"commit": _run("rev-parse", "--short", "HEAD"),
            "branch": _run("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(_run("status", "--porcelain", "--", path.name))}


def _func_source(module_path: Path, name: str) -> Optional[str]:
    source = module_path.read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    return None


def _node_source(module_path: Path, names: list[str]) -> str:
    """Source of the named functions, concatenated, as one python block."""
    chunks = []
    for name in names:
        src = _func_source(module_path, name)
        if src is None:
            chunks.append(f"def {name}(...):\n    ...  # not found in dali_onboard.py")
        else:
            chunks.append(src)
    return "\n\n\n".join(chunks)


def _routing_table(module_path: Path) -> str:
    """Render the conditional edges straight out of build_graph's source."""
    src = _func_source(module_path, "build_graph") or ""
    rows = []
    for line in src.splitlines():
        line = line.strip()
        if line.startswith("g.add_conditional_edges"):
            rows.append(f"`{line}`")
    return "\n".join(rows) or "(no conditional edges found - did build_graph change?)"


def _fallback_plan(module_path: Path) -> str:
    source = module_path.read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_FALLBACK_PLAN":
                    return ast.get_source_segment(source, node) or ""
    return "_FALLBACK_PLAN = []"


def _gate_inventory(module_path: Path) -> list[tuple[str, str, str]]:
    """(node, ask text, options) for every interrupt in the file."""
    src = module_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines()
    out: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(node):
            if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == "interrupt"):
                continue
            ask, options = "", []
            if sub.args and isinstance(sub.args[0], ast.Dict):
                for key, val in zip(sub.args[0].keys, sub.args[0].values):
                    if not isinstance(key, ast.Constant):
                        continue
                    if key.value == "ask":
                        ask = _literal_text(val, lines)
                    elif isinstance(key.value, str) and key.value.endswith("_options"):
                        options = [e.value for e in getattr(val, "elts", [])
                                   if isinstance(e, ast.Constant)]
            out.append((node.name, ask, ", ".join(options) or "-"))
    return out


def _literal_text(node: ast.AST, lines: list[str]) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for val in node.values:
            if isinstance(val, ast.Constant):
                parts.append(str(val.value))
            else:
                parts.append("{...}")
        return "".join(parts).strip()
    if hasattr(node, "lineno"):
        return " ".join(lines[node.lineno - 1:node.end_lineno]).strip()[:160]
    return "?"


def _install_cell() -> str:
    return '''# Run me first.
# - Inside a rag-ai-scientist checkout: nothing to install, the path insert is enough.
# - On SWAN: no general internet, so pip goes through CERN's mirror (URL below).
import os, sys, subprocess
from pathlib import Path

# A checkout next to this notebook (or anywhere in DALI_REPO) needs no install.
for candidate in (os.environ.get("DALI_REPO", ""), str(Path.cwd()),
                  str(Path.cwd().parent), str(Path.cwd().parent / "rag-ai-scientist")):
    if candidate and (Path(candidate) / "rag_ai_scientist" / "dali_onboard.py").exists():
        sys.path.insert(0, str(Path(candidate).resolve()))
        print("using checkout:", Path(candidate).resolve())
        break

def _pkg_version():
    from importlib.metadata import version
    return version("rag-ai-scientist")

try:
    from rag_ai_scientist import dali_onboard as ob
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install",
                    "--index-url", "https://gitlab.cern.ch/api/v4/projects/6480/packages/pypi/simple",
                    "rag-ai-scientist"], check=False)
    from rag_ai_scientist import dali_onboard as ob

print("dali_onboard:", Path(ob.__file__).resolve())
print("python:", sys.version.split()[0], " (need >= 3.10 for langgraph)")

missing = []
for mod, pipname in (("langgraph", "langgraph"), ("langchain_chroma", "langchain-chroma"),
                     ("chromadb", "chromadb"), ("yaml", "PyYAML")):
    try:
        __import__(mod)
    except ImportError:
        missing.append(pipname)
if missing:
    print("MISSING (install them before the flow cells):", ", ".join(missing))
    print("  SWAN: pip install --index-url "
          "https://gitlab.cern.ch/api/v4/projects/6480/packages/pypi/simple "
          + " ".join(missing))
else:
    print("all flow dependencies present")'''


def _state_cell(module_path: Path) -> str:
    source = module_path.read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == "State":
            return ast.get_source_segment(source, node) or ""
    return "class State(TypedDict, total=False): ...  # not found"


def _explore_state_cell() -> str:
    return '''# The state is a plain dict: print what a node changed.
from rag_ai_scientist import dali_onboard as ob

print("State keys:", sorted(ob.State.__annotations__))
print("MAX_LOOPS =", ob.MAX_LOOPS, " (attempts per step before escalating)")
print("embedding tiers:")
for tier, (model, note) in ob.EMBEDDING_MODELS.items():
    print(f"  {tier:<6} {model:<40} {note}")'''


def _checkpoint_cell(module_path: Path) -> str:
    source = module_path.read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == "FileCheckpointSaver":
            return ast.get_source_segment(source, node) or ""
    return "class FileCheckpointSaver(MemorySaver): ...  # not found"


def _interrupt_demo_cell() -> str:
    return '''# A gate in 15 lines: pause, ask, resume. No physics, no I/O.
from typing import TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

class S(TypedDict, total=False):
    answer: str

def ask(state: S) -> dict:
    # everything in this dict is what the driver sees; the return value is
    # whatever the driver resumes with.
    ans = interrupt({"ask": "Approve the plan? [approve|rebuild]",
                     "gate_options": ["approve", "rebuild"]})
    return {"answer": ans}

g = StateGraph(S)
g.add_node("ask", ask)
g.add_edge(START, "ask")
g.add_edge("ask", END)
app = g.compile(checkpointer=MemorySaver())
cfg = {"configurable": {"thread_id": "demo"}}

out = app.invoke({}, cfg)
print("paused with:", out["__interrupt__"][0].value)
out = app.invoke(Command(resume="approve"), cfg)
print("resumed, state now:", {k: v for k, v in out.items() if k != "__interrupt__"})'''


def _build_graph_source(module_path: Path) -> str:
    return _node_source(module_path, ["build_graph"])


def _graph_shape_cell() -> str:
    return '''# Ask the compiled graph what it actually looks like (ground truth, not docs).
from rag_ai_scientist import dali_onboard as ob
from langgraph.checkpoint.memory import MemorySaver

app = ob.build_graph(checkpointer=MemorySaver())
graph = app.get_graph()
print("nodes:")
for node_id in graph.nodes:
    print("  ", node_id)
print("edges:")
for edge in graph.edges:
    cond = "  [conditional]" if getattr(edge, "conditional", False) else ""
    print(f"   {edge.source} -> {edge.target}{cond}")'''


def _drivers_source(module_path: Path) -> str:
    return _node_source(module_path, ["run_interactive"])


def _driver_anatomy_cell() -> str:
    return '''# The whole interactive driver is this loop. Read it once and the CLI is obvious.
from rag_ai_scientist import dali_onboard as ob
from langgraph.types import Command

DRIVER_PSEUDOCODE = """
    checkpointer = ob.FileCheckpointSaver(workspace/.dali/onboard/<thread>.json)
    graph        = ob.build_graph(checkpointer=checkpointer)
    cfg          = {'configurable': {'thread_id': <thread>}}
    out          = graph.invoke({'workspace': str(workspace)}, cfg)
    while '__interrupt__' in out:
        prompt = out['__interrupt__'][0].value        # the gate's payload
        reply  = <read the human's answer for this kind of gate>
        out    = graph.invoke(Command(resume=reply), cfg)
    # then print checks[] and exit non-zero if any check failed
"""
print(DRIVER_PSEUDOCODE)
print("gate payloads the driver knows how to ask about:")
for key in ("fields", "model_options", "agent_options", "brain_options",
            "brain_dir", "summary", "artifacts", "gate_options",
            "step_options", "smoke_options", "fetch_options"):
    print("  ", key)'''


def _offline_demo_cell() -> str:
    return '''# The real nodes, offline: stubbed embeddings and stubbed LLM, real chunking,
# real chroma brain, real plan validation, real artifacts. No keys, no downloads.
from pathlib import Path
from rag_ai_scientist import dali_onboard as ob

work = Path.cwd() / "dali-notebook-work"
work.mkdir(parents=True, exist_ok=True)
state = ob.run_demo(workspace=str(work), verbose=True)

print("\\nChecks:")
for name, chk in state["checks"].items():
    print(f"  [{'PASS' if chk['ok'] else 'FAIL'}] {name}: {chk['evidence'][:110]}")
print("\\nArtifacts:")
for name, path in state.get("artifacts", {}).items():
    print(f"  {name}: {path}")'''


def _read_artifacts_cell() -> str:
    return '''# Read what the flow wrote. This is the human-facing contract of the whole run.
from pathlib import Path

work = Path.cwd() / "dali-notebook-work" / ".dali" / "onboard" / "demo-project"
for rel in ("WORKFLOW.md", "state/pipeline.yaml", "reports/pipeline-dag.dot"):
    path = work / rel
    print("=" * 78)
    print(rel, "->", path if path.exists() else "MISSING")
    print("=" * 78)
    if path.exists():
        text = path.read_text(encoding="utf-8")
        print(text if len(text) < 4000 else text[:4000] + "\\n... (truncated)")'''


def _query_brain_cell() -> str:
    return '''# Query the demo brain the same way the gates do. The demo brain uses the
# hashed demo embeddings, so keep the override set while you query it.
import os
from pathlib import Path
from rag_ai_scientist import dali_onboard as ob

os.environ["DALI_EMBEDDING_CLASS"] = f"{ob.__name__}:_HashedEmbeddings"
work = Path.cwd() / "dali-notebook-work" / ".dali" / "onboard" / "demo-project"
state = {"workspace": str(work), "brain_dir": str(work / ".dali" / "brain"),
         "embedding_model": ob.DEMO_EMBEDDING_NAME}

for question in ("What is the statistical sensitivity?",
                 "What is the 2015 MagUp KKpipi signal yield?"):
    answered, evidence = ob._brain_probe(state, question)
    print(f"\\nQ: {question}   -> answered={answered}")
    print(evidence[:600])'''


def _drive_graph_cell() -> str:
    return '''# Drive the REAL graph (not the scripted demo) with a scripted driver, so you
# can watch every gate fire and answer it programmatically.
from pathlib import Path
from rag_ai_scientist import dali_onboard as ob
from langgraph.types import Command

answers = {
    "fields": {"paper_path": "", "code_path": "", "autonomous": False},
    "model_options": {"model": "small"},
    "agent_options": {"choice": "continue"},
    "brain_options": {"question": "What is the statistical sensitivity?",
                      "verdict": "approve"},
    "gate_options": "approve",
    "step_options": "run",
    "smoke_options": "pass",
    "fetch_options": {"choice": "retry"},
}

work = Path.cwd() / "dali-notebook-work" / "graph-run"
(work / ".dali" / "onboard").mkdir(parents=True, exist_ok=True)
app = ob.build_graph()
cfg = {"configurable": {"thread_id": "notebook"}}
out = app.invoke({"workspace": str(work)}, cfg)

steps = 0
while "__interrupt__" in out and steps < 25:
    prompt = out["__interrupt__"][0].value
    kind = next((k for k in answers if k in prompt), None)
    print(f"\\n[{steps}] gate: {str(prompt.get('ask', ''))[:90]}")
    if kind is None:
        print("    no scripted answer for", sorted(prompt), "-> stopping")
        break
    reply = answers[kind]
    if kind == "fields":
        project = work / ".dali" / "onboard" / "demo-project"
        # reuse the offline demo project as the inputs
        from rag_ai_scientist.dali_onboard import DEMO_PAPER, DEMO_CODE
        (project / "paper").mkdir(parents=True, exist_ok=True)
        (project / "code").mkdir(parents=True, exist_ok=True)
        (project / "paper" / "main.md").write_text(DEMO_PAPER, encoding="utf-8")
        for name, text in DEMO_CODE.items():
            (project / "code" / name).write_text(text, encoding="utf-8")
        reply = {"paper_path": str(project / "paper" / "main.md"),
                 "code_path": str(project / "code"), "autonomous": True}
    print(f"    answer: {str(reply)[:90]}")
    out = app.invoke(Command(resume=reply), cfg)
    steps += 1

print("\\nchecks so far:")
for name, chk in out.get("checks", {}).items():
    print(f"  [{'PASS' if chk['ok'] else 'FAIL'}] {name}: {chk['evidence'][:100]}")'''


def _diagram_cell() -> str:
    return '''# Draw the flow. Needs graphviz; if it is missing the ASCII fallback prints.
from pathlib import Path
from rag_ai_scientist import dali_onboard as ob

out_dir = Path.cwd() / "dali-notebook-work"
out_dir.mkdir(parents=True, exist_ok=True)
app = ob.build_graph()
try:
    svg = app.get_graph().draw_mermaid()
    (out_dir / "dali_flow.mmd").write_text(svg, encoding="utf-8")
    print("mermaid source written to", out_dir / "dali_flow.mmd")
    try:
        from IPython.display import Markdown, display
        display(Markdown("```mermaid\\n" + svg + "\\n```"))
    except Exception:
        print(svg)
except Exception as exc:
    print("mermaid failed:", exc)

print("\\nASCII flow:")
print(r"""
  get_inputs -> check_agent -> fetch_inputs -> choose_embedding_model
      -> embed_and_chunk -> build_brain -> test_brain --rebuild--> build_brain
      -> summarize -> approve_summary --rebuild--> build_brain
      -> plan_dag -> render_artifacts -> approve_plan --rebuild--> build_brain
      -> execute -> validate --fail, loops<MAX--> correct -> execute
                          \-- ok --> advance --steps left--> execute
                          \-- done / stopped / exhausted --> smoke_test -> END
""")'''


def _exercises_cell() -> str:
    return '''# Exercise 1: make a gate reject you.
# Resume the brain gate with verdict="rebuild" and watch after_brain_test route
# back to build_brain. Print the checks you get.
#
# Exercise 2: add a step to the plan.
# Edit state/pipeline.yaml in the demo project (add a step with a benchmark
# whose source path you can point at), then re-render the artifacts with
# ob.render_artifacts(state) and diff WORKFLOW.md.
#
# Exercise 3: make a step fail on purpose.
# Set a step's command to something that exits non-zero, run execute/validate,
# then run correct with no LLM key and read what it writes into checks[].
# Why does it set loops = MAX_LOOPS?
#
# Exercise 4: your own gate.
# Write a node that interrupts with {"ask": ..., "my_options": [...]}, add it
# between render_artifacts and approve_plan, and drive it from a cell.
raise SystemExit("Read the exercises above and delete this line when you start.")'''


def _sync_cell(module_path: Path, meta: dict) -> str:
    data = json.dumps(meta, indent=2)
    return f'''# Is this notebook still describing the code you have open?
# Run `dali-notebook-sync --repo <checkout>` locally to regenerate it.
NOTEBOOK_META = {data}

from pathlib import Path
from rag_ai_scientist import dali_onboard as ob
import hashlib

print("notebook generated from:", NOTEBOOK_META["source_sha256"][:12],
      "commit", NOTEBOOK_META["git"]["commit"], "on", NOTEBOOK_META["git"]["branch"])
print("your dali_onboard.py:", ob.__file__)
if Path(ob.__file__).exists():
    here = hashlib.sha256(Path(ob.__file__).read_bytes()).hexdigest()
    print("same file?" , "YES" if here == NOTEBOOK_META["source_sha256"] else "NO - regenerate the notebook")'''


def _gates_table(module_path: Path) -> str:
    rows = _gate_inventory(module_path)
    lines = ["| node | what it asks | options |", "|---|---|---|"]
    for node, ask, options in rows:
        ask = ask.replace("|", "/").replace("\n", " ")
        lines.append(f"| `{node}` | {ask[:150]} | `{options}` |")
    lines += ["", f"Source of truth: `dali_onboard.py` @ commit "
                  f"`{{{{commit}}}}`. Routers extracted from `build_graph`:", "",
              _routing_table(module_path).replace("|", "/")]
    return "\n".join(lines)


def _overview_section() -> str:
    try:
        from rag_ai_scientist.dali_onboard import MAX_LOOPS
    except Exception:
        MAX_LOOPS = 5
    return f"""# The DALI onboarding flow, step by step

*Generated notebook - do not edit the cells; edit `dali_onboard.py` and
re-run `dali-create-notebook`. See the last cell of this section for the exact
commit this was built from.*

DALI onboarding turns **a paper + a codebase** into a **built, tested, planned
workspace**: a searchable RAG index (the "brain"), a plain-language summary of
the analysis, a DAG of reproduction steps each carrying its golden benchmark,
and an execute -> validate -> correct loop over those steps.

It is implemented as a **LangGraph state machine** in
`rag_ai_scientist/dali_onboard.py`. Three ideas carry the whole design:

1. **Deterministic nodes do the work.** Chunking, embedding, retrieval,
   execution and validation are plain code with plain checks.
2. **The LLM only proposes.** It appears in `summarize`, `plan_dag` and
   `correct`; every proposal is then executed and validated by the harness.
   Nothing the LLM says is trusted.
3. **A human sits on every consequential edge.** Seven `interrupt()` gates
   (inputs, agent, fetch, model, brain, summary, plan, per-step, smoke test),
   and each one records the verdict verbatim in `state["checks"]`.

## How to work through this notebook

Run the cells top to bottom. Each section is: *what the node is for* ->
*the actual source, taken from the file this notebook was generated from* ->
*a cell you can run*. Nothing needs an API key and nothing downloads a model:
the last sections drive the real code path with the embeddings and the chat
model stubbed out.

{_INSTALL_HELP}

## Flow at a glance

```
get_inputs -> check_agent -> fetch_inputs -> choose_embedding_model
  -> embed_and_chunk -> build_brain -> test_brain        [gate: approve|rebuild]
  -> summarize -> approve_summary                        [gate: approve|rebuild]
  -> plan_dag -> render_artifacts -> approve_plan        [gate: approve|rebuild]
  -> execute -> validate -> correct -> execute           [loop, max {MAX_LOOPS} attempts]
                    \\\\-- ok --> advance --more steps--> execute
                    \\\\-- done / stopped / exhausted --> smoke_test -> END
```

Every node writes a verifiable check into `state["checks"][<name>]`; the
session exits non-zero if any check failed."""


def build_notebook(module_path: Path, extra_sections: Optional[dict[str, str]] = None) -> "nbformat.NotebookNode":
    meta = {
        "tool": "dali-create-notebook",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": sys.version.split()[0],
        "source": str(module_path),
        "source_sha256": _sha256(module_path),
        "git": _git(module_path),
    }
    nb = nbformat.v4.new_notebook()
    nb.metadata.update({
        "kernelspec": {"display_name": "Python 3 (py312)", "language": "python",
                       "name": "python3"},
        "language_info": {"name": "python", "version": sys.version.split()[0]},
        "dali": meta,
    })

    cells: list = []
    cells.append(md_cell("overview", _overview_section()))
    cells.append(code_cell("install", _install_cell()))

    cells.append(md_cell("state", (
        "## The State: the only thing the nodes share\n\n"
        "Every node takes this dict and returns a *partial* update. Two fields "
        "use a reducer (`_merge`) so parallel writes to `last_result` and "
        "`checks` merge instead of clobber. Note `total=False`: a node only "
        "sees the keys earlier nodes have written, which is why routing "
        "functions always read with `.get(...)`.\n")))
    cells.append(md_cell("state-source",
                         "```python\n" + _state_cell(module_path) + "\n```"))
    cells.append(code_cell("state-explore", _explore_state_cell()))

    cells.append(md_cell("interrupts", (
        "## `interrupt()` and `Command(resume=...)`: how a human gate works\n\n"
        "A node calls `interrupt(payload)`. LangGraph raises inwards, the "
        "graph pauses, and the driver receives `out[\"__interrupt__\"][0].value` "
        "- the payload. The driver asks the human, then calls "
        "`graph.invoke(Command(resume=answer), cfg)`; the *same* node resumes "
        "and its return value is the answer.\n\n"
        "Two consequences worth internalising:\n\n"
        "- the node's code **before** the interrupt runs again on resume, so "
        "side effects go after the gate or into a separate node;\n"
        "- the pause is a *checkpoint*, not a stack: the process can die and "
        "the session continues from disk.\n\n"
        "Run this 15-line graph before reading any real node:")))
    cells.append(code_cell("interrupt-demo", _interrupt_demo_cell()))

    cells.append(md_cell("checkpoint", (
        "## Checkpoints: why the session is resumable\n\n"
        "`FileCheckpointSaver` subclasses `MemorySaver` and snapshots "
        "`storage` / `writes` / `blobs` to `.dali/onboard/<thread>.json` on "
        "every `put`. That is why `dali-onboard` offers to resume an unfinished "
        "session, and why killing it mid-embedding costs nothing. It is "
        "best-effort by design: any load/save error falls back to pure "
        "in-memory behaviour rather than breaking the run.\n")))
    cells.append(md_cell("checkpoint-source",
                         "```python\n" + _checkpoint_cell(module_path) + "\n```"))

    for node, title, teaching in NODE_SECTIONS:
        names = [node]
        if node == "advance":
            names = ["advance", "after_agent", "after_fetch", "after_brain_test",
                     "after_summary_test", "after_plan_test", "after_validate",
                     "after_advance"]
        if node == "embed_and_chunk":
            names = ["_collect_chunks", "embed_and_chunk"]
        if node == "test_brain":
            names = ["test_brain", "_brain_probe"]
        if node == "choose_embedding_model":
            names = ["detect_hardware", "choose_embedding_model", "_get_embeddings"]
        if node == "correct":
            names = ["correct", "_brain_context"]
        if node == "summarize":
            names = ["_brain_hits", "_material", "summarize"]
        if node == "plan_dag":
            names = ["_normalise_plan", "plan_dag"]
        if node == "render_artifacts":
            names = ["render_workflow_markdown", "render_artifacts"]
        cells.append(md_cell(f"node-{node}", f"## {title}\n\n{teaching}"))
        cells.append(md_cell(f"node-{node}-source",
                             "The live source this section describes:\n\n```python\n"
                             + _node_source(module_path, names) + "\n```"))
        if node == "plan_dag":
            cells.append(md_cell("node-plan_dag-fallback",
                                 "And the plan used when there is no LLM key or nothing "
                                 "retrievable - three honest, human-verified steps, never "
                                 "an invented pipeline:\n\n```python\n"
                                 + _fallback_plan(module_path) + "\n```"))
        if node == "execute":
            cells.append(code_cell("node-execute-probe",
                                   '# execute() with no command: the human-verified path.\n'
                                   'from rag_ai_scientist import dali_onboard as ob\n\n'
                                   'state = {"plan": [{"id": "s", "description": "a human looks",\n'
                                   '             "command": "", "check": "human confirms",\n'
                                   '             "depends_on": [], "benchmarks": []}],\n'
                                   '         "step": 0, "autonomous": True, "workspace": "."}\n'
                                   'print(ob.execute(state)["last_result"])'))

    cells.append(md_cell("graph", (
        "## Assembling the graph\n\n"
        "`build_graph` is the whole flow in one screen: every node, every edge, "
        "every router. Read it top to bottom and you know the system.\n")))
    cells.append(md_cell("graph-source",
                         "```python\n" + _build_graph_source(module_path) + "\n```"))
    cells.append(md_cell("graph-routers",
                         "The conditional edges, extracted from that source:\n\n"
                         + _routing_table(module_path)))
    cells.append(code_cell("graph-shape", _graph_shape_cell()))

    cells.append(md_cell("drivers", (
        "## The two drivers\n\n"
        "The graph knows nothing about terminals. `run_interactive` is the "
        "terminal REPL: it builds the checkpointer, invokes, and answers each "
        "interrupt by looking at which keys the payload carries. `run_demo` is "
        "the offline scripted driver: same nodes, stubbed embeddings and chat "
        "model, so a newcomer can watch the whole loop in seconds without keys.\n")))
    cells.append(md_cell("drivers-source",
                         "```python\n" + _drivers_source(module_path) + "\n```"))
    cells.append(code_cell("drivers-anatomy", _driver_anatomy_cell()))

    cells.append(md_cell("offline-demo", (
        "## Run the real flow, offline, right here\n\n"
        "This is `dali-onboard-demo` in a cell. Only two things are stubbed - "
        "the embedding model (a deterministic hash embedding) and the chat "
        "model (a scripted reply). Chunking, the chroma brain, retrieval, plan "
        "validation and artifact rendering are the production code path.\n\n"
        "The fictional \"Aurora\" project it feeds itself exists only so the "
        "brain has something to retrieve; its numbers are demo numbers.")))
    cells.append(code_cell("offline-demo-run", _offline_demo_cell()))
    cells.append(code_cell("offline-demo-artifacts", _read_artifacts_cell()))
    cells.append(code_cell("offline-demo-brain", _query_brain_cell()))
    cells.append(md_cell("offline-demo-graph-note", (
        "### The same thing through the real graph object\n\n"
        "The scripted demo calls nodes in order. This cell instead compiles the "
        "graph and answers each gate from a dict, so you can see the pauses and "
        "resumes themselves. It needs `langgraph` installed.")))
    cells.append(code_cell("offline-demo-drive", _drive_graph_cell()))

    cells.append(md_cell("diagram", (
        "## The flow, drawn\n\n"
        "`build_graph().get_graph()` can emit the diagram itself - the same "
        "object the CLI and the notebook share, so the picture cannot drift "
        "from the code.")))
    cells.append(code_cell("diagram-run", _diagram_cell()))

    cells.append(md_cell("gates", _gates_table(module_path).replace("{{commit}}",
                                                                    meta["git"]["commit"] or "unknown")))
    cells.append(md_cell("exercises", (
        "## Exercises\n\n"
        "Each one is a change you can actually make, with a check that tells you "
        "it worked.")))
    cells.append(code_cell("exercises-run", _exercises_cell()))

    cells.append(md_cell("troubleshooting", """## Troubleshooting

| symptom | cause / fix |
|---|---|
| `ModuleNotFoundError: langgraph` | old `rag-ai-scientist`; `pip install -U rag-ai-scientist` and confirm >= 0.1.10 (earlier 0.1.x has no `dali-onboard`) |
| `No module named 'langgraph'` on SWAN | SWAN kernel is Python < 3.10; pick `py312` |
| pip install fails on SWAN | SWAN has no general internet; use the CERN PyPI mirror URL in the install cell |
| `sqlite3` version errors when building the brain | the code already swaps in `pysqlite3` on lxplus-like hosts; if it still fails, `pip install pysqlite3-binary` |
| summary/plan cells say "no LLM key" | `GROQ_API_KEY` / `OPENAI_API_KEY` not exported in the SWAN session; the flow still runs, with human-verified steps |
| brain hits look off-topic | rebuild with the `base` or `large` tier; `small` is a baseline, not the recommended quality |
| notebook says "NO - regenerate the notebook" | `dali_onboard.py` changed since generation; run `dali-notebook-sync --repo <checkout>` |

**Where things live** (default workspace): `.dali/brain/` (the vector store),
`.dali/onboard/<thread>.json` (checkpoints), `.dali/onboard/inbox/` (fetched
inputs), `WORKFLOW.md`, `state/pipeline.yaml`, `reports/pipeline-dag.dot`.

**The rules the flow will not let you break**: a failed check is fixed in the
code or the config - never in an output, never in a reference value; a number
with no traceable source is left to a human; max `MAX_LOOPS` attempts per step,
then escalate."""))
    cells.append(code_cell("sync", _sync_cell(module_path, meta)))

    if extra_sections:
        for name, source in extra_sections.items():
            cells.append(md_cell(name, source))

    nb.cells = cells
    return nb


def find_source(root: Path) -> Path:
    for candidate in (root / "rag_ai_scientist" / "dali_onboard.py",):
        if candidate.exists():
            return candidate
    try:
        from rag_ai_scientist import dali_onboard as ob

        return Path(ob.__file__)
    except Exception:
        pass
    raise SystemExit(f"dali_onboard.py not found under {root}; run from a "
                     "rag-ai-scientist checkout or pass --source")


def manifest_path(out_dir: Path) -> Path:
    return out_dir / MANIFEST_NAME


def write_notebook(nb: "nbformat.NotebookNode", out_dir: Path, source: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / NOTEBOOK_NAME
    nbformat.write(nb, path)
    meta = nb.metadata["dali"]
    manifest_path(out_dir).write_text(
        json.dumps({**meta, "notebook": path.name,
                    "notebook_sha256": _sha256(path)}, indent=2) + "\n",
        encoding="utf-8")
    return path


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dali-create-notebook",
        description="Generate the SWAN-openable notebook that teaches the DALI "
                    "onboarding flow from the current dali_onboard.py.")
    parser.add_argument("--repo", default=".", help="rag-ai-scientist checkout.")
    parser.add_argument("--source", default="", help="Explicit dali_onboard.py.")
    parser.add_argument("--out", default="", help="Output dir (default: <repo>/docs/notebook).")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite even if the notebook was hand-edited.")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    source = Path(args.source).resolve() if args.source else find_source(repo)
    out_dir = Path(args.out).resolve() if args.out else repo / "docs" / "notebook"

    existing = out_dir / NOTEBOOK_NAME
    if existing.exists() and not args.force:
        stamp = manifest_path(out_dir)
        if stamp.exists():
            stored = json.loads(stamp.read_text(encoding="utf-8")).get("notebook_sha256")
            if stored and stored != _sha256(existing):
                raise SystemExit(
                    f"{existing} differs from the last generated copy "
                    "(hand-edited?). Re-run with --force to overwrite.")

    nb = build_notebook(source)
    path = write_notebook(nb, out_dir, source)
    print(f"wrote {path}")
    print(f"  from {source} (sha256 {nb.metadata['dali']['source_sha256'][:12]}, "
          f"commit {nb.metadata['dali']['git']['commit'] or 'unknown'})")
    print(f"  {len(nb.cells)} cells ({sum(1 for c in nb.cells if c.cell_type == 'code')} "
          "runnable)")
    print(f"  manifest: {manifest_path(out_dir)}")
    print("Open it in SWAN: https://swan.cern.ch -> your project -> upload this .ipynb")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
