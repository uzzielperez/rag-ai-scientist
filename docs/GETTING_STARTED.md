# Getting Started

This guide sets up a local research knowledge base and connects it to any AI client that supports MCP over stdio.

## Requirements

- Python 3.10 or newer.
- An MCP-compatible client, such as GitHub Copilot in VS Code, Cursor, Cline, or Claude Desktop.
- Optional: an LLM provider key for generated answers. Without one, retrieval returns source snippets.

## Install

```bash
python3 -m venv ~/.venvs/rag-ai-scientist
source ~/.venvs/rag-ai-scientist/bin/activate
python -m pip install --upgrade pip
python -m pip install rag-ai-scientist
rag-ai-scientist --help
```

## Create and index a project

Create a project directory and put your research material under `references/`:

```bash
mkdir -p ~/my-ai-scientist/references
cd ~/my-ai-scientist
```

Add PDF, Markdown, text, LaTeX, or supported source files to `references/`, then create the index configuration and build the local database:

```bash
rag-ai-scientist init-references --project-root . --references-dir ./references
rag-ai-scientist setup-rag --project-root .
```

The database is written to `.rag-ai-scientist/rag_db` by default. Set `indexing.data_dir` in `configs/references.yaml`, or pass `--data-dir` to `init-references`, to choose another location. Existing projects with `.cursor/rag_db` are detected automatically unless a data directory is explicitly configured.

## Connect an MCP client

The server command is the same across clients; only the configuration file format and location differ. Use an absolute path to the executable from the environment where you installed the package and to the project you indexed.

For VS Code with GitHub Copilot, create `.vscode/mcp.json` in the project:

```json
{
	"servers": {
		"rag-ai-scientist": {
			"type": "stdio",
			"command": "/absolute/path/to/venv/bin/rag-ai-scientist",
			"args": ["mcp", "--project-root", "/absolute/path/to/my-ai-scientist"]
		}
	}
}
```

For clients that use an `mcpServers` object, such as Cursor, Cline, and Claude Desktop, register the same command and arguments in that client's MCP configuration:

```json
{
	"mcpServers": {
		"rag-ai-scientist": {
			"command": "/absolute/path/to/venv/bin/rag-ai-scientist",
			"args": ["mcp", "--project-root", "/absolute/path/to/my-ai-scientist"]
		}
	}
}
```

Restart or reload the client's MCP servers after saving the configuration. The server provides `query_analysis_knowledge`, `search_papers`, `retrieve_documents`, and `get_skill` tools.

## Optional answer generation

Add provider settings to `.rag-ai-scientist/.env` if you want LLM-generated answers. For example, `GROQ_API_KEY` enables the optional Groq backend. Keep credentials out of source control. Retrieval and packaged skills do not require a provider key.

## Refresh the index

Add or update files under `references/`, then rebuild:

```bash
rag-ai-scientist setup-rag --project-root . --force
```
