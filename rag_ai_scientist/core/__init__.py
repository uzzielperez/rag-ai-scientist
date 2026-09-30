"""Domain-free core: text extraction, deterministic indexing, lexical search.

Nothing in this package knows about a specific paper, challenge or experiment.
It turns a user-provided corpus into a reproducible index of chunks that carry
resolvable citations, which is the only retrieval primitive the harness needs.
"""

from __future__ import annotations

from rag_ai_scientist.core.retrieval import (
    Chunk,
    RetrievalError,
    SearchHit,
    build_index,
    chunks_hash,
    load_index,
    resolve_citation,
    search,
)

__all__ = [
    "Chunk",
    "RetrievalError",
    "SearchHit",
    "build_index",
    "chunks_hash",
    "load_index",
    "resolve_citation",
    "search",
]
