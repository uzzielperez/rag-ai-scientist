"""DALI onboarding as a LangGraph state machine.

Flow: inputs -> embed+chunk -> build RAG brain -> test brain (human gate)
      -> plan -> [execute -> validate -> correct]* -> smoke test (human gate) -> done

Deterministic nodes do the work (they reuse the rag-ai-scientist indexing and
harness machinery); the LLM is only used in plan() and correct(). Every node
writes a verifiable check into state["checks"].

Requires langgraph (Python >= 3.10).
"""
from __future__ import annotations

import json
import operator
import os
import pickle
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class FileCheckpointSaver(MemorySaver):
    """MemorySaver that snapshots to (and restores from) a pickle file.

    Keeps the onboarding session resumable across CLI invocations without
    pulling in langgraph-checkpoint-sqlite. Best-effort: on any load/save
    error it silently falls back to pure in-memory behaviour.
    """

    def __init__(self, path: Path | str) -> None:
        super().__init__()
        self._path = Path(path)
        self._restore()

    def _restore(self) -> None:
        try:
            if not self._path.exists():
                return
            with self._path.open("rb") as fh:
                data = pickle.load(fh)
            self.storage.update(data["storage"])
            self.writes.update(data["writes"])
            self.blobs.update(data["blobs"])
        except Exception:
            pass

    def _snapshot(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"storage": dict(self.storage),
                       "writes": dict(self.writes),
                       "blobs": dict(self.blobs)}
            tmp = self._path.with_suffix(".tmp")
            with tmp.open("wb") as fh:
                pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
            tmp.replace(self._path)
        except Exception:
            pass

    def put(self, config, checkpoint, metadata, new_versions):
        result = super().put(config, checkpoint, metadata, new_versions)
        self._snapshot()
        return result

    def put_writes(self, config, writes, task_id, task_path=""):
        result = super().put_writes(config, writes, task_id, task_path)
        self._snapshot()
        return result

    def delete_thread(self, thread_id):
        result = super().delete_thread(thread_id)
        self._snapshot()
        return result

MAX_LOOPS = 5

_CODE_SUFFIXES = {".py", ".cxx", ".cpp", ".cc", ".C", ".h", ".hpp", ".yaml", ".yml", ".toml", ".sh", ".cmake", ".txt", ".md"}
_DOC_SUFFIXES = {".pdf", ".md", ".txt", ".tex", ".rst"}


def _merge(base: dict, new: dict) -> dict:
    return {**(base or {}), **(new or {})}


class State(TypedDict, total=False):
    paper_path: str
    code_path: str
    autonomous: bool          # False = human approves each loop iteration
    workspace: str
    brain_dir: str
    n_chunks: int
    plan: list[dict]
    step: int
    loops: int
    embedding_model: str        # chosen at the choose_embedding_model gate
    torch_device: str           # cpu | mps | cuda
    agent_found: str            # where check_agent located dali.md
    last_result: Annotated[dict, _merge]
    checks: Annotated[dict, _merge]   # node name -> {"ok": bool, "evidence": str}


EMBEDDING_MODELS = {
    "small": ("sentence-transformers/all-MiniLM-L6-v2",
              "22M params, ~0.5 GB RAM, fastest; good baseline for code+docs"),
    "base": ("BAAI/bge-base-en-v1.5",
             "109M params, ~1.5 GB RAM; noticeably better retrieval, still fine on modern CPUs"),
    "large": ("BAAI/bge-large-en-v1.5",
              "335M params, ~3 GB RAM; best quality, slow on CPU, worth it on many cores or GPU"),
}


def detect_hardware() -> dict:
    """CPU cores, RAM GB, torch device -> recommended embedding tier."""
    import platform
    try:
        cores = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") \
            else (os.cpu_count() or 2)
    except Exception:
        cores = os.cpu_count() or 2
    ram_gb = 0.0
    try:
        if sys.platform == "darwin":
            import subprocess as sp
            ram_gb = int(sp.check_output(["sysctl", "-n", "hw.memsize"]).split()[0]) / 2**30
        else:
            with open("/proc/meminfo") as fh:
                for line in fh:
                    if line.startswith("MemTotal"):
                        ram_gb = int(line.split()[1]) / 2**20
                        break
    except Exception:
        pass
    device, accel = "cpu", ""
    try:
        import torch
        if torch.backends.mps.is_available():
            device, accel = "mps", " (Apple GPU)"
        elif torch.cuda.is_available():
            device, accel = "cuda", " (NVIDIA GPU)"
    except Exception:
        pass
    if device != "cpu":
        rec = "large"
    elif cores >= 8 and ram_gb >= 16:
        rec = "base"
    else:
        rec = "small"
    if rec == "large" and 0 < ram_gb < 16:
        rec = "base"
    if rec == "base" and 0 < ram_gb < 8:
        rec = "small"
    return {"cores": cores, "ram_gb": round(ram_gb, 1), "device": device,
            "accel": accel, "recommended": rec}


def choose_embedding_model(state: State) -> dict:
    """Human gate: offer embedding models sized for this machine; user picks."""
    hw = detect_hardware()
    menu = "\n".join(f"  [{tier}] {EMBEDDING_MODELS[tier][0]}  - {EMBEDDING_MODELS[tier][1]}"
                     for tier in EMBEDDING_MODELS)
    ans = interrupt({
        "ask": (f"Your machine: {hw['cores']} cores, {hw['ram_gb']} GB RAM, "
                f"torch device '{hw['device']}'{hw['accel']}.\n"
                f"Which embedding model for the brain? (recommended: {hw['recommended']})\n"
                f"{menu}"),
        "model_options": list(EMBEDDING_MODELS),
    })
    choice = ans.get("model", str(ans)) if isinstance(ans, dict) else str(ans)
    choice = choice.strip().lower()
    if choice not in EMBEDDING_MODELS:
        choice = hw["recommended"]
    model = EMBEDDING_MODELS[choice][0]
    return {"embedding_model": model, "torch_device": hw["device"],
            "checks": _check(state, "embedding_model", True,
                             f"{model} on {hw['device']} ({hw['cores']} cores, "
                             f"{hw['ram_gb']} GB)")}


def _get_embeddings(state: State):
    """One factory so brain build, probe, and query always agree on the model."""
    from langchain_huggingface import HuggingFaceEmbeddings
    model = state.get("embedding_model") or EMBEDDING_MODELS["small"][0]
    device = state.get("torch_device", "cpu")
    return HuggingFaceEmbeddings(
        model_name=model,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
        show_progress=False,
    )


def _check(state: State, name: str, ok: bool, evidence: str) -> dict:
    checks = dict(state.get("checks", {}))
    checks[name] = {"ok": ok, "evidence": evidence}
    return checks


def _get_llm():
    """LLM factory: Groq if GROQ_API_KEY is set, else OpenAI-compatible endpoint."""
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key and groq_key != "gsk_your-key-here":
        from langchain_groq import ChatGroq

        return ChatGroq(api_key=groq_key, temperature=0, model="llama-3.3-70b-versatile")
    if os.environ.get("OPENAI_API_KEY", "").strip():
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(temperature=0)
    return None


def _brain_context(state: State, query: str, k: int = 4) -> str:
    try:
        try:  # sqlite workaround for lxplus-like environments
            __import__("pysqlite3")
            sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
        except Exception:
            pass
        try:
            from langchain_chroma import Chroma
        except ImportError:
            from langchain_community.vectorstores import Chroma

        embeddings = _get_embeddings(state)
        store = Chroma(
            persist_directory=state["brain_dir"],
            collection_name="dali-brain",
            embedding_function=embeddings,
        )
        docs = store.similarity_search(query, k=k)
        return "\n\n---\n".join(
            f"[{d.metadata.get('doc_path', '?')}]\n{d.page_content[:800]}" for d in docs
        )
    except Exception as exc:  # brain unavailable -> LLM plans from goals alone
        return f"(brain unavailable: {exc})"


def _brain_probe(state: State, query: str) -> tuple[bool, str]:
    """Answer a question from the brain; returns (answered, evidence)."""
    try:
        try:
            __import__("pysqlite3")
            sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
        except Exception:
            pass
        try:
            from langchain_chroma import Chroma
        except ImportError:
            from langchain_community.vectorstores import Chroma

        embeddings = _get_embeddings(state)
        store = Chroma(
            persist_directory=state["brain_dir"],
            collection_name="dali-brain",
            embedding_function=embeddings,
        )
        hits = store.similarity_search_with_score(query, k=3)
    except Exception as exc:
        return False, f"query failed: {exc}"
    if not hits:
        return False, "no hits"
    lines = []
    for doc, score in hits:
        src = doc.metadata.get("doc_path", doc.metadata.get("file", "?"))
        lines.append(f"score={score:.3f} {src}: {doc.page_content[:200]}")
    return True, "\n".join(lines)


# ---- nodes -----------------------------------------------------------------
def get_inputs(state: State) -> dict:
    ans = interrupt({
        "ask": "What are we working on? Point me at the paper and the code.",
        "fields": ["paper_path", "code_path", "autonomous"],
    })
    if isinstance(ans, str):
        raise ValueError(
            "The inputs interrupt needs a dict with keys paper_path, code_path, autonomous."
        )
    ok = bool(ans.get("paper_path") and ans.get("code_path"))
    return {**ans, "checks": _check(state, "inputs", ok, str(ans))}


AGENT_LOCATIONS = [
    ("opencode (project)", ".opencode/agent/dali.md"),
    ("opencode (user)", "~/.config/opencode/agent/dali.md"),
    ("claude-code (project)", ".claude/agents/dali.md"),
    ("claude-code (user)", "~/.claude/agents/dali.md"),
    ("cursor", ".cursor/agents/dali.md"),
    ("codex", ".codex/agents/dali.md"),
    ("copilot/vscode", ".github/agents/dali.md"),
]


def _find_agent(workspace: Path) -> list[str]:
    found = []
    for label, rel in AGENT_LOCATIONS:
        p = Path(os.path.expanduser(rel))
        if not p.is_absolute():
            p = workspace / p
        if p.exists():
            found.append(label)
    return found


def _find_install_script(state: State) -> Optional[Path]:
    env = os.environ.get("DALI_HARNESS")
    candidates = [Path(env) / "install/install.sh"] if env else []
    try:
        import rag_ai_scientist
        pkg = Path(rag_ai_scientist.__file__).parent
        candidates += [pkg / "install/install.sh", pkg / "harness/install/install.sh"]
    except Exception:
        pass
    candidates.append(Path.home() / "Desktop/DALI-basic-harness/install/install.sh")
    for c in candidates:
        if c.exists():
            return c
    return None


def check_agent(state: State) -> dict:
    """Gate: is the DALI agent callable in this workspace/IDE? The onboarding
    output is meant to be handed to `/agent dali`, so verify it exists before
    the expensive embedding work; offer to install the harness if missing."""
    workspace = Path(state.get("workspace") or os.getcwd())
    found = _find_agent(workspace)
    if found:
        return {"agent_found": ", ".join(found),
                "checks": _check(state, "agent", True, f"dali agent found: {found}")}
    installer = _find_install_script(state)
    help_text = (
        "The DALI agent (/agent dali) is not installed in this workspace or in "
        "any known IDE location.\n"
        + (f"Installer available: {installer}\n" if installer else
           "No local installer found: get the harness first "
           "(pip install rag-ai-scientist, or clone DALI-nucleus).\n")
        + "  [install] run the installer for your IDE now\n"
        "  [continue] onboard anyway (brain only; you install the agent later)\n"
        "  [abort] stop here"
    )
    while True:
        ans = interrupt({"ask": help_text,
                         "agent_options": ["install", "continue", "abort"]})
        choice = ans.get("choice", str(ans)) if isinstance(ans, dict) else str(ans)
        choice = choice.strip().lower()
        if choice.startswith("abort"):
            return {"checks": _check(state, "agent", False, "user aborted: no dali agent"),
                    "last_result": {"stopped": True}}
        if choice.startswith("install") and installer:
            ide = ans.get("ide", "opencode") if isinstance(ans, dict) else "opencode"
            r = subprocess.run(
                ["bash", str(installer), "--ide", ide, "--workspace", str(workspace)],
                capture_output=True, text=True)
            found = _find_agent(workspace)
            ok = bool(found)
            evidence = (f"installer rc={r.returncode}; agent now: {found or 'still missing'}; "
                        f"tail: {(r.stdout + r.stderr).strip()[-200:]}")
            if ok:
                return {"agent_found": ", ".join(found),
                        "checks": _check(state, "agent", True, evidence)}
            help_text = f"Install did not produce a dali agent.\n{evidence}\nRetry, continue anyway, or abort?"
        elif choice.startswith("install"):
            help_text = ("No installer found locally. Run `pip install "
                         "rag-ai-scientist` or clone the harness, set "
                         "DALI_HARNESS=/path/to/harness, then retry.")
        else:
            return {"checks": _check(state, "agent", True,
                                     "no dali agent found; user chose to continue")}


_CERN_GITLAB_HOSTS = ("gitlab.cern.ch", "gitlab-build.cern.ch")


def _open_url(src: str):
    """urlopen with a browser-like UA; on CERN GitLab, try ~/.netrc credentials."""
    req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0 (dali-onboard)"})
    host = urllib.parse.urlparse(src).netloc.split("@")[-1]
    if any(h in host for h in _CERN_GITLAB_HOSTS):
        try:
            import netrc
            login, _, password = (netrc.netrc().authenticators(host.split(":")[0])
                                  or (None, None, None))
            if login and password:
                import base64
                token = base64.b64encode(f"{login}:{password}".encode()).decode()
                req.add_header("Authorization", f"Basic {token}")
        except Exception:
            pass
    return urllib.request.urlopen(req, timeout=120)


def _fetch_if_url(src: str, dest_dir: Path) -> Path:
    parsed = urllib.parse.urlparse(src)
    if parsed.scheme not in ("http", "https"):
        path = Path(src).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"input path does not exist: {path}")
        if path.is_file():
            return path
        return path
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = Path(parsed.path).name or "download"
    target = dest_dir / name
    if not target.exists():
        with _open_url(src) as resp, target.open("wb") as fh:
            shutil.copyfileobj(resp, fh)
    return target


def _fetch_error_help(src: str, exc: Exception) -> str:
    host = urllib.parse.urlparse(src).netloc.split("@")[-1]
    status = getattr(exc, "code", None)
    if status in (401, 403) and any(h in host for h in _CERN_GITLAB_HOSTS):
        return (
            f"{exc} — {host} needs CERN Single Sign-On, which plain fetches "
            "cannot complete.\n"
            "  Option A (recommended): clone the repo on a machine that can "
            "auth (lxplus, or here after a one-time SSO login + PAT in "
            "~/.netrc), then give me the LOCAL path.\n"
            "  Option B: open https://gitlab.cern.ch/users/sign_in in your "
            "browser, create a read_repository PAT, and store it:\n"
            "      echo 'machine gitlab.cern.ch login <cern-username> "
            "password <PAT>' >> ~/.netrc\n"
            "  then choose retry.\n"
            "  Option C: if the repo is mirrored publicly (e.g. a tarball "
            "URL), give me that URL instead."
        )
    return f"{type(exc).__name__}: {exc}"


def fetch_inputs(state: State) -> dict:
    """Human gate: fetch paper + code; on failure explain how to fix access
    (CERN GitLab needs SSO/PAT) and let the user correct the paths or abort."""
    workspace = Path(state.get("workspace") or os.getcwd())
    inbox = workspace / ".dali" / "onboard" / "inbox"
    while True:
        try:
            paper = _fetch_if_url(state["paper_path"], inbox)
            code = _fetch_if_url(state["code_path"], inbox)
            return {"checks": _check(state, "fetch", True,
                                     f"paper={paper.name} code={code.name}")}
        except Exception as exc:
            failed_src = state["paper_path"] if not _already_fetched(
                state.get("paper_path", ""), inbox) else state["code_path"]
            help_text = _fetch_error_help(failed_src, exc)
            ans = interrupt({
                "ask": f"I could not fetch an input.\n{help_text}\n"
                       "Fix it and retry, or give corrected paths.",
                "fetch_options": ["retry", "new paths", "abort"],
            })
            reply = ans.get("choice", str(ans)) if isinstance(ans, dict) else str(ans)
            if reply.startswith("abort"):
                return {"checks": _check(state, "fetch", False, str(exc)),
                        "last_result": {"stopped": True}}
            if reply.startswith("new") and isinstance(ans, dict):
                for key in ("paper_path", "code_path"):
                    if ans.get(key):
                        state[key] = ans[key]
            continue


def _looks_like_url(s: str) -> bool:
    return urllib.parse.urlparse(s).scheme in ("http", "https")


def _already_fetched(src: str, inbox: Path) -> bool:
    if not _looks_like_url(src):
        return True
    name = Path(urllib.parse.urlparse(src).path).name or "download"
    return (inbox / name).exists()


def _collect_chunks(state: State) -> tuple[list, list[Path]]:
    """Extract + chunk paper and code (already fetched) into Documents."""
    from rag.index_documents import _classify_document, _create_chunks, _extract_text

    workspace = Path(state.get("workspace") or os.getcwd())
    inbox = workspace / ".dali" / "onboard" / "inbox"

    paper = _fetch_if_url(state["paper_path"], inbox)
    code = _fetch_if_url(state["code_path"], inbox)

    paths: list[Path] = []
    for root, suffixes in ((paper, _DOC_SUFFIXES), (code, _CODE_SUFFIXES)):
        if root.is_file():
            paths.append(root)
        else:
            wanted = {s.lower() for s in suffixes}
            paths.extend(sorted(p for p in root.rglob("*") if p.suffix.lower() in wanted))

    documents = []
    for path in paths:
        text = _extract_text(path)
        if not text.strip():
            continue
        source_type, doc_category = _classify_document(path, {})
        metadata = {
            "file": path.name,
            "doc_path": str(path),
            "source_type": source_type,
            "doc_category": doc_category,
        }
        documents.extend(
            _create_chunks(
                text=text,
                metadata=metadata,
                chunk_size=1500,
                chunk_overlap=200,
                scientific_chunk_size=2000,
                scientific_chunk_overlap=300,
            )
        )
    return documents, paths


def embed_and_chunk(state: State) -> dict:
    documents, paths = _collect_chunks(state)
    n_chunks = len(documents)
    return {
        "n_chunks": n_chunks,
        "checks": _check(state, "chunks", n_chunks > 0, f"{n_chunks} chunks from {len(paths)} files"),
    }


def build_brain(state: State) -> dict:
    """Embed the chunks into a persistent chroma DB (the 'brain')."""
    try:
        from langchain_chroma import Chroma
    except ImportError:
        from langchain_community.vectorstores import Chroma

    workspace = Path(state.get("workspace") or os.getcwd())
    brain_dir = str(workspace / ".dali" / "brain")
    documents, _ = _collect_chunks(state)

    embeddings = _get_embeddings(state)
    Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=brain_dir,
        collection_name="dali-brain",
    )
    return {
        "brain_dir": brain_dir,
        "checks": _check(state, "brain", len(documents) > 0,
                         f"{len(documents)} chunks indexed at {brain_dir}"),
    }


def test_brain(state: State) -> dict:
    """Human gate: ask the brain a question, show real hits, ask for approval."""
    q = interrupt({
        "ask": "Ask the brain a test question. Does the answer look right?",
        "brain_options": ["approve", "rebuild"],
        "brain_dir": state.get("brain_dir", ""),
    })
    if isinstance(q, dict):
        question = str(q.get("question", "")).strip()
        verdict = str(q.get("verdict", "approve"))
    else:
        question, verdict = "", str(q)
    answered, evidence = (False, "no question asked")
    if question and state.get("brain_dir"):
        answered, evidence = _brain_probe(state, question)
        print(f"[brain] {evidence}")
    ok = verdict == "approve"
    return {"checks": _check(state, "brain_test", ok, f"user: {verdict}; probe: {evidence[:500]}")}


def _parse_json_array(text: str) -> Optional[list]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("["):]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def make_plan(state: State) -> dict:
    """LLM turns project goals into a linear list of verifiable steps."""
    goals = state.get("goals", "")
    context = _brain_context(state, goals or "What does this project do and how is it run?")
    llm = _get_llm()
    plan: list[dict] = []
    if llm is not None:
        from langchain_core.messages import HumanMessage, SystemMessage

        prompt = (
            "You are the DALI onboarding planner. From the project material below, produce a "
            "linear plan of 3-7 verifiable steps to reproduce the project's nominal result. "
            'Reply ONLY with a JSON array of objects: '
            '[{"description": str, "command": str, "check": str}] where command is a shell '
            "command runnable from the workspace root and check states how success is verified."
            f"\n\nProject goals: {goals or '(ask the brain)'}\n\nMaterial:\n{context}"
        )
        try:
            reply = llm.invoke([
                SystemMessage(content="Reply with valid JSON only."),
                HumanMessage(content=prompt),
            ])
            parsed = _parse_json_array(reply.content)
            if parsed:
                plan = [
                    {"description": str(s.get("description", f"step {i+1}")),
                     "command": str(s.get("command", "")),
                     "check": str(s.get("check", "exit code 0"))}
                    for i, s in enumerate(parsed) if isinstance(s, dict)
                ]
        except Exception as exc:
            print(f"[plan] LLM planning failed ({exc}); using fallback plan.")
    if not plan:
        plan = [
            {"description": "reproduce nominal result", "command": "", "check": "human confirms output matches reference"},
            {"description": "run preselection", "command": "", "check": "exit code 0 and non-empty output"},
            {"description": "run fit", "command": "", "check": "exit code 0 and converged"},
        ]
    return {"plan": plan, "step": 0, "loops": 0,
            "checks": _check(state, "plan", len(plan) > 0, f"{len(plan)} steps")}


def execute(state: State) -> dict:
    step = state["plan"][state["step"]]
    if not state.get("autonomous"):
        go = interrupt({"ask": f"Run step {state['step']+1}/{len(state['plan'])}: {step['description']}?",
                        "step_options": ["run", "skip", "stop"]})
        if go == "stop":
            return {"last_result": {"stopped": True, "description": step["description"]}}
        if go == "skip":
            return {"last_result": {"skipped": True, "returncode": 0,
                                    "description": step["description"], "stdout_tail": "", "stderr_tail": ""}}
    if not step.get("command"):
        return {"last_result": {"returncode": 0, "description": step["description"],
                                "stdout_tail": "(no command: human-verified step)", "stderr_tail": ""}}
    workspace = state.get("workspace") or os.getcwd()
    proc = subprocess.run(
        step["command"], shell=True, cwd=workspace,
        capture_output=True, text=True, timeout=3600,
    )
    return {"last_result": {
        "returncode": proc.returncode,
        "description": step["description"],
        "command": step["command"],
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }}


def validate(state: State) -> dict:
    r = state["last_result"]
    ok = r.get("returncode") == 0 and not r.get("stopped")
    return {"checks": _check(state, f"validate_{state['step']}", ok, str(r)[:500])}


def correct(state: State) -> dict:
    """LLM proposes a fix from the failure evidence; the new command is still
    executed and validated by the harness, so the fix is checked, not trusted."""
    r = state["last_result"]
    step = state["plan"][state["step"]]
    loops = state.get("loops", 0)
    llm = _get_llm()
    fix = ""
    if llm is not None:
        from langchain_core.messages import HumanMessage, SystemMessage

        context = _brain_context(state, f"How do I fix this failure: {r.get('stderr_tail', '')[-500:]}")
        try:
            reply = llm.invoke([
                SystemMessage(content="Reply with valid JSON only."),
                HumanMessage(content=(
                    "A workflow step failed. Propose one corrected shell command.\n"
                    f"Step: {step['description']}\nCommand: {step.get('command','')}\n"
                    f"rc={r.get('returncode')}\nstderr tail:\n{r.get('stderr_tail','')[-1500:]}\n"
                    f"Brain context:\n{context}\n"
                    'Reply ONLY {"command": "..."}'
                )),
            ])
            text = reply.content
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1:
                fix = str(json.loads(text[start : end + 1]).get("command", "")).strip()
        except Exception as exc:
            print(f"[correct] LLM fix failed ({exc}); retrying unchanged step.")
    if not fix or fix == step.get("command"):
        # No usable new proposal: retrying the identical command cannot change
        # the outcome, so burn the remaining attempts and escalate.
        loops = MAX_LOOPS
    plan = list(state["plan"])
    if fix and fix != step.get("command"):
        plan[state["step"]] = {**step, "command": fix,
                               "fixes": step.get("fixes", []) + [fix]}
    return {"plan": plan, "loops": loops,
            "checks": _check(state, f"correct_{state['step']}_loop{loops}",
                             bool(fix), fix or "no fix proposed; escalating to human")}


def advance(state: State) -> dict:
    return {"step": state["step"] + 1, "loops": 0}


def smoke_test(state: State) -> dict:
    r = interrupt({"ask": "Run the small smoke test yourself. Did it pass?",
                   "smoke_options": ["pass", "fail"]})
    return {"checks": _check(state, "smoke_test", r == "pass", f"user: {r}")}


# ---- routing ---------------------------------------------------------------
def after_agent(state) -> Literal["fetch_inputs", "abort"]:
    return "abort" if state.get("checks", {}).get("agent", {}).get("ok") is False \
        else "fetch_inputs"


def after_fetch(state) -> Literal["embed_and_chunk", "abort"]:
    return "abort" if state.get("checks", {}).get("fetch", {}).get("ok") is False \
        else "embed_and_chunk"


def after_brain_test(state) -> Literal["make_plan", "build_brain"]:
    return "make_plan" if state["checks"]["brain_test"]["ok"] else "build_brain"


def after_validate(state) -> Literal["advance", "correct", "smoke_test"]:
    if state["last_result"].get("stopped") or state["loops"] >= MAX_LOOPS:
        return "smoke_test"
    return "advance" if state["checks"][f"validate_{state['step']}"]["ok"] else "correct"


def after_advance(state) -> Literal["execute", "smoke_test"]:
    return "execute" if state["step"] < len(state["plan"]) else "smoke_test"


# ---- graph -----------------------------------------------------------------
def build_graph(checkpointer=None):
    g = StateGraph(State)
    for fn in (get_inputs, check_agent, fetch_inputs, choose_embedding_model,
               embed_and_chunk, build_brain, test_brain, make_plan, execute,
               validate, correct, advance, smoke_test):
        g.add_node(fn.__name__, fn)

    g.add_edge(START, "get_inputs")
    g.add_edge("get_inputs", "check_agent")
    g.add_conditional_edges("check_agent", after_agent,
                            {"fetch_inputs": "fetch_inputs", "abort": END})
    g.add_edge("fetch_inputs", "choose_embedding_model")
    g.add_conditional_edges("fetch_inputs", after_fetch,
                            {"embed_and_chunk": "choose_embedding_model", "abort": END})
    g.add_edge("choose_embedding_model", "embed_and_chunk")
    g.add_edge("embed_and_chunk", "build_brain")
    g.add_edge("build_brain", "test_brain")
    g.add_conditional_edges("test_brain", after_brain_test)
    g.add_edge("make_plan", "execute")
    g.add_edge("execute", "validate")
    g.add_conditional_edges("validate", after_validate)
    g.add_edge("correct", "execute")
    g.add_conditional_edges("advance", after_advance)
    g.add_edge("smoke_test", END)

    return g.compile(checkpointer=checkpointer or MemorySaver())


def _human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0 or unit == "TB":
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


def _print_intro(workspace_dir: Path, checkpoint_exists: bool) -> None:
    usage = shutil.disk_usage(workspace_dir)
    free = _human_size(usage.free)
    print(
        "\n"
        "  ================================================\n"
        "    Hi, I'm DALI.\n"
        "  ================================================\n"
        "  I'm here to scaffold your physics analyses - the boilerplate,\n"
        "  the plumbing, the bookkeeping - so you can spend more time on\n"
        "  the physics itself.\n"
        "\n"
        "  Nothing here is a black box: the code I generate and the\n"
        "  pipeline (the \"pipes\") it runs are yours to customise and\n"
        "  inspect at every step - open any file, tweak any config.\n"
        "\n"
        "  Give me a project (a paper + a codebase) and I'll set it up\n"
        "  step by step, checking my work at every stage:\n"
        "\n"
        "    1. Read your paper and codebase, chunk them into memory.\n"
        "    2. Build a searchable RAG index (the \"brain\") in this workspace.\n"
        "    3. Let you test the brain, then approve or rebuild it.\n"
        "    4. Plan how to reproduce the project's nominal result.\n"
        "    5. Run each step, validate it, and correct failures (up to\n"
        f"       {MAX_LOOPS} attempts each) before a final smoke test.\n"
        "\n"
        "  Where things live:\n"
        f"    Workspace : {workspace_dir}\n"
        f"    Brain     : {workspace_dir / '.dali' / 'brain'}\n"
        f"    Checkpoint: {workspace_dir / '.dali' / 'onboard'}\n"
        "\n"
        f"  Disk: {free} free here. The index is usually a few hundred MB\n"
        "  (embedding model + vector store); your own inputs are counted\n"
        "  once you give me their paths.\n"
        + (
            "\n  I found an unfinished session here - I'll resume it unless\n"
            "  you start a fresh one.\n"
            if checkpoint_exists
            else ""
        )
        + "  ================================================\n"
    )


_LEARN_TOPICS: dict[str, tuple[str, str]] = {
    "1": (
        "Examples & tutorials",
        "  Ready-made walkthroughs so you can see a full run before your own:\n"
        "    - docs/GETTING_STARTED.md   : first-time setup, end to end.\n"
        "    - docs/examples/            : worked stories (e.g. the WHEST\n"
        "                                  estimation challenge).\n"
        "    - Try it now: run `dali-onboard --workspace <a small demo dir>`\n"
        "      and pick a tiny paper + code folder to watch the whole loop.",
    ),
    "2": (
        "Skills (what I know how to do)",
        "  Skills are recipe folders that teach me a workflow - like items in\n"
        "  a toolbox. The built-ins live in `rag_ai_scientist/skills/`:\n"
        "    rag-setup, an-pipeline-runner, an-validation,\n"
        "    ap-starterkit-execution, challenge-harness, overleaf-paper-sync,\n"
        "    cms-higgs-opendata, whest-estimation-challenge.\n"
        "  Add your own: copy `skills/_template/`, rename the folder, edit its\n"
        "  SKILL.md (name + description + steps). That's it - it's now mine.",
    ),
    "3": (
        "Tools (what I can run)",
        "  Tools are the commands I can call, exposed over MCP so any AI\n"
        "  client can use them too. See `rag_ai_scientist/mcp_server.py`.\n"
        "  Add your own: register a function as an MCP tool in that server\n"
        "  (same pattern as the existing ones), and it shows up for me and\n"
        "  for Copilot/Cursor/Cline automatically.",
    ),
    "4": (
        "The pipes (the pipeline) & how to extend them",
        "  The 'pipes' are the step-by-step pipeline I build and run: each\n"
        "  step is a small, inspectable unit (read -> build brain -> test ->\n"
        "  plan -> run/validate/correct -> smoke test). Think Minecraft or\n"
        "  Roblox: you snap blocks together and each block does one thing.\n"
        "  Extend them: add or reorder steps in the plan, drop in a skill or\n"
        "  tool as a new block, or edit a step's command/config in the\n"
        "  workspace. Nothing is fixed - open the files and change them.\n"
        "  Contribute a reusable pipe back: add it as a skill folder (see 2)\n"
        "  so everyone gets your block.",
    ),
}


def _print_learn_more() -> None:
    print(
        "\n  Want to know more? Pick a topic:\n"
        "    1) Examples & tutorials   - what to run to see me in action\n"
        "    2) Skills                 - what I can do + how to add your own\n"
        "    3) Tools                  - what I can run + how to add your own\n"
        "    4) The pipes              - the pipeline + how to extend/contribute\n"
        "    (or just press Enter to get started)"
    )


def _learn_more_menu() -> None:
    """Optional educational detour before the session starts (tty only)."""
    if not sys.stdin.isatty():
        return
    _print_learn_more()
    while True:
        try:
            choice = input("\n  learn more [1-4, Enter=skip]: ").strip()
        except EOFError:
            return
        if choice == "":
            return
        topic = _LEARN_TOPICS.get(choice)
        if topic is None:
            print("  (pick 1-4, or press Enter to continue)")
            continue
        title, body = topic
        print(f"\n  -- {title} " + "-" * max(0, 46 - len(title)))
        print(body)
        print("  " + "-" * 50)
        print("  (press Enter for the menu again, or type 'go' to start)")
        try:
            nxt = input("> ").strip().lower()
        except EOFError:
            return
        if nxt == "go":
            return


def _confirm_workspace(workspace_dir: Path, assume_yes: bool) -> None:
    """Make sure the user means to work in this workspace before anything runs."""
    if assume_yes or not sys.stdin.isatty():
        return
    answer = input(f"\n  Is {workspace_dir} the right workspace? [Y/n] ").strip().lower()
    if answer in ("", "y", "yes"):
        return
    print("  No problem - re-run with --workspace /path/to/your/analysis.")
    raise SystemExit(0)


def run_interactive(workspace: str = "", thread_id: str = "dali-onboard",
                    assume_yes: bool = False) -> dict:
    """Terminal REPL driver: resumes each interrupt with human input."""
    workspace_dir = Path(workspace or os.getcwd()).resolve()
    checkpoint_path = workspace_dir / ".dali" / "onboard" / f"{thread_id}.json"
    _print_intro(workspace_dir, checkpoint_path.exists())
    _confirm_workspace(workspace_dir, assume_yes)
    _learn_more_menu()
    checkpointer = FileCheckpointSaver(checkpoint_path)
    graph = build_graph(checkpointer=checkpointer)
    cfg = {"configurable": {"thread_id": thread_id}}
    inputs: dict = {"workspace": str(workspace_dir)}
    out = graph.invoke(inputs, cfg)
    while "__interrupt__" in out:
        prompt = out["__interrupt__"][0].value
        print("\n[DALI]", prompt["ask"])
        if "fields" in prompt:
            print("  (a local path or a URL is fine; I'll fetch URLs;"
                  " for gitlab.cern.ch use a local clone or a PAT in ~/.netrc)")
            reply = {
                "paper_path": input("  paper  > ").strip(),
                "code_path": input("  code   > ").strip(),
                "autonomous": input("  run without asking each step? [y/N] ").lower() == "y",
            }
        elif prompt.get("model_options"):
            default = prompt["ask"].split("recommended:")[-1].strip().split(")")[0]
            choice = input(f"  model [{default}] > ").strip().lower()
            reply = {"model": choice if choice in prompt["model_options"] else default}
        elif prompt.get("agent_options"):
            choice = input("  [i]nstall / [c]ontinue anyway / [a]bort > ").strip().lower() or "continue"
            reply = {"choice": {"i": "install", "c": "continue", "a": "abort"}.get(
                choice[:1], choice if choice in ("install", "continue", "abort") else "continue")}
            if reply["choice"] == "install":
                ide = input("  ide [opencode] > ").strip().lower() or "opencode"
                reply["ide"] = ide
        elif prompt.get("brain_dir"):
            question = input("test question (empty to skip): ").strip()
            reply = {"question": question, "verdict": "approve"} if question else "approve"
        elif "fetch" in prompt.get("ask", "").lower() or "could not fetch" in prompt.get("ask", ""):
            choice = input("  [r]etry / [n]ew paths / [a]bort > ").strip().lower() or "retry"
            reply = {"choice": {"r": "retry", "n": "new paths", "a": "abort"}.get(
                choice[:1], choice if choice in ("retry", "abort") else "retry")}
            if reply["choice"] == "new paths":
                paper = input("  paper  > ").strip()
                code = input("  code   > ").strip()
                if paper:
                    reply["paper_path"] = paper
                if code:
                    reply["code_path"] = code
        else:
            reply = input("> ").strip()
        out = graph.invoke(Command(resume=reply), cfg)
    print("\nChecks:")
    for name, chk in out.get("checks", {}).items():
        mark = "PASS" if chk["ok"] else "FAIL"
        print(f"  [{mark}] {name}: {chk['evidence'][:120]}")
    failed = [n for n, c in out.get("checks", {}).items() if not c["ok"]]
    if failed:
        raise SystemExit(1)
    return out


def run_interactive_cli(workspace: str = "") -> dict:
    """Console-script entry point for `dali-onboard`."""
    import argparse

    parser = argparse.ArgumentParser(prog="dali-onboard",
                                     description="DALI onboarding state machine (LangGraph).")
    parser.add_argument("--workspace", default=workspace or ".",
                        help="Workspace root where .dali/brain is built.")
    parser.add_argument("--thread-id", default="dali-onboard", help="Checkpoint thread id.")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip the workspace confirmation prompt.")
    args = parser.parse_args()
    return run_interactive(workspace=args.workspace, thread_id=args.thread_id,
                           assume_yes=args.yes)


if __name__ == "__main__":
    run_interactive_cli()
