# Getting started (pip install — no GitHub required)

This guide assumes you **only** install from PyPI and create a **normal folder** for your project. You do **not** need to clone a repository or use GitHub.

## What you are building

A **local AI scientist setup**: your PDFs, notes, and instructions live in one directory; `rag-ai-scientist` indexes them into a private vector database under **`.cursor/rag_db`**. Cursor (or any MCP client) can then **query that knowledge** and use **packaged skills** (checklists for specific workflows).

---

## 1) Prerequisites

- **Python 3.10+**
- **`pip`**
- Optional: **Cursor** (or another MCP-capable editor) — recommended so agents can call the tools.

---

## 2) Install the package

```bash
python3 -m venv ~/.venvs/rag-ai-scientist
source ~/.venvs/rag-ai-scientist/bin/activate   # Windows: use .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install rag-ai-scientist
```

Verify:

```bash
rag-ai-scientist --help
```

---

## 3) Create a project folder (anywhere on your machine)

Use any path you like. No `git init` required.

```bash
mkdir -p ~/my-ai-scientist/references
cd ~/my-ai-scientist
```

---

## 4) Add **your** research and instructions

Put materials you want the model to retrieve under **`references/`** (or another folder name you prefer):

- Notes and methodology: **`.md`**, **`.txt`**
- Papers: **`.pdf`**
- Small code snippets or configs: **`.py`**, **`.tex`** (see indexer limits in **`docs/REFERENCES.md`**)

Example — create a starter note:

```bash
cat > references/project_context.md << 'EOF'
# My research context

## Goal
Describe what you are trying to learn or reproduce.

## Conventions
Define symbols, datasets, and filenames agents should respect.

## Do / don't
What must never be overwritten; what is allowed to change.
EOF
```

You maintain these files like normal documentation; they are **your** ground truth for the AI scientist.

---

## 5) Point the tool at your folder and build the index

From **`~/my-ai-scientist`** (your project root):

```bash
rag-ai-scientist init-references \
  --project-root . \
  --references-dir ./references
```

This creates **`configs/references.yaml`**. Then build the database:

```bash
rag-ai-scientist setup-rag --project-root . --force
```

After this, **`./.cursor/rag_db`** exists and holds embeddings for everything under your references path.

---

## 6) Start the MCP server (for Cursor / agents)

In the same environment where `rag-ai-scientist` is installed:

```bash
rag-ai-scientist mcp --project-root .
```

Typically you do **not** run this by hand every time — you register one persistent command in Cursor (next section).

---

## 7) Cursor MCP configuration

Use an **absolute path** to your project root (the directory that contains **`configs/`** and **`.cursor/rag_db`**).

Example **`~/.cursor/mcp.json`** fragment:

```json
{
  "mcpServers": {
    "rag-ai-scientist": {
      "command": "rag-ai-scientist",
      "args": ["mcp", "--project-root", "/absolute/path/to/my-ai-scientist"]
    }
  }
}
```

Use the same Python environment as `rag-ai-scientist` (same `command` resolution). On Windows, use the full path to `rag-ai-scientist.exe` if needed.

Optional: copy **`.env.example`** patterns from the maintainer docs into **`./.cursor/.env`** if you want LLM-assisted answers (e.g. **`GROQ_API_KEY`**); without it, retrieval still works with extractive snippets.

---

## 8) What you can ask the system to do

| Mechanism | What it uses |
|-----------|----------------|
| **`query_analysis_knowledge`** | Your **indexed** files under `references/` (after `setup-rag`). |
| **`get_skill`** | **Packaged** markdown skills shipped inside the wheel (no indexing). Example: **`cms-higgs-opendata`** for a CMS open-data Higgs checklist. |
| **`retrieve_documents`** / **`search_papers`** | Raw or filtered chunks from your index (depending on metadata). |

So: **your research** → index **your** folder; **generic workflows** → **`get_skill`** without extra files.

---

## 9) Update instructions and refresh the index

When you change notes or add papers:

1. Edit or drop files under **`references/`** (or add new directories).
2. If you added **new top-level paths**, edit **`configs/references.yaml`** and add those paths under **`sources`** (see **`docs/REFERENCES.md`**).
3. Rebuild:

   ```bash
   rag-ai-scientist setup-rag --project-root . --force
   ```

That is the normal maintenance loop for your AI scientist’s knowledge base.

---

## 10) Optional: advanced / maintainer workflows

- Full reliability-loop scripts, extra configs, and contributor setup are described elsewhere in **`docs/`** (for people working from a full checkout).
- Developer install and PyPI release: **`DEV_README.md`**.

---

## Summary

| Step | Action |
|------|--------|
| Install | `pip install rag-ai-scientist` |
| Project | Ordinary folder + `references/` with your files |
| Configure | `init-references` → `setup-rag --force` |
| Agents | `rag-ai-scientist mcp` via Cursor MCP |
| Maintain | Edit references → rerun `setup-rag --force` |

No GitHub step.
