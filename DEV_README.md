# Maintainer / development notes

End-user documentation is in [`README.md`](./README.md). This file is for **editable installs**, **release builds**, and **PyPI uploads**.

## Local editable install

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Use `uv` if you prefer (`uv pip install -e .`).

## Test the whest example locally

```bash
pip install -e .
cd ../whest-starterkit
bash scripts/setup_rag_references.sh
rag-ai-scientist init-references --project-root . --references-dir ./references --force
rag-ai-scientist setup-rag --project-root . --force
python -c "from pathlib import Path; import rag_ai_scientist; p=Path(rag_ai_scientist.__file__).parent/'skills'/'whest-estimation-challenge'/'SKILL.md'; print(p.read_text()[:200])"
```

## Publishing a release to PyPI

### Prerequisites

- Maintainer access to the [`rag-ai-scientist`](https://pypi.org/project/rag-ai-scientist/) project on PyPI.
- A **PyPI API token** (Account settings → API tokens).
- Bump **`version`** in `pyproject.toml` and `rag_ai_scientist/__init__.py` before uploading.

### Build and upload

```bash
rm -rf dist/ build/ rag_ai_scientist.egg-info
python -m build
twine check dist/*
twine upload dist/*
```

See the full credential and Test PyPI notes in the GitHub `dev` branch copy of this file.

### Release checklist (0.1.5+)

- [ ] New skill under `rag_ai_scientist/skills/` ships in wheel (`skills/**/*.md` in `pyproject.toml`)
- [ ] Harness profile registered (`harness/profiles/` + `registry.py`)
- [ ] Overleaf tools smoke-tested with `OVERLEAF_PROJECTS_CONFIG` (no tokens committed)
- [ ] Mirror skill in `.cursor/skills/` for local MCP override
- [ ] Example narrative in `docs/examples/` if retrieval should cite it
- [ ] README mentions new skill / harness / overleaf commands
- [ ] Smoke test: `pip install dist/*.whl` and `get_skill` / `harness list`
