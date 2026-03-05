#!/usr/bin/env python3
"""Ingest curated notes into the local Chroma RAG store."""

from __future__ import annotations

# sqlite workaround for lxplus-like environments
try:  # pragma: no cover
    __import__("pysqlite3")
    import sys

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except Exception:  # pragma: no cover
    pass

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

try:
    from langchain_chroma import Chroma
except ImportError:  # pragma: no cover
    from langchain_community.vectorstores import Chroma

CURSOR_DIR = Path(__file__).parent
VECTOR_DB = CURSOR_DIR / "rag_db"
INGEST_LOG = VECTOR_DB / "ingest_log.jsonl"
COLLECTION_NAME = os.environ.get("RAG_COLLECTION_NAME", "rag-ai-scientist")

load_dotenv(CURSOR_DIR / ".env")


def get_vectorstore() -> Chroma:
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
        show_progress=False,
    )
    return Chroma(
        persist_directory=str(VECTOR_DB),
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
    )


def ingest(title: str, content: str, tags: list[str]) -> None:
    vectorstore = get_vectorstore()
    ingested_at = datetime.now(timezone.utc).isoformat()
    doc = Document(
        page_content=content,
        metadata={
            "file": title,
            "source_type": "curated_note",
            "tags": ",".join(tags),
            "ingested_at": ingested_at,
        },
    )
    ids = vectorstore.add_documents([doc])
    log_entry = {
        "id": ids[0],
        "title": title,
        "tags": tags,
        "length": len(content),
        "ingested_at": ingested_at,
        "preview": content[:120].replace("\n", " "),
    }
    INGEST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with INGEST_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(log_entry, ensure_ascii=True) + "\n")
    print(f"Ingested '{title}' as {ids[0]} into '{COLLECTION_NAME}'.")
    print(f"Log: {INGEST_LOG}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest short curated notes into local RAG.")
    parser.add_argument("--title", required=True, help="Short title for this note")
    parser.add_argument("--content", help="Inline content")
    parser.add_argument("--file", help="Path to a .txt/.md file")
    parser.add_argument("--interactive", action="store_true", help="Read multiline content from stdin")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    args = parser.parse_args()

    if args.file:
        content = Path(args.file).read_text(encoding="utf-8").strip()
    elif args.content:
        content = args.content.strip()
    elif args.interactive:
        print("Paste content, then Ctrl-D:")
        content = sys.stdin.read().strip()
    else:
        parser.error("Provide one of: --content, --file, --interactive")
        return

    if not content:
        parser.error("Content is empty.")
        return

    tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
    ingest(title=args.title, content=content, tags=tags)


if __name__ == "__main__":
    main()
