#!/usr/bin/env python3
"""General MCP server for local RAG + project skills."""

from __future__ import annotations

# sqlite workaround for lxplus-like environments
try:  # pragma: no cover
    __import__("pysqlite3")
    import sys

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except Exception:  # pragma: no cover
    pass

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server import Server
from mcp.types import Resource, TextContent, Tool
from langchain_huggingface import HuggingFaceEmbeddings

try:
    from langchain_chroma import Chroma
except ImportError:  # pragma: no cover
    from langchain_community.vectorstores import Chroma

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

CURSOR_DIR = Path(__file__).parent
load_dotenv(CURSOR_DIR / ".env")

SKILLS_DIR = CURSOR_DIR / "skills"
VECTOR_DB = CURSOR_DIR / "rag_db"
COLLECTION_NAME = os.environ.get("RAG_COLLECTION_NAME", "rag-ai-scientist")

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
    show_progress=False,
)
vectorstore = Chroma(
    persist_directory=str(VECTOR_DB),
    collection_name=COLLECTION_NAME,
    embedding_function=embeddings,
)

llm = None
groq_key = os.environ.get("GROQ_API_KEY", "").strip()
if groq_key and groq_key != "gsk_your-key-here":
    try:
        from langchain_groq import ChatGroq

        llm = ChatGroq(api_key=groq_key, temperature=0, model="llama-3.3-70b-versatile")
        logger.info("Groq client ready.")
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not initialize Groq client: %s", exc)
else:
    logger.info("GROQ_API_KEY not set. query_analysis_knowledge will return extractive results.")

app = Server("rag-ai-scientist")


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
            description="Return skill instructions from .cursor/skills/<skill>/.",
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
            docs = await asyncio.to_thread(vectorstore.similarity_search, query, k)
            if not docs:
                return [TextContent(type="text", text="No relevant documents found.")]
            if llm is None:
                return [TextContent(type="text", text=_format_extractive(docs, "Top matches"))]

            context = "\n\n".join(
                [f"[From {doc.metadata.get('file', 'unknown')}]\n{doc.page_content}" for doc in docs]
            )
            prompt = (
                f"Answer the question based only on this context.\n\nQuestion: {query}\n\n"
                f"Context:\n{context}\n\n"
                "If the answer is not in context, say so clearly."
            )
            response = await asyncio.to_thread(llm.invoke, prompt)
            sources = list({doc.metadata.get("file", "unknown") for doc in docs[:3]})
            return [TextContent(type="text", text=f"{response.content}\n\nSources: {', '.join(sources)}")]

        if name == "search_papers":
            topic = arguments["topic"]
            k = int(arguments.get("k", 5))
            docs = await asyncio.to_thread(
                vectorstore.similarity_search, topic, k=k, filter={"source_type": "paper"}
            )
            if not docs:
                docs = await asyncio.to_thread(vectorstore.similarity_search, topic, min(3, k))
            return [TextContent(type="text", text=_format_extractive(docs, "Paper matches"))]

        if name == "retrieve_documents":
            query = arguments["query"]
            k = int(arguments.get("k", 5))
            docs = await asyncio.to_thread(vectorstore.similarity_search_with_score, query, k)
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
            skill_path = SKILLS_DIR / skill / ("SKILL.md" if not step else f"{step}.md")
            if not skill_path.exists():
                return [TextContent(type="text", text=f"Skill file not found: {skill_path}")]
            return [TextContent(type="text", text=skill_path.read_text(encoding="utf-8"))]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as exc:
        logger.exception("Tool error")
        return [TextContent(type="text", text=f"Tool error: {exc}")]


@app.list_resources()
async def list_resources() -> list[Resource]:
    if not SKILLS_DIR.exists():
        return []
    resources: list[Resource] = []
    for md_file in sorted(SKILLS_DIR.rglob("*.md")):
        rel = md_file.relative_to(SKILLS_DIR)
        resources.append(
            Resource(
                uri=f"skill://{rel.parent}/{rel.stem}",
                name=str(rel),
                description=f"Skill instructions: {rel}",
                mimeType="text/markdown",
            )
        )
    return resources


@app.read_resource()
async def read_resource(uri: str) -> str:
    rel = Path(uri.replace("skill://", ""))
    target = SKILLS_DIR / rel.parent / f"{rel.name}.md"
    if not target.exists():
        raise FileNotFoundError(f"Resource not found: {uri}")
    return target.read_text(encoding="utf-8")


async def main() -> None:
    from mcp.server.stdio import stdio_server

    logger.info("MCP server ready - waiting for connections...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
