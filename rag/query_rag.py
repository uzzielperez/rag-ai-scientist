#!/usr/bin/env python3
"""Query the local RAG vector database built by index_documents.py."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def cosine_similarity(query_vec: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    q_norm = np.linalg.norm(query_vec) + 1e-12
    v_norm = np.linalg.norm(vectors, axis=1) + 1e-12
    return (vectors @ query_vec) / (v_norm * q_norm)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-dir", default=".cursor/rag_db")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    db_dir = Path(args.db_dir)
    chunks = [json.loads(line) for line in (db_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line]
    vectors = np.array(json.loads((db_dir / "vectors.json").read_text(encoding="utf-8")))
    vocab = json.loads((db_dir / "vocab.json").read_text(encoding="utf-8"))

    vectorizer = TfidfVectorizer(vocabulary=vocab)
    query_vec = vectorizer.fit_transform([args.query]).toarray()[0]
    sims = cosine_similarity(query_vec, vectors)
    top_indices = np.argsort(sims)[::-1][: args.top_k]

    for rank, idx in enumerate(top_indices, start=1):
        item = chunks[int(idx)]
        preview = item["text"].replace("\n", " ")[:200]
        print(f"[{rank}] score={sims[idx]:.4f} file={item['doc_path']} chunk={item['chunk_index']}")
        print(f"    {preview}")


if __name__ == "__main__":
    main()
