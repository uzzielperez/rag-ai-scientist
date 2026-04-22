from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

try:  # sqlite workaround for lxplus-like environments
    __import__("pysqlite3")
    import sys as _sys

    _sys.modules["sqlite3"] = _sys.modules.pop("pysqlite3")
except Exception:  # pragma: no cover
    pass

import yaml
from dotenv import load_dotenv
from mcp.server import Server
from mcp.types import Resource, TextContent, Tool
from langchain_huggingface import HuggingFaceEmbeddings

try:
    from langchain_chroma import Chroma
except ImportError:  # pragma: no cover
    from langchain_community.vectorstores import Chroma


logger = logging.getLogger(__name__)


def _collection_name(project_root: Path) -> str:
    env_name = os.environ.get("RAG_COLLECTION_NAME", "").strip()
    if env_name:
        return env_name

    cfg = project_root / "configs" / "references.yaml"
    if cfg.exists():
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        return str(data.get("indexing", {}).get("collection_name", "rag-ai-scientist"))
    return "rag-ai-scientist"


def _skills_root(project_root: Path) -> Path:
    project_skills = project_root / ".cursor" / "skills"
    if project_skills.exists():
        return project_skills

    # Fallback to skills shipped in the installed module.
    return Path(__file__).resolve().parent / "skills"


def _load_skill_text(skills_root: Path, skill: str, step: str | None) -> str:
    path = skills_root / skill / ("SKILL.md" if not step else f"{step}.md")
    if not path.exists():
        raise FileNotFoundError(f"Skill file not found: {path}")
    return path.read_text(encoding="utf-8")


def _format_extractive(docs: list, title: str = "Results") -> str:
    if not docs:
        return "No relevant documents found."
    lines = [f"**{title}:**", ""]
    for idx, doc in enumerate(docs, 1):
        source = doc.metadata.get("file", doc.metadata.get("doc_path", "unknown"))
        snippet = doc.page_content[:400].replace("\n", " ")
        lines.append(f"{idx}. {source}")
        lines.append(snippet)
        lines.append("")
    return "\n".join(lines).strip()


def _try_init_llm() -> object | None:
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key or groq_key == "gsk_your-key-here":
        return None
    from langchain_groq import ChatGroq

    return ChatGroq(api_key=groq_key, temperature=0, model="llama-3.3-70b-versatile")


def run_mcp(*, project_root: Path) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
        stream=sys.stderr,
    )

    project_root = project_root.resolve()
    cursor_dir = project_root / ".cursor"
    vector_db_dir = cursor_dir / "rag_db"
    if not vector_db_dir.exists():
        raise SystemExit(
            f"RAG DB not found at {vector_db_dir}. Run `rag-ai-scientist setup-rag` first."
        )

    load_dotenv(cursor_dir / ".env")

    skills_root = _skills_root(project_root)
    collection_name = _collection_name(project_root)

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
        show_progress=False,
    )
    vectorstore = Chroma(
        persist_directory=str(vector_db_dir),
        collection_name=collection_name,
        embedding_function=embeddings,
    )

    llm = _try_init_llm()

    app = Server("rag-ai-scientist")

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="query_analysis_knowledge",
                description=(
                    "Search indexed knowledge and answer using either an LLM (if configured) "
                    "or an extractive summary with sources."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "k": {"type": "number"}},
                    "required": ["query"],
                },
            ),
            Tool(
                name="search_papers",
                description="Search chunks tagged as source_type=paper.",
                inputSchema={
                    "type": "object",
                    "properties": {"topic": {"type": "string"}, "k": {"type": "number"}},
                    "required": ["topic"],
                },
            ),
            Tool(
                name="retrieve_documents",
                description="Return raw nearest-neighbor chunks as JSON.",
                inputSchema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "k": {"type": "number"}},
                    "required": ["query"],
                },
            ),
            Tool(
                name="get_skill",
                description="Return skill instructions from packaged defaults or project overrides.",
                inputSchema={
                    "type": "object",
                    "properties": {"skill": {"type": "string"}, "step": {"type": "string"}},
                    "required": ["skill"],
                },
            ),
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            if name == "query_analysis_knowledge":
                query = arguments["query"]
                k = int(arguments.get("k", 5))
                docs = await asyncio.to_thread(vectorstore.similarity_search, query, k=k)
                if not docs:
                    return [TextContent(type="text", text="No relevant documents found.")]

                if llm is None:
                    return [TextContent(type="text", text=_format_extractive(docs, "Top matches"))]

                context = "\n\n".join(
                    [f"[From {doc.metadata.get('file', 'unknown')}]\n{doc.page_content}" for doc in docs]
                )
                prompt = (
                    "Answer the question based only on this context.\n\n"
                    f"Question: {query}\n\n"
                    f"Context:\n{context}\n\n"
                    "If the answer is not in context, say so clearly."
                )
                response = await asyncio.to_thread(llm.invoke, prompt)
                sources = list({doc.metadata.get("file", "unknown") for doc in docs[:3]})
                return [
                    TextContent(
                        type="text",
                        text=f"{response.content}\n\nSources: {', '.join(sources)}",
                    )
                ]

            if name == "search_papers":
                topic = arguments["topic"]
                k = int(arguments.get("k", 5))
                docs = await asyncio.to_thread(
                    vectorstore.similarity_search, topic, k=k, filter={"source_type": "paper"}
                )
                if not docs:
                    docs = await asyncio.to_thread(vectorstore.similarity_search, topic, k=min(3, k))
                return [TextContent(type="text", text=_format_extractive(docs, "Paper matches"))]

            if name == "retrieve_documents":
                query = arguments["query"]
                k = int(arguments.get("k", 5))
                docs = await asyncio.to_thread(vectorstore.similarity_search_with_score, query, k=k)
                payload = []
                for doc, score in docs:
                    payload.append(
                        {
                            "score": float(score),
                            "metadata": doc.metadata,
                            "text": doc.page_content,
                        }
                    )
                return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=True))]

            if name == "get_skill":
                skill = arguments["skill"]
                step = arguments.get("step")
                content = _load_skill_text(skills_root, skill=skill, step=step)
                return [TextContent(type="text", text=content)]

            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as exc:
            logger.exception("Tool error")
            return [TextContent(type="text", text=f"Tool error: {exc}")]

    @app.list_resources()
    async def list_resources() -> list[Resource]:
        resources: list[Resource] = []
        if not skills_root.exists():
            return resources
        for md_file in sorted(skills_root.rglob("*.md")):
            rel = md_file.relative_to(skills_root)
            uri = f"skill://{rel.parent}/{rel.stem}"
            resources.append(
                Resource(
                    uri=uri,
                    name=str(rel),
                    description=f"Skill instructions: {rel}",
                    mimeType="text/markdown",
                )
            )
        return resources

    @app.read_resource()
    async def read_resource(uri: str) -> str:
        rel = Path(uri.replace("skill://", ""))
        target = skills_root / rel.parent / f"{rel.name}.md"
        if not target.exists():
            raise FileNotFoundError(f"Resource not found: {uri}")
        return target.read_text(encoding="utf-8")

    async def main_async() -> None:
        from mcp.server.stdio import stdio_server

        logger.info("✓ MCP server ready — waiting for connections...")
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    asyncio.run(main_async())


def main() -> None:
    parser = argparse.ArgumentParser(description="Start rag-ai-scientist MCP server (stdio).")
    parser.add_argument("--project-root", default=".", help="Target analysis repo root.")
    args = parser.parse_args()
    run_mcp(project_root=Path(args.project_root))


if __name__ == "__main__":
    main()

