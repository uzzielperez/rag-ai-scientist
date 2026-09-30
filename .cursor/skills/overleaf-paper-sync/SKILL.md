---
name: overleaf-paper-sync
description: Sync LaTeX bundles to Overleaf via Git integration and inspect projects through rag-ai-scientist Overleaf MCP tools (companion to OVERLEAF_PROJECTS_CONFIG / Node Overleaf MCP). Use when pushing paper drafts, reading Overleaf files, or documenting a challenge run.
---

# Overleaf paper sync (built into rag-ai-scientist)

## Two layers

| Layer | What | How |
|-------|------|-----|
| **Inspect / edit in any MCP client** | list/read/write sections | vendored Node server below *or* Python tools |
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
# Install the vendored Node MCP server (ships in the wheel since 0.1.10):
rag-ai-scientist overleaf install-node-server --dest ~/.config/overleaf-mcp
```

## MCP tools (inside rag-ai-scientist)

```json
{ "name": "overleaf_list_projects" }
{ "name": "overleaf_status", "arguments": { "project": "default" } }
{ "name": "overleaf_list_files", "arguments": { "project": "default" } }
{ "name": "overleaf_read_file", "arguments": { "project": "default", "path": "main.tex" } }
{ "name": "overleaf_sync_bundle", "arguments": { "bundle_dir": "output/overleaf_bundle", "dry_run": true } }
```

## Cursor companion (this custom Overleaf MCP)

Install it straight from the wheel (no separate download), then point any
MCP client at the **local** server:

```json
{
  "mcpServers": {
    "overleaf": {
      "command": "node",
      "args": ["/Users/YOU/.config/overleaf-mcp/overleaf-mcp-server.js"],
      "env": {
        "OVERLEAF_PROJECTS_CONFIG": "/Users/YOU/.config/overleaf-mcp/projects.json"
      }
    }
  }
}
```

Tools: `list_files`, `read_file`, `write_file`, `get_sections`, `get_section_content`,
`status_summary`, `list_projects`, `delete_file`, `commit_changes`, `push_changes`,
`git_status`, `upload_file`.

`projects.json` lives next to the server and includes keys like `default`, `my-notes`, …

## Safety

- Do not paste git tokens into chat, commits, or skills.
- Prefer `--dry-run` before the first push.
- Treat `.overleaf_mirror/` as local cache (gitignore it).

## Challenge loop hook

A harness `document` stage can point here: after a run, sync a short notes bundle or paper draft to Overleaf with `overleaf_sync_bundle`.
