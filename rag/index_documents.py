#!/usr/bin/env python3
"""Build a lightweight local RAG vector database from configured references."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def iter_paths(config: dict) -> Iterable[Path]:
    for group in config.get("sources", []):
        for raw_path in group.get("paths", []):
            p = Path(raw_path).expanduser()
            if p.is_file():
                yield p
            elif p.is_dir():
                for ext in group.get("extensions", []):
                    yield from p.rglob(f"*{ext}")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--chunk-size", type=int, default=1800)
    parser.add_argument("--chunk-overlap", type=int, default=250)
    args = parser.parse_args()

    with Path(args.config).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    rows = []
    for path in sorted(set(iter_paths(config))):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for idx, chunk in enumerate(chunk_text(text, args.chunk_size, args.chunk_overlap)):
            rows.append(
                {
                    "doc_path": str(path),
                    "doc_hash": file_hash(path),
                    "chunk_index": idx,
                    "text": chunk,
                }
            )

    if not rows:
        raise SystemExit("No indexable documents found from config.")

    vectorizer = TfidfVectorizer(stop_words="english", max_features=20000)
    matrix = vectorizer.fit_transform([row["text"] for row in rows]).toarray()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "chunks.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    (out_dir / "vectors.json").write_text(json.dumps(matrix.tolist()), encoding="utf-8")
    # Cast vocabulary indices to native int for JSON serialization compatibility.
    serializable_vocab = {token: int(index) for token, index in vectorizer.vocabulary_.items()}
    (out_dir / "vocab.json").write_text(json.dumps(serializable_vocab, sort_keys=True), encoding="utf-8")
    (out_dir / "meta.json").write_text(
        json.dumps(
            {
                "chunks": len(rows),
                "documents": len({row["doc_path"] for row in rows}),
                "chunk_size": args.chunk_size,
                "chunk_overlap": args.chunk_overlap,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(f"Indexed {len(rows)} chunks from {len({row['doc_path'] for row in rows})} documents.")


if __name__ == "__main__":
    main()
