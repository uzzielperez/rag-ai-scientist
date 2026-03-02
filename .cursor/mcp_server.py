#!/usr/bin/env python3
"""Minimal MCP server backed by the local .cursor/rag_db index."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import numpy as np
from mcp.server import Server
from mcp.types import TextContent, Tool
from sklearn.feature_extraction.text import TfidfVectorizer

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    stream=sys.stderr,  # keep stdout clean for MCP protocol
)
logger = logging.getLogger(__name__)

APP = Server("rag-ai-scientist")
DB_DIR = Path(__file__).parent / "rag_db"

CHUNKS: list[dict] = []
VECTORS: np.ndarray | None = None
VOCAB: dict[str, int] = {}


def _load_db() -> tuple[list[dict], np.ndarray, dict]:
    chunks_path = DB_DIR / "chunks.jsonl"
    vectors_path = DB_DIR / "vectors.json"
    vocab_path = DB_DIR / "vocab.json"

    if not (chunks_path.exists() and vectors_path.exists() and vocab_path.exists()):
        raise FileNotFoundError(
            "Missing RAG DB files. Build first with: ./scripts/build_rag_db.sh"
        )

    chunks = [
        json.loads(line)
        for line in chunks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    vectors = np.array(json.loads(vectors_path.read_text(encoding="utf-8")))
    vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
    return chunks, vectors, vocab


def _init_index() -> None:
    global CHUNKS, VECTORS, VOCAB
    logger.info("Loading RAG database into memory...")
    CHUNKS, VECTORS, VOCAB = _load_db()
    logger.info(
        "RAG database loaded: %d chunks, vector shape=%s",
        len(CHUNKS),
        tuple(VECTORS.shape),
    )


def _cosine_similarity(query_vec: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    q_norm = np.linalg.norm(query_vec) + 1e-12
    v_norm = np.linalg.norm(vectors, axis=1) + 1e-12
    return (vectors @ query_vec) / (v_norm * q_norm)


def _search(query: str, top_k: int = 5) -> list[dict]:
    if VECTORS is None or not CHUNKS or not VOCAB:
        raise RuntimeError("RAG DB is not initialized.")

    vectorizer = TfidfVectorizer(vocabulary=VOCAB)
    query_vec = vectorizer.fit_transform([query]).toarray()[0]
    sims = _cosine_similarity(query_vec, VECTORS)
    top_indices = np.argsort(sims)[::-1][:top_k]

    results: list[dict] = []
    for idx in top_indices:
        row = CHUNKS[int(idx)]
        results.append(
            {
                "score": float(sims[idx]),
                "doc_path": row.get("doc_path", "unknown"),
                "chunk_index": row.get("chunk_index", -1),
                "text": row.get("text", ""),
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
            matches = await asyncio.to_thread(_search, topic, max(k * 3, 10))
            paper_matches = [m for m in matches if "/papers/" in m["doc_path"]][:k]
            if not paper_matches:
                return [TextContent(type="text", text="No paper chunks found.")]

            lines = []
            for i, match in enumerate(paper_matches, start=1):
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
