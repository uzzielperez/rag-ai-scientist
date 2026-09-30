# Vendored Node Overleaf MCP server

Source: the working copy from `~/.config/overleaf-mcp/` (clean header,
`OVERLEAF_GIT_TOKEN` / `OVERLEAF_PROJECT_ID` env fallback kept).

Files:
- `overleaf-mcp-server.js` — stdio MCP server (list/read/write/sections/commit/push/upload)
- `overleaf-git-client.js` — git.overleaf.com mirror client (required by the server)
- `package.json` — needs `@modelcontextprotocol/sdk ^1.12.1` (`npm install` after install)

Install via pip package:

```bash
rag-ai-scientist overleaf install-node-server --dest ~/.config/overleaf-mcp
npm install --prefix ~/.config/overleaf-mcp
```

Credentials are never bundled: set `OVERLEAF_PROJECTS_CONFIG` (JSON) or
`OVERLEAF_PROJECT_ID` + `OVERLEAF_GIT_TOKEN`.
