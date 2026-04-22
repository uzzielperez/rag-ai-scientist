#!/usr/bin/env python3
"""Export indexed chunks for a given paper (by doc_path substring)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    __import__("pysqlite3")
    import sys as _sys
    _sys.modules["sqlite3"] = _sys.modules.pop("pysqlite3")
except Exception:
    pass

CURSOR_DIR = Path(__file__).resolve().parent
RAG_DB = CURSOR_DIR / "rag_db"
os.environ.setdefault("COLLECTION_NAME", "rag-ai-scientist")

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

def main():
    doc_path_substring = sys.argv[1] if len(sys.argv) > 1 else ""
    if not doc_path_substring:
        print("Usage: python export_paper_chunks.py <doc_path_substring>", file=sys.stderr)
        sys.exit(1)

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
        show_progress=False,
    )
    vectorstore = Chroma(
        persist_directory=str(RAG_DB),
        collection_name=os.environ.get("RAG_COLLECTION_NAME", "rag-ai-scientist"),
        embedding_function=embeddings,
    )
    # Retrieve many chunks likely from this paper
    docs = vectorstore.similarity_search(doc_path_substring, k=100)
    by_doc = {}
    for doc in docs:
        path = doc.metadata.get("doc_path") or doc.metadata.get("file") or ""
        if doc_path_substring in path:
            by_doc.setdefault(path, []).append(doc)
    if not by_doc:
        print("No indexed chunks found for that document.", file=sys.stderr)
        sys.exit(2)
    # Sort by chunk_index and output
    for path, chunk_docs in by_doc.items():
        chunk_docs.sort(key=lambda d: d.metadata.get("chunk_index", 0))
        for d in chunk_docs:
            print(d.page_content)
            print("\n---\n")

if __name__ == "__main__":
    main()
