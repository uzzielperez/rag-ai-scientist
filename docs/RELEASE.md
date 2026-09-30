# Releasing to PyPI

Version is declared twice and must match: `pyproject.toml` (`[project] version`)
and `rag_ai_scientist/__init__.py` (`__version__`).

## 1. Gate the tree

```bash
cd ~/Desktop/rag-ai-scientist
source .venv/bin/activate
python -m pytest tests/ -q          # expect: 37 passed
ras demo --fast                     # expect: exit 0, ALL GATES PASSED inside the show
ras run  --project-root .           # expect: [ALL GATES PASSED]
ras eval --project-root .           # expect: tier1 1.0  tier23 1.0  citations_valid True
```

## 2. Build

```bash
source .venv/bin/activate        # build and twine live in the project venv
pip install -U build twine
rm -rf dist build rag_ai_scientist.egg-info   # dist/ holds older 0.1.x wheels
python -m build
twine check dist/*
```

`rm -rf dist` matters: `twine upload dist/*` with old artifacts in place fails
with `400 File already exists`.

`build` and `twine` are venv binaries, not system ones: in a shell where the
venv was never activated, plain `twine` is `command not found`. Either activate,
or skip activation entirely and address the binaries by path — `.venv/bin/twine
check dist/*`, `.venv/bin/python -m build` — which works from any directory.

## 3. Sanity-check the wheel

```bash
python -m zipfile -l dist/rag_ai_scientist-0.2.1-py3-none-any.whl \
  | grep -E 'ras_cli|demo|harness/|skills/harness-tutorial|skills/_template'
```

The wheel carries `rag_ai_scientist/` plus `skills/**/*.md` (including
`harness-tutorial`) and the packaged `demo.py` behind `ras demo`. `docs/`,
`tests/` and `evals/golden/` are **not** in the wheel, so a `pip install` user
gets the CLI, the demo and the tutorial skill, but not the walkthrough Markdown
or the LHCb corpus — those come from the sdist or the repository.

`MANIFEST.in` puts `docs/**/*.md` and `scripts/demo.py` into the **sdist** only.
Keep it that way: never glob PDFs into an sdist.

## 4. Upload

Create a token at <https://pypi.org/manage/account/token/> (scope "Entire
account" if you publish more than this project). With 2FA on your account, an
API token is required — username/password uploads are refused.

```bash
cd ~/Desktop/rag-ai-scientist      # project root, where dist/ lives
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
.venv/bin/twine upload dist/rag_ai_scientist-0.2.1-py3-none-any.whl \
                       dist/rag_ai_scientist-0.2.1.tar.gz
```

Or avoid the env var entirely with keyring (`pip install keyring`, then store
the token under service `pypi` for user `__token__`).

To dry-run against TestPyPI first (needs a separate test.pypi.org account):

```bash
.venv/bin/twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

## 5. Verify from a clean environment

```bash
python -m venv /tmp/verify-release && source /tmp/verify-release/bin/activate
pip install -U rag-ai-scientist==0.2.1
ras --help && python -c "import rag_ai_scientist as r; print(r.__version__)"
ras demo --fast          # the demo must work with no repository present
```

## 6. Tag it

```bash
git add -A && git commit -m "Release 0.2.1"
git tag v0.2.1 && git push && git push --tags
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
- `0.2.0` is frozen on PyPI (uploaded 2026-09-30) and its README/project page
  cannot be edited; `0.2.1` is the first release that ships the demo as
  `ras demo` and the tutorial as the packaged `harness-tutorial` skill.
  If a release ever ships broken, the fix is a new number — or
  yank the files in the PyPI UI so pip skips them while they stay downloadable.
