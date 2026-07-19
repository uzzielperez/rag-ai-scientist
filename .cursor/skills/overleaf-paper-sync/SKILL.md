---
name: overleaf-paper-sync
description: Sync LaTeX bundles to Overleaf via Git integration and inspect projects through rag-ai-scientist Overleaf MCP tools (companion to OVERLEAF_PROJECTS_CONFIG / Node Overleaf MCP). Use when pushing paper drafts, reading Overleaf files, or documenting a challenge run.
---

# Overleaf paper sync (built into rag-ai-scientist)

## Two layers

| Layer | What | How |
|-------|------|-----|
| **Inspect / edit in Cursor** | list/read/write sections | Node `@mjyoo2/overleaf-mcp` *or* Python tools below |
| **Push rendered bundles** | copy `main.tex` + figures → Overleaf | `rag-ai-scientist overleaf sync` / MCP `overleaf_sync_bundle` |

Credentials: **never commit tokens**. Prefer env vars.

## Configuration

Same JSON the Cursor Overleaf MCP uses:

```bash
export OVERLEAF_PROJECTS_CONFIG="$HOME/.config/overleaf-mcp/projects.json"
```

Or single-project:

```bash
export OVERLEAF_PROJECT_ID="<id>"
export OVERLEAF_GIT_TOKEN="<git-integration-token>"
```

Optional YAML (higgs-style): `configs/overleaf.local.yaml` with `project_id` + `git_token`.

## CLI

```bash
rag-ai-scientist overleaf list-projects
rag-ai-scientist overleaf status --project-root . --project default
rag-ai-scientist overleaf sync --project-root . --bundle-dir output/overleaf_bundle --project default
rag-ai-scientist overleaf sync --bundle-dir output/overleaf_bundle --dry-run
```

## MCP tools (inside rag-ai-scientist)

```json
{ "name": "overleaf_list_projects" }
{ "name": "overleaf_status", "arguments": { "project": "default" } }
{ "name": "overleaf_list_files", "arguments": { "project": "default" } }
{ "name": "overleaf_read_file", "arguments": { "project": "default", "path": "main.tex" } }
{ "name": "overleaf_sync_bundle", "arguments": { "bundle_dir": "output/overleaf_bundle", "dry_run": true } }
```

## Cursor companion (Node MCP)

Keep the existing Overleaf MCP entry for rich section write tools:

```json
{
  "mcpServers": {
    "overleaf": {
      "command": "npx",
      "args": ["-y", "@mjyoo2/overleaf-mcp"],
      "env": {
        "OVERLEAF_PROJECTS_CONFIG": "/Users/YOU/.config/overleaf-mcp/projects.json"
      }
    },
    "rag-ai-scientist": {
      "command": "rag-ai-scientist",
      "args": ["mcp", "--project-root", "/absolute/path/to/project"]
    }
  }
}
```

If the Node server fails discovery, Python tools above still work for list/read/sync.

## Safety

- Do not paste git tokens into chat, commits, or skills.
- Prefer `--dry-run` before the first push.
- Treat `.overleaf_mirror/` as local cache (gitignore it).

## Challenge loop hook

The `whest` harness `document` stage points here: after scoring, sync a short notes bundle or paper draft to Overleaf with `overleaf_sync_bundle`.
