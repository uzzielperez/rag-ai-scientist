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

## Publishing a release to PyPI

### Prerequisites

- Maintainer access to the [`rag-ai-scientist`](https://pypi.org/project/rag-ai-scientist/) project on PyPI.
- A **PyPI API token** (Account settings → API tokens). You cannot retrieve an old token; create a new one if lost.
- Bump **`version`** in `pyproject.toml` before uploading a new release; re-uploading the same version fails unless you use `--skip-existing` (usually avoid).

### Optional: virtualenv for build/upload tools

Keeps `build` / `twine` separate from runtime deps:

```bash
python3 -m venv .venv-publish
source .venv-publish/bin/activate
python -m pip install --upgrade pip build twine
```

### Clean previous artifacts

From the repository root:

```bash
rm -rf dist/ build/ rag_ai_scientist.egg-info
```

### Build source distribution and wheel

```bash
python -m build
```

This writes files under `dist/` (for example `rag_ai_scientist-<version>.tar.gz` and a `.whl`).

### Check distributions

```bash
twine check dist/*
```

### Store credentials in `~/.pypirc`

Use an API token (recommended). **Username must be exactly `__token__`**; the token string is the password.

Example `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi

[pypi]
username = __token__
password = pypi-YOUR_FULL_TOKEN_HERE
```

Replace `pypi-YOUR_FULL_TOKEN_HERE` with your full token (including the `pypi-` prefix).

Restrict permissions:

```bash
chmod 600 ~/.pypirc
```

Never commit this file or paste tokens into the repository.

### Upload to PyPI

Run from the directory that contains `dist/`:

```bash
twine upload dist/*
```

Or pass an explicit path:

```bash
twine upload /path/to/rag-ai-scientist-installable/dist/*
```

### Verify

- Open [pypi.org/project/rag-ai-scientist](https://pypi.org/project/rag-ai-scientist/) and confirm the new version appears (may take a minute).
- Smoke test: `python -m pip install 'rag-ai-scientist==<version>'`.

### Optional: git tag

```bash
git tag -a vX.Y.Z -m "Release X.Y.Z"
git push origin vX.Y.Z
```

### Optional: Test PyPI

Create a separate token scoped to Test PyPI, add a `[testpypi]` section with `repository = https://test.pypi.org/legacy/`, then:

```bash
twine upload --repository testpypi dist/*
```

Installing from Test PyPI often requires `--extra-index-url https://pypi.org/simple/` for dependencies that are not mirrored there.

### Environment variables instead of `~/.pypirc`

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD='pypi-...'
twine upload dist/*
```

Useful for CI; prefer masked secrets in CI, never echo tokens in logs.
