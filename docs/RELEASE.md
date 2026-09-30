# Releasing to PyPI

Version is declared twice and must match: `pyproject.toml` (`[project] version`)
and `rag_ai_scientist/__init__.py` (`__version__`).

## 1. Gate the tree

```bash
cd ~/Desktop/rag-ai-scientist
source .venv/bin/activate
python -m pytest tests/ -q          # expect: 32 passed
ras run  --project-root .           # expect: [ALL GATES PASSED]
ras eval --project-root .           # expect: tier1 1.0  tier23 1.0  citations_valid True
```

## 2. Build

```bash
pip install -U build twine
rm -rf dist build rag_ai_scientist.egg-info   # dist/ holds older 0.1.x wheels
python -m build
twine check dist/*
```

`rm -rf dist` matters: `twine upload dist/*` with old artifacts in place fails
with `400 File already exists`.

## 3. Sanity-check the wheel

```bash
python -m zipfile -l dist/rag_ai_scientist-0.2.0-py3-none-any.whl \
  | grep -E 'ras_cli|harness/|skills/_template'
```

The wheel carries `rag_ai_scientist/` plus `skills/**/*.md`; `docs/`, `tests/`
and `evals/golden/` are **not** packaged, so a `pip install` user gets the CLI
but not the LHCb corpus or golden set. Those live in the repository.

## 4. Upload

Create a token at <https://pypi.org/manage/account/token/> (scope "Entire
account" if you publish more than this project). With 2FA on your account, an
API token is required — username/password uploads are refused.

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
twine upload dist/rag_ai_scientist-0.2.0-py3-none-any.whl \
             dist/rag_ai_scientist-0.2.0.tar.gz
```

Or avoid the env var entirely with keyring (`pip install keyring`, then store
the token under service `pypi` for user `__token__`).

To dry-run against TestPyPI first (needs a separate test.pypi.org account):

```bash
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

## 5. Verify from a clean environment

```bash
python -m venv /tmp/verify-release && source /tmp/verify-release/bin/activate
pip install -U rag-ai-scientist==0.2.0
ras --help && python -c "import rag_ai_scientist as r; print(r.__version__)"
```

## 6. Tag it

```bash
git add -A && git commit -m "Release 0.2.0"
git tag v0.2.0 && git push && git push --tags
```

## Notes

- PyPI never lets a version number be reused. A bad upload means skipping to
  the next number, not re-uploading.
- Publishing ships the source: this tree is AGPL-3.0-or-later with a
  proprietary dual-license offer, so the uploaded sdist is publicly readable.
- `license = { text = "AGPL-3.0-or-later" }` is the deprecated form; newer
  setuptools warns about it and PEP 639 wants `license = "AGPL-3.0-or-later"`
  plus `license-files`. Harmless today, worth migrating when convenient.
- `0.2.0` rather than `0.1.11`: removing the `whest` profile and the
  `whest-estimation-challenge` / `challenge-harness` skills is a breaking change.
