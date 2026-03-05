# Contributing

Thanks for contributing to `rag-ai-scientist`.

## Contribution terms

By submitting a pull request, you agree that:

1. You have the right to submit the contribution.
2. Your contribution is licensed under AGPL-3.0-or-later.
3. You grant project maintainers the right to relicense your contribution as
   part of the project's dual-licensing model (open-source AGPL + commercial).

If these terms do not work for your organization, open an issue before contributing.

## Development quickstart

```bash
python3 -m venv ~/mcp_env
source ~/mcp_env/bin/activate
python -m pip install --upgrade pip
bash .cursor/setup_rag.sh
```

## Pull request checklist

- Keep changes script-driven and reproducible.
- Update docs/configs with code changes.
- Do not commit secrets (`.env`, private keys, tokens).
- Validate local indexing when touching RAG/MCP files:
  - `python .cursor/index_documents.py --force`
  - `python .cursor/visualize_rag.py --top-n 200`
