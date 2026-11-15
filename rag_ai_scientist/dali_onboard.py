"""DALI onboarding as a LangGraph state machine.

Flow: inputs -> check agent -> fetch inputs -> choose embedding model
      -> embed+chunk -> build RAG brain -> test brain (human gate)
      -> summarize the analysis from the brain (human gate)
      -> plan the DAG + golden benchmarks -> render WORKFLOW.md / pipeline.yaml
         (human gate) -> [execute -> validate -> correct]* -> smoke test -> done

Deterministic nodes do the work (they reuse the rag-ai-scientist indexing and
harness machinery); the LLM is only used in summarize(), plan_dag() and
correct(), and every LLM proposal is still executed and validated by the
harness - never trusted. Every node writes a verifiable check into
state["checks"].

After the plan gate the workflow is written out as plain-language artifacts the
human can read and edit:

    WORKFLOW.md               goal, main result, reverse-engineered plan, and a
                              table of steps with the golden benchmark per step
    state/pipeline.yaml       machine-readable steps + checks (source of truth)
    reports/pipeline-dag.dot  step dependency graph (dot -Tsvg)

Reference numbers quoted in those artifacts are extracted from brain chunks and
carry the doc path they were read from; nothing is invented, and a step with no
traceable number is left to a human instead of being guessed.

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
MAX_BENCHMARKS_PER_STEP = 8
PLAIN_WORDS_RULE = (
    "Use plain words a new collaborator can follow: short sentences, no jargon "
    "without a one-line explanation, and always say what a number is for."
)

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
    summary: dict             # {"goal", "result", "plan"} in plain words, from the brain
    plan: list[dict]          # DAG steps: description/command/check/depends_on/benchmarks
    artifacts: dict           # rendered artifact name -> path
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
    """One factory so brain build, probe, and query always agree on the model.

    DALI_EMBEDDING_CLASS="pkg.module:Name" overrides it with any object exposing
    embed_documents/embed_query; the offline demo uses that hook so nothing has
    to monkeypatch module globals."""
    override = os.environ.get("DALI_EMBEDDING_CLASS", "").strip()
    if override:
        module_name, _, attr = override.partition(":")
        import importlib

        return getattr(importlib.import_module(module_name), attr)()
    model = state.get("embedding_model") or EMBEDDING_MODELS["small"][0]
    from langchain_huggingface import HuggingFaceEmbeddings
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


def _parse_json_object(text: str) -> Optional[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _ask_json(llm, prompt: str) -> Any:
    """One LLM call, JSON in / Python out (dict or list). None on any failure."""
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        reply = llm.invoke([
            SystemMessage(content="Reply with valid JSON only."),
            HumanMessage(content=prompt),
        ])
    except Exception as exc:
        print(f"[llm] call failed ({exc}); continuing without it.")
        return None
    text = getattr(reply, "content", "") or ""
    return _parse_json_object(text) if "{" in text else _parse_json_array(text)


def _brain_hits(state: State, query: str, k: int = 6) -> list[tuple[str, str]]:
    """(doc_path, text) pairs straight from the brain; [] when it is unavailable."""
    try:
        context = _brain_context(state, query, k=k)
    except Exception:
        return []
    hits = []
    for block in context.split("\n\n---\n"):
        block = block.strip()
        if not block.startswith("["):
            continue
        path, _, body = block.partition("]\n")
        hits.append((path.lstrip("[").strip(), body.strip()))
    return hits


def _material(hits: list[tuple[str, str]], per_hit: int = 1200) -> str:
    return "\n\n---\n".join(f"[{path}]\n{text[:per_hit]}" for path, text in hits)


def summarize(state: State) -> dict:
    """Read the brain and say, in plain words, what the analysis is for, which
    result a reproduction has to land on, and how to work backwards from that
    result to the input data. Nothing is executed here."""
    hits = _brain_hits(
        state,
        "What is the physics goal of this analysis, what is the headline result "
        "or number, and what are the analysis stages in order?",
        k=8,
    )
    material = _material(hits)
    llm = _get_llm()
    summary: dict = {}
    if llm is not None and material:
        data = _ask_json(llm, (
            "You are the DALI onboarding summariser. From the material below, write "
            "three short plain-language blocks about this analysis.\n"
            f"{PLAIN_WORDS_RULE}\n"
            'Reply ONLY {"goal": str, "result": str, "plan": str} where\n'
            '  goal   = 2-4 sentences: what the analysis is trying to measure, and why;\n'
            '  result = 1-3 sentences: the headline number a reproduction must land on, '
            'with units, plus anything the documents do not let us check;\n'
            '  plan   = the route from that final number back to the raw data, one stage '
            'per line, each line saying what that stage has to produce.\n'
            f"Material:\n{material}"
        ))
        if isinstance(data, dict):
            summary = {key: str(data[key]).strip()
                       for key in ("goal", "result", "plan") if data.get(key)}
    incomplete = not summary.get("goal")
    if incomplete:
        summary = {
            "goal": "(no LLM key, or nothing retrievable: state the goal yourself - "
                    "which number must this reproduction land on?)",
            "result": summary.get("result", "(not extracted)"),
            "plan": summary.get("plan", "(not extracted)"),
        }
    return {"summary": summary,
            "checks": _check(state, "summary", not incomplete,
                             f"goal: {summary['goal'][:200]}")}


def approve_summary(state: State) -> dict:
    """Human gate: is the plain-language summary right, before we plan against it?"""
    verdict = interrupt({
        "ask": "Is this summary of the analysis right (goal / result / route)?",
        "gate_options": ["approve", "rebuild"],
        "summary": state.get("summary", {}),
    })
    verdict = verdict.get("verdict", "approve") if isinstance(verdict, dict) else str(verdict)
    return {"checks": _check(state, "summary_test", verdict == "approve", f"user: {verdict}")}


_FALLBACK_PLAN = [
    {"id": "reproduce", "description": "reproduce nominal result", "command": "",
     "check": "human confirms output matches reference", "depends_on": [],
     "benchmarks": []},
    {"id": "preselect", "description": "run preselection", "command": "",
     "check": "exit code 0 and non-empty output", "depends_on": ["reproduce"],
     "benchmarks": []},
    {"id": "fit", "description": "run fit", "command": "",
     "check": "exit code 0 and converged", "depends_on": ["preselect"],
     "benchmarks": []},
]


def _normalise_plan(parsed: list) -> list[dict]:
    """Validate a proposed plan into DAG steps: unique ids, no unknown or
    forward dependencies, benchmarks kept only when they carry a value."""
    steps: list[dict] = []
    seen: set[str] = set()
    for i, raw in enumerate(parsed):
        if not isinstance(raw, dict):
            continue
        step_id = str(raw.get("id") or f"step{i + 1}").strip().replace(" ", "-")
        while step_id in seen:
            step_id = f"{step_id}-{len(seen) + 1}"
        seen.add(step_id)
        benchmarks = []
        for b in (raw.get("benchmarks") or [])[:MAX_BENCHMARKS_PER_STEP]:
            if not isinstance(b, dict) or b.get("value") in (None, ""):
                continue
            benchmarks.append({
                "quantity": str(b.get("quantity", "")).strip(),
                "value": b.get("value"),
                "unit": str(b.get("unit", "")).strip(),
                "source": str(b.get("source", "")).strip() or "(no source given)",
                "confidence": "extracted-unverified",
            })
        steps.append({
            "id": step_id,
            "description": str(raw.get("description", f"step {i + 1}")).strip(),
            "command": str(raw.get("command", "")).strip(),
            "check": str(raw.get("check", "exit code 0")).strip(),
            "depends_on": [str(d).strip() for d in (raw.get("depends_on") or [])],
            "benchmarks": benchmarks,
        })
    ids = {s["id"] for s in steps}
    order: list[str] = []
    kept: list[dict] = []
    for s in steps:
        # only earlier steps can be depended on: that alone keeps the graph acyclic
        s["depends_on"] = [d for d in s["depends_on"] if d in ids and d in order]
        order.append(s["id"])
        kept.append(s)
    return kept


def plan_dag(state: State) -> dict:
    """Turn the brain into a DAG of verifiable steps, each carrying the golden
    benchmarks (reference number + the doc it was read from) that validate it."""
    summary = state.get("summary", {})
    hits = _brain_hits(
        state,
        "What are the analysis stages, the commands that run them, and the "
        "reference numbers (counts, thresholds, yields, uncertainties) quoted in "
        "the documentation for each stage?",
        k=10,
    )
    material = _material(hits)
    llm = _get_llm()
    plan: list[dict] = []
    if llm is not None and material:
        data = _ask_json(llm, (
            "You are the DALI onboarding planner. Reverse-engineer this analysis "
            "into a plan of 4-10 steps, starting from the result that must be "
            "reproduced and working back to the input data.\n"
            f"{PLAIN_WORDS_RULE}\n"
            'Reply ONLY {"steps": [ ... ]} where each step is\n'
            '  {"id": short-kebab-id, "description": what this step does in plain '
            'words, "command": shell command runnable from the workspace root (empty '
            'string if a human has to do it), "check": how success is verified, '
            '"depends_on": [ids of earlier steps only], '
            '"benchmarks": [{"quantity": str, "value": number or [min, max], '
            '"unit": str, "source": the path from the [brackets] of the material '
            'block you took it from"}]}\n'
            "Hard rule for benchmarks: quote only numbers that appear verbatim in the "
            "material, always with their source path; if a step has no such number, "
            "return an empty list instead of guessing one.\n"
            f"Goal: {summary.get('goal', '')}\n"
            f"Result to reproduce: {summary.get('result', '')}\n"
            f"Route: {summary.get('plan', '')}\n\nMaterial:\n{material}"
        ))
        parsed = data.get("steps") if isinstance(data, dict) else data
        if isinstance(parsed, list):
            plan = _normalise_plan(parsed)
    if not plan:
        plan = [dict(s, benchmarks=list(s["benchmarks"])) for s in _FALLBACK_PLAN]
    n_bench = sum(len(s["benchmarks"]) for s in plan)
    return {"plan": plan, "step": 0, "loops": 0,
            "checks": _check(state, "plan", bool(plan),
                             f"{len(plan)} steps, {n_bench} benchmarks with sources")}


def render_workflow_markdown(summary: dict, plan: list[dict]) -> str:
    """Plain-language one-file view: goal, the result to land on, the route
    backwards, and a table of steps with the golden benchmark for each."""
    out = ["# Analysis workflow (DALI onboarding)\n",
           "> Written by `dali-onboard` from the project brain. Machine-readable "
           "version: `state/pipeline.yaml` (the source of truth); DAG: "
           "`reports/pipeline-dag.dot` (`dot -Tsvg` it to see the picture).\n",
           "## What this analysis is trying to do\n",
           summary.get("goal", "(not summarised)"), "",
           "## The result we have to land on\n",
           summary.get("result", "(not summarised)"), "",
           "## The plan, read backwards from the result\n",
           "```", summary.get("plan", "(not summarised)"), "```", "",
           "## Steps and golden benchmarks\n",
           "| # | Step | How it is checked | Golden benchmark (from the docs) | Source |",
           "|---|---|---|---|---|"]
    for i, step in enumerate(plan):
        deps = f" (after {', '.join(step['depends_on'])})" if step["depends_on"] else ""
        command = f"\n  `{step['command']}`" if step["command"] else ""
        if step["benchmarks"]:
            bench, sources = [], []
            for b in step["benchmarks"]:
                unit = f" {b['unit']}" if b["unit"] else ""
                bench.append(f"{b['quantity']}: **{b['value']}**{unit}")
                sources.append(b["source"])
            bench_cell = "<br>".join(bench)
            source_cell = "<br>".join(dict.fromkeys(sources))
        else:
            bench_cell, source_cell = "_none extracted - human to supply_", "-"
        out.append(f"| {i} | **{step['id']}**{deps} | {step['check']}{command} "
                   f"| {bench_cell} | {source_cell} |")
    out += ["",
            "Benchmarks are marked `extracted-unverified` in `state/pipeline.yaml`: "
            "the planner read them out of the documentation, and they are not "
            "checked against a table until that step actually runs. A step with no "
            "benchmark is validated by a person, never by a guessed number.", "",
            "Rules: a failed check is fixed in the code or the config, never in an "
            f"output or a reference value; max {MAX_LOOPS} attempts per step, then "
            "escalate to a human."]
    return "\n".join(out) + "\n"


def _dot_label(step: dict) -> str:
    return f"{step['id']}|{step['description'][:60]}".replace('"', "'").replace("\n", " ")


def render_artifacts(state: State) -> dict:
    """Write the workflow out for a human to read and edit. Deterministic: no
    LLM, so re-running it on the same plan gives the same files."""
    import yaml

    workspace = Path(state.get("workspace") or os.getcwd())
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / "state").mkdir(parents=True, exist_ok=True)

    plan = state.get("plan", [])
    pipeline = {
        "defaults": {"max_attempts": MAX_LOOPS,
                     "embedding_model": state.get("embedding_model", "")},
        "summary": state.get("summary", {}),
        "steps": [{
            "id": s["id"],
            "title": s["description"],
            "command": s["command"],
            "checks": [{"type": "human", "description": s["check"]}],
            "benchmarks": s["benchmarks"],
            "depends_on": s["depends_on"],
            "status": "pending",
        } for s in plan],
    }
    pipeline_path = workspace / "state" / "pipeline.yaml"
    pipeline_path.write_text(
        "# Pipeline single source of truth - written by dali-onboard.\n"
        "# Benchmarks are reference numbers read out of the docs (see source);\n"
        "# they stay 'extracted-unverified' until the step that checks them runs.\n"
        "# Edit this file, then re-run dali-onboard to refresh the reports.\n"
        + yaml.safe_dump(pipeline, sort_keys=False, width=100),
        encoding="utf-8",
    )

    lines = ["digraph dali_workflow {",
             "  graph[rankdir=LR]; node[shape=box, style=rounded];"]
    lines += [f'  "{s["id"]}" [label="{_dot_label(s)}"];' for s in plan]
    lines += [f'  "{dep}" -> "{s["id"]}";'
              for s in plan for dep in s["depends_on"]]
    lines.append("}")
    dag_path = workspace / "reports" / "pipeline-dag.dot"
    dag_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    workflow_path = workspace / "WORKFLOW.md"
    workflow_path.write_text(render_workflow_markdown(state.get("summary", {}), plan),
                             encoding="utf-8")

    artifacts = {"WORKFLOW.md": str(workflow_path),
                 "state/pipeline.yaml": str(pipeline_path),
                 "reports/pipeline-dag.dot": str(dag_path)}
    n_bench = sum(len(s["benchmarks"]) for s in plan)
    return {"artifacts": artifacts,
            "checks": _check(state, "artifacts", workflow_path.exists(),
                             f"{len(plan)} steps, {n_bench} benchmarks -> "
                             f"{', '.join(artifacts)}")}


def approve_plan(state: State) -> dict:
    """Human gate: read the rendered workflow, then approve the plan, or edit
    state/pipeline.yaml and rebuild from it."""
    verdict = interrupt({
        "ask": "Read WORKFLOW.md (the steps and their golden benchmarks). Approve the "
               "plan, or edit state/pipeline.yaml and choose rebuild.",
        "gate_options": ["approve", "rebuild"],
        "artifacts": state.get("artifacts", {}),
    })
    verdict = verdict.get("verdict", "approve") if isinstance(verdict, dict) else str(verdict)
    return {"checks": _check(state, "plan_test", verdict == "approve", f"user: {verdict}")}


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


def after_brain_test(state) -> Literal["summarize", "build_brain"]:
    return "summarize" if state["checks"]["brain_test"]["ok"] else "build_brain"


def after_summary_test(state) -> Literal["plan_dag", "build_brain"]:
    return "plan_dag" if state["checks"]["summary_test"]["ok"] else "build_brain"


def after_plan_test(state) -> Literal["execute", "build_brain"]:
    return "execute" if state["checks"]["plan_test"]["ok"] else "build_brain"


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
               embed_and_chunk, build_brain, test_brain, summarize,
               approve_summary, plan_dag, render_artifacts, approve_plan,
               execute, validate, correct, advance, smoke_test):
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
    g.add_conditional_edges("test_brain", after_brain_test,
                            {"summarize": "summarize", "build_brain": "build_brain"})
    g.add_edge("summarize", "approve_summary")
    g.add_conditional_edges("approve_summary", after_summary_test,
                            {"plan_dag": "plan_dag", "build_brain": "build_brain"})
    g.add_edge("plan_dag", "render_artifacts")
    g.add_edge("render_artifacts", "approve_plan")
    g.add_conditional_edges("approve_plan", after_plan_test,
                            {"execute": "execute", "build_brain": "build_brain"})
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


def _print_summary(summary: dict) -> None:
    print("\n  -- What I think this analysis is " + "-" * 16)
    print(f"  GOAL\n    {summary.get('goal', '(none)')}\n")
    print(f"  RESULT TO LAND ON\n    {summary.get('result', '(none)')}\n")
    print("  ROUTE, BACKWARDS FROM THE RESULT")
    for line in str(summary.get("plan", "(none)")).splitlines() or ["(none)"]:
        print(f"    {line}")
    print("  " + "-" * 56)


def _print_plan_table(plan: list[dict], artifacts: dict) -> None:
    print("\n  -- Steps and golden benchmarks " + "-" * 24)
    print(f"  {'#':<3} {'step':<18} {'after':<16} benchmark (read out of the docs)")
    for i, step in enumerate(plan):
        deps = ",".join(step.get("depends_on", [])) or "-"
        benches = step.get("benchmarks") or []
        if benches:
            first = benches[0]
            more = f" (+{len(benches) - 1} more)" if len(benches) > 1 else ""
            unit = f" {first['unit']}" if first.get("unit") else ""
            bench = f"{first['quantity']} = {first['value']}{unit}{more}"
        else:
            bench = "none extracted - human to supply"
        print(f"  {i:<3} {step['id']:<18} {deps:<16} {bench[:58]}")
    print("  " + "-" * 56)
    for name, path in artifacts.items():
        print(f"  wrote {name}: {path}")


def _verdict_gate() -> str:
    """approve / rebuild gate: Enter approves, r rebuilds."""
    while True:
        answer = input("  [Enter] = approve, r = rebuild: ").strip().lower()
        if answer in ("", "a", "approve"):
            return "approve"
        if answer in ("r", "rebuild"):
            return "rebuild"
        print("  (press Enter to approve, or r to rebuild)")


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
        elif prompt.get("summary"):
            _print_summary(prompt["summary"])
            reply = _verdict_gate()
        elif prompt.get("artifacts"):
            _print_plan_table(out.get("plan", []), prompt["artifacts"])
            reply = _verdict_gate()
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
    if out.get("artifacts"):
        print("\nWorkflow written to:")
        for name, path in out["artifacts"].items():
            print(f"  {name}: {path}")
    failed = [n for n, c in out.get("checks", {}).items() if not c["ok"]]
    if failed:
        raise SystemExit(1)
    return out


# ---- offline demo ----------------------------------------------------------
# A scripted session that drives the real nodes with the LLM and the embedding
# model stubbed out, so a newcomer can watch the whole onboarding - brain,
# summary gate, plan gate, WORKFLOW.md - in seconds, offline, without API keys.
# The numbers below are invented for a fictional "Aurora" analysis; they exist
# only so the demo has something to retrieve.

DEMO_PAPER = """# Aurora D0 CP violation tutorial (demo)

We measure CP violation in D0 -> K+ K- pi+ pi- and D0 -> pi+ pi+ pi- pi- with
the Run 2 sample, 2015 to 2018 in both magnet polarities.

The statistical sensitivity of the measurement is 3.4e-4 for the four-pion
mode and 8.1e-4 for the KKpipi mode.

## Stages

1. Skimming: keep one candidate per event, require PNNK above 0.05 and a D0
   mass between 1.84 and 1.89 GeV.
2. Signal extraction: build the angular variables, bin the phase space at the
   phi(1019.455 MeV), rho(775.49 MeV) and K*(896 MeV) pole masses.
3. Efficiency: reweight simulation with a gradient-boosting model; the weight
   uncertainty plateaus at 0.007 for weights above 0.03, from 100 bootstrap
   toys.
4. Mass fits: count signal in each bin. The 2015 MagUp KKpipi signal yield is
   65215 candidates.
5. CP asymmetries: assemble the binned asymmetries and quote the sensitivity.
6. Systematics: kaon reconstruction asymmetry 0.3e-4, peaking background 1e-5,
   control sample 1.0e-4.
"""

DEMO_CODE = {
    "selector.py": '"""Offline selection."""\n'
                   'PNNK_MIN = 0.05\nD0_MASS = (1.84, 1.89)\n'
                   'def select(tree):\n    return tree\n',
    "binning.py": '"""Phase-space binning."""\n'
                  'PHI_MASS = 1019.455\nRHO_MASS = 775.49\nKSTAR_MASS = 896.0\n'
                  'def bin_phase_space(tree):\n    return tree\n',
    "simfit.py": '"""1D mass fits for the signal yield."""\n'
                 'def fit(tree):\n    return 0.0\n',
}

DEMO_SUMMARY = {
    "goal": "We check whether matter and antimatter versions of the D0 decay at "
            "slightly different rates into four lighter particles. A difference "
            "would be CP violation, one of the clues for why the universe holds "
            "matter at all.",
    "result": "The number a reproduction has to land on is the statistical "
              "sensitivity: 3.4e-4 for the four-pion mode and 8.1e-4 for the "
              "KKpipi mode. The final binned asymmetries are not in the demo "
              "notes, so they cannot be checked.",
    "plan": "sensitivity  <-  binned CP asymmetries\n"
            "asymmetries  <-  mass fits (signal counts per bin)\n"
            "fits         <-  efficiency model + binned angular variables\n"
            "angles       <-  skimmed candidates (selection cuts)\n"
            "skimming     <-  input ntuples",
}

DEMO_PLAN = [
    {"id": "environment", "description": "build the code so later steps run in a known state",
     "command": "cd code && python -c \"import selector, binning, simfit\"",
     "check": "the three modules import cleanly", "depends_on": [], "benchmarks": []},
    {"id": "skimming", "description": "apply the selection and keep the surviving candidates",
     "command": "python selector.py", "check": "cut values in the code match the notes",
     "depends_on": ["environment"],
     "benchmarks": [
         {"quantity": "PNNK threshold", "value": 0.05, "unit": "none",
          "source": "paper/main.md"},
         {"quantity": "D0 mass window", "value": [1.84, 1.89], "unit": "GeV",
          "source": "paper/main.md"}]},
    {"id": "signal", "description": "compute the angles and bin the phase space",
     "command": "python binning.py", "check": "bin edges sit at the resonance poles",
     "depends_on": ["skimming"],
     "benchmarks": [
         {"quantity": "phi pole mass", "value": 1019.455, "unit": "MeV",
          "source": "paper/main.md"},
         {"quantity": "rho pole mass", "value": 775.49, "unit": "MeV",
          "source": "paper/main.md"},
         {"quantity": "K*(892) pole mass", "value": 896, "unit": "MeV",
          "source": "paper/main.md"}]},
    {"id": "efficiency", "description": "learn from simulation how often a candidate is detected",
     "command": "", "check": "a human confirms the weight uncertainty plateau",
     "depends_on": ["signal"],
     "benchmarks": [
         {"quantity": "weight uncertainty plateau", "value": 0.007, "unit": "none",
          "source": "paper/main.md"},
         {"quantity": "bootstrap toys", "value": 100, "unit": "toys",
          "source": "paper/main.md"}]},
    {"id": "fit", "description": "fit the mass peak and count the signal in each bin",
     "command": "python simfit.py", "check": "yields agree with the notes",
     "depends_on": ["signal", "efficiency"],
     "benchmarks": [
         {"quantity": "2015 MagUp KKpipi signal yield", "value": 65215, "unit": "candidates",
          "source": "paper/main.md"}]},
    {"id": "cpv", "description": "turn the counts into the physics number",
     "command": "", "check": "sensitivity matches the notes", "depends_on": ["fit"],
     "benchmarks": [
         {"quantity": "sensitivity, four-pion mode", "value": 3.4e-4, "unit": "none",
          "source": "paper/main.md"},
         {"quantity": "sensitivity, KKpipi mode", "value": 8.1e-4, "unit": "none",
          "source": "paper/main.md"}]},
    {"id": "systematics", "description": "check the signal is not a detector effect",
     "command": "", "check": "each assigned uncertainty matches the notes",
     "depends_on": ["cpv"],
     "benchmarks": [
         {"quantity": "kaon reconstruction asymmetry", "value": 0.3e-4, "unit": "none",
          "source": "paper/main.md"},
         {"quantity": "peaking background", "value": 1e-5, "unit": "none",
          "source": "paper/main.md"},
         {"quantity": "control sample", "value": 1.0e-4, "unit": "none",
          "source": "paper/main.md"}]},
]


class _DemoLLM:
    """Scripted stand-in for the chat model: answers the planner prompt with
    DEMO_PLAN so the demo shows the real node logic without a network call."""

    def invoke(self, messages):
        from langchain_core.messages import HumanMessage

        prompt = next((m.content for m in messages if isinstance(m, HumanMessage)), "")
        if '"steps"' in prompt:
            payload = {"steps": [
                {k: v for k, v in step.items() if k != "confidence"} for step in DEMO_PLAN
            ]}
        else:
            payload = dict(DEMO_SUMMARY)
        return type("Reply", (), {"content": json.dumps(payload)})()


DEMO_EMBEDDING_NAME = "demo-hashing-embeddings"


class _HashedEmbeddings:
    """Word-hash embeddings: deterministic, offline, no model download. Retrieval
    still behaves (shared words score highest), which is all the demo needs."""

    DIMS = 256

    def _one(self, text: str) -> list[float]:
        import hashlib
        import math

        vector = [0.0] * self.DIMS
        for word in "".join(c if c.isalnum() else " " for c in text.lower()).split():
            slot = int(hashlib.md5(word.encode()).hexdigest()[:8], 16) % self.DIMS
            vector[slot] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts):
        return [self._one(t) for t in texts]

    def embed_query(self, text):
        return self._one(text)

    def embed_query_with_scores(self, text):  # pragma: no cover - interface parity
        return self.embed_query(text)


def run_demo(workspace: str = "", verbose: bool = True) -> dict:
    """Drive the real nodes end to end on a throwaway project, offline.

    Stubs only the two things that need a download or a key: the embedding model
    and the chat model. Everything else - chunking, the chroma brain, the
    retrieval behind the summary, plan validation, artifact rendering - is the
    production code path.
    """
    # The embedding override stays set for the caller too: the checks a caller
    # runs afterwards (the demo tests, dali-onboard-demo) query the same brain,
    # and only this demo ever names the demo model.
    previous_override = os.environ.get("DALI_EMBEDDING_CLASS")
    os.environ["DALI_EMBEDDING_CLASS"] = f"{__name__}:_HashedEmbeddings"
    workspace_dir = Path(workspace or os.getcwd()).resolve()
    project = workspace_dir / ".dali" / "onboard" / "demo-project"
    (project / "paper").mkdir(parents=True, exist_ok=True)
    (project / "code").mkdir(parents=True, exist_ok=True)
    (project / "paper" / "main.md").write_text(DEMO_PAPER, encoding="utf-8")
    for name, text in DEMO_CODE.items():
        (project / "code" / name).write_text(text, encoding="utf-8")

    def say(text: str = "") -> None:
        if verbose:
            print(text, flush=True)

    real_llm = _get_llm
    globals()["_get_llm"] = _DemoLLM
    state: State = {"workspace": str(project),
                    "paper_path": str(project / "paper" / "main.md"),
                    "code_path": str(project / "code"),
                    "autonomous": False,
                    "embedding_model": DEMO_EMBEDDING_NAME}
    try:
        say("\n  [1/6] chunking the paper and the code, building the brain")
        state.update(embed_and_chunk(state))
        say(f"         {state['checks']['chunks']['evidence']}")
        state.update(build_brain(state))
        say(f"         {state['checks']['brain']['evidence']}")

        say("\n  [2/6] asking the brain a question a person would ask")
        answered, evidence = _brain_probe(state, "What is the statistical sensitivity?")
        say(f"         answered={answered}  top hit: "
            f"{evidence.splitlines()[0][:100] if answered else evidence}")

        say("\n  [3/6] summarising the analysis from what the brain returns")
        state.update(summarize(state))
        _print_summary(state["summary"])

        say("\n  [4/6] planning the steps and pulling the golden benchmarks out of the docs")
        state.update(plan_dag(state))
        say(f"         {state['checks']['plan']['evidence']}")

        say("\n  [5/6] writing the workflow files")
        state.update(render_artifacts(state))
        _print_plan_table(state["plan"], state["artifacts"])

        say("\n  [6/6] running one step through the execute -> validate loop")
        # execute() would ask a human first (autonomous=False) and interrupt()
        # needs a graph context, so the demo shows the gate it would ask and
        # then runs the step as if it had been approved.
        first = state["plan"][0]
        say(f"         gate it would ask: run step 1/{len(state['plan'])}: "
            f"{first['description']}? [run|skip|stop]  -> demo answers: run")
        state["step"] = 0
        state.update(execute({**state, "autonomous": True}))
        state.update(validate(state))
        say(f"         step {first['id']!r}: rc="
            f"{state['last_result'].get('returncode')}, "
            f"validate={state['checks']['validate_0']['ok']}")
    finally:
        globals()["_get_llm"] = real_llm

    say("")
    return state


def _restore_embedding_override(previous: Optional[str]) -> None:
    if previous is None:
        os.environ.pop("DALI_EMBEDDING_CLASS", None)
    else:
        os.environ["DALI_EMBEDDING_CLASS"] = previous


def run_demo_cli(workspace: str = "") -> dict:
    """Console-script entry point for `dali-onboard-demo`."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="dali-onboard-demo",
        description="Watch DALI onboarding work, offline: no API keys, no model download.")
    parser.add_argument("--workspace", default=workspace or ".",
                        help="Where the throwaway demo project is written.")
    parser.add_argument("--quiet", action="store_true", help="Only the final checks.")
    args = parser.parse_args()
    previous = os.environ.get("DALI_EMBEDDING_CLASS")
    state = run_demo(workspace=args.workspace, verbose=not args.quiet)
    checks = dict(state.get("checks", {}))
    # the demo brain is only reachable through the demo model, so query it
    # before handing the environment back
    answered = _demo_probe_ok(state)
    checks["brain_probe"] = {
        "ok": answered,
        "evidence": "the brain answers a question about its own project",
    }
    _restore_embedding_override(previous)
    print("\nChecks:")
    for name, chk in checks.items():
        print(f"  [{'PASS' if chk['ok'] else 'FAIL'}] {name}: {chk['evidence'][:110]}")
    if any(not c["ok"] for c in checks.values()):
        raise SystemExit(1)
    print("\nOpen the result: "
          f"{Path(state['workspace']) / 'WORKFLOW.md'}")
    return state


def _demo_probe_ok(state: State) -> bool:
    """The demo must be able to answer a real question from its own brain."""
    answered, evidence = _brain_probe(state, "What is the statistical sensitivity?")
    return answered and "paper/main.md" in evidence


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
