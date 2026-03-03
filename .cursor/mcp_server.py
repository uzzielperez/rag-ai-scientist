#!/usr/bin/env python3
"""Minimal MCP server backed by the local .cursor/rag_db index."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

from mcp.server import Server
from mcp.types import TextContent, Tool
from langchain_huggingface import HuggingFaceEmbeddings

try:
    from langchain_chroma import Chroma
except ImportError:  # pragma: no cover - compatibility fallback
    from langchain_community.vectorstores import Chroma

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    stream=sys.stderr,  # keep stdout clean for MCP protocol
)
logger = logging.getLogger(__name__)

APP = Server("rag-ai-scientist")
DB_DIR = Path(__file__).parent / "rag_db"
VECTORSTORE: Chroma | None = None


def _init_index() -> None:
    global VECTORSTORE

    if not DB_DIR.exists():
        raise FileNotFoundError(
            f"Missing RAG DB directory at {DB_DIR}. Build first with: python .cursor/index_documents.py --force"
        )

    logger.info("Loading Hugging Face embedding model...")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    logger.info("Embedding model ready.")

    logger.info("Opening Chroma vector store...")
    VECTORSTORE = Chroma(
        persist_directory=str(DB_DIR),
        collection_name="rag-ai-scientist",
        embedding_function=embeddings,
    )
    logger.info("Vector store ready.")


def _search(query: str, top_k: int = 5, papers_only: bool = False) -> list[dict]:
    if VECTORSTORE is None:
        raise RuntimeError("RAG DB is not initialized.")

    if papers_only:
        docs_and_scores = VECTORSTORE.similarity_search_with_score(
            query, k=top_k, filter={"source_type": "paper"}
        )
    else:
        docs_and_scores = VECTORSTORE.similarity_search_with_score(query, k=top_k)

    results: list[dict] = []
    for doc, distance in docs_and_scores:
        score = max(0.0, 1.0 - float(distance))
        results.append(
            {
                "score": score,
                "doc_path": doc.metadata.get("doc_path", "unknown"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "text": doc.page_content,
            }
        )
    return results


@APP.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="query_analysis_knowledge",
            description="Search local analysis docs and return an extractive answer with sources.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Question or topic"},
                    "k": {"type": "number", "description": "Top chunks (default: 5)"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="search_papers",
            description="Search only chunks from paths that contain '/papers/'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Paper search topic"},
                    "k": {"type": "number", "description": "Top chunks (default: 5)"},
                },
                "required": ["topic"],
            },
        ),
        Tool(
            name="retrieve_documents",
            description="Return raw matching chunks with scores and file paths.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "k": {"type": "number", "description": "Top chunks (default: 5)"},
                },
                "required": ["query"],
            },
        ),
    ]


@APP.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "query_analysis_knowledge":
            query = arguments["query"]
            k = int(arguments.get("k", 5))
            matches = await asyncio.to_thread(_search, query, k)
            if not matches:
                return [TextContent(type="text", text="No relevant chunks found.")]

            answer_lines = []
            for i, match in enumerate(matches, start=1):
                preview = match["text"].replace("\n", " ")[:260]
                answer_lines.append(
                    f"[{i}] score={match['score']:.4f} file={match['doc_path']} "
                    f"chunk={match['chunk_index']}\n{preview}"
                )
            return [TextContent(type="text", text="\n\n".join(answer_lines))]

        if name == "search_papers":
            topic = arguments["topic"]
            k = int(arguments.get("k", 5))
            matches = await asyncio.to_thread(_search, topic, k, True)
            if not matches:
                return [TextContent(type="text", text="No paper chunks found.")]

            lines = []
            for i, match in enumerate(matches, start=1):
                preview = match["text"].replace("\n", " ")[:260]
                lines.append(
                    f"[{i}] score={match['score']:.4f} file={match['doc_path']}\n{preview}"
                )
            return [TextContent(type="text", text="\n\n".join(lines))]

        if name == "retrieve_documents":
            query = arguments["query"]
            k = int(arguments.get("k", 5))
            matches = await asyncio.to_thread(_search, query, k)
            text = json.dumps(matches, indent=2, ensure_ascii=True)
            return [TextContent(type="text", text=text)]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as exc:
        return [TextContent(type="text", text=f"Tool error: {exc}")]


async def main() -> None:
    from mcp.server.stdio import stdio_server

    logger.info("Initializing MCP server components...")
    await asyncio.to_thread(_init_index)
    logger.info("MCP server ready - waiting for connections...")

    async with stdio_server() as (read_stream, write_stream):
        await APP.run(read_stream, write_stream, APP.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
