"""Deterministic lexical index over corpus chunks.

The v1 default store is a JSONL file of chunks plus a BM25 scorer implemented
with the standard library. It was chosen because the harness must be able to
prove three properties on any machine, offline and with no model download:

1. indexing the same corpus twice yields byte-identical ``chunks.jsonl``;
2. every search result carries a citation that resolves to ``(file, page,
   chunk_id, hash)`` of a file that exists;
3. a run is reproducible from its manifest alone.

Embedding-backed stores can be added as providers later without changing the
harness loop, because the loop only consumes ``search`` and
``resolve_citation``.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from rag_ai_scientist.core.text import (
    chunk_text,
    extract_pages,
    file_hash,
    iter_corpus_files,
    normalize_text,
    sha256_text,
    tokenize,
)

INDEX_SCHEMA_VERSION = 1
CHUNKS_FILENAME = "chunks.jsonl"
META_FILENAME = "index.json"
_IDF_DF_RATIO_LIMIT = 0.5
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n")


class RetrievalError(RuntimeError):
    """Raised when an index cannot be built, loaded or trusted."""


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_path: str
    file: str
    page: int
    chunk_index: int
    text: str
    doc_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_path": self.doc_path,
            "file": self.file,
            "page": self.page,
            "chunk_index": self.chunk_index,
            "doc_hash": self.doc_hash,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chunk":
        return cls(
            chunk_id=str(data["chunk_id"]),
            doc_path=str(data["doc_path"]),
            file=str(data["file"]),
            page=int(data["page"]),
            chunk_index=int(data["chunk_index"]),
            doc_hash=str(data.get("doc_hash", "")),
            text=str(data["text"]),
        )


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float
    matched_terms: tuple[str, ...]

    def citation(self) -> dict[str, Any]:
        return {
            "file": self.chunk.file,
            "page": self.chunk.page,
            "chunk_id": self.chunk.chunk_id,
            "hash": self.chunk.doc_hash,
            "score": round(self.score, 3),
        }


def chunks_hash(chunks_path: Path) -> str:
    """SHA-256 of the chunk file, used as the index fingerprint."""
    return file_hash(chunks_path)


def _chunk_id(doc_hash: str, page: int, index_in_page: int, text: str) -> str:
    return sha256_text(f"{doc_hash}:{page}:{index_in_page}:{text}")[:16]


class LexicalIndex:
    """An immutable BM25 index over a corpus."""

    def __init__(self, chunks: list[Chunk], meta: dict[str, Any], *, index_dir: Path | None = None) -> None:
        self.chunks = chunks
        self.meta = meta
        self.index_dir = index_dir
        self.by_id: dict[str, Chunk] = {chunk.chunk_id: chunk for chunk in chunks}
        self._lengths = [max(1, len(tokenize(chunk.text))) for chunk in chunks]
        self._avgdl = (sum(self._lengths) / len(self._lengths)) if self._lengths else 1.0

    def __len__(self) -> int:
        return len(self.chunks)

    # -- construction ----------------------------------------------------
    @classmethod
    def build(
        cls,
        *,
        project_root: Path,
        paths: list[str],
        index_dir: Path,
        extensions: list[str],
        chunk_chars: int,
        chunk_overlap: int,
    ) -> "LexicalIndex":
        files = iter_corpus_files(project_root, paths, extensions)
        if not files:
            raise RetrievalError(
                f"No corpus files matched {paths} under {project_root}. "
                f"Supported extensions: {', '.join(sorted(extensions))}"
            )
        chunks: list[Chunk] = []
        docs: list[dict[str, Any]] = []
        for path in files:
            doc_hash = file_hash(path)
            try:
                doc_path = str(path.resolve().relative_to(project_root))
            except ValueError:
                doc_path = str(path.resolve())
            pages = extract_pages(path)
            if not pages:
                continue
            raw_chunks = chunk_text(pages, chunk_chars=chunk_chars, chunk_overlap=chunk_overlap)
            per_page: dict[int, int] = {}
            chars = 0
            for raw in raw_chunks:
                page = int(raw["page"])
                index_in_page = per_page.get(page, 0)
                per_page[page] = index_in_page + 1
                text = raw["text"]
                chars += len(text)
                chunks.append(
                    Chunk(
                        chunk_id=_chunk_id(doc_hash, page, index_in_page, text),
                        doc_path=doc_path,
                        file=path.name,
                        page=page,
                        chunk_index=index_in_page,
                        text=text,
                        doc_hash=doc_hash,
                    )
                )
            docs.append(
                {
                    "doc_path": doc_path,
                    "file": path.name,
                    "doc_hash": doc_hash,
                    "pages": len(pages),
                    "chunks": sum(per_page.values()),
                    "chars": chars,
                }
            )
        chunks.sort(key=lambda c: (c.doc_path, c.page, c.chunk_index))
        meta = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "provider": "lexical-bm25",
            "chunk_params": {"chunk_chars": chunk_chars, "chunk_overlap": chunk_overlap},
            "chunk_count": len(chunks),
            "doc_count": len(docs),
            "total_chars": sum(len(chunk.text) for chunk in chunks),
            "docs": docs,
        }
        index = cls(chunks, meta, index_dir=index_dir)
        index.save()
        return index

    def save(self) -> Path:
        if self.index_dir is None:
            raise RetrievalError("Index has no directory; cannot save.")
        self.index_dir.mkdir(parents=True, exist_ok=True)
        chunks_path = self.index_dir / CHUNKS_FILENAME
        payload = "".join(
            json.dumps(chunk.as_dict(), sort_keys=True, ensure_ascii=False) + "\n"
            for chunk in self.chunks
        )
        chunks_path.write_text(payload, encoding="utf-8")
        meta = dict(self.meta)
        meta["chunks_sha256"] = chunks_hash(chunks_path)
        meta["chunks_file"] = CHUNKS_FILENAME
        (self.index_dir / META_FILENAME).write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.meta = meta
        return chunks_path

    @classmethod
    def load(cls, index_dir: Path, *, verify: bool = True) -> "LexicalIndex":
        meta_path = index_dir / META_FILENAME
        chunks_path = index_dir / CHUNKS_FILENAME
        if not meta_path.exists() or not chunks_path.exists():
            raise RetrievalError(
                f"No index at {index_dir}. Build it with `ras index` (or `ras run`)."
            )
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        chunks = [
            Chunk.from_dict(json.loads(line))
            for line in chunks_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if verify:
            expected = meta.get("chunks_sha256")
            actual = chunks_hash(chunks_path)
            if expected and expected != actual:
                raise RetrievalError(
                    f"Index at {index_dir} is corrupt: chunks_sha256 is {expected} "
                    f"but the file hashes to {actual}."
                )
        index = cls(chunks, meta, index_dir=index_dir)
        if index.meta.get("chunk_count") != len(chunks):
            raise RetrievalError(
                f"Index at {index_dir} is inconsistent: meta says "
                f"{index.meta.get('chunk_count')} chunks, file has {len(chunks)}."
            )
        return index


    # -- search ----------------------------------------------------------
    def _postings(self, terms: Iterable[str]) -> tuple[dict[str, dict[int, int]], dict[str, int]]:
        wanted = set(terms)
        postings: dict[str, dict[int, int]] = {term: {} for term in wanted}
        for position, chunk in enumerate(self.chunks):
            tokens = tokenize(chunk.text)
            for token in wanted.intersection(tokens):
                postings[token][position] = tokens.count(token)
        return postings, {term: len(posting) for term, posting in postings.items()}

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        min_score: float = 0.0,
        min_terms: int = 1,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> list[SearchHit]:
        """BM25 search.

        Only *informative* terms (document frequency <= 50% of the corpus)
        count towards ``min_terms``: boilerplate tokens such as preprint line
        numbers appear everywhere and must not be able to "support" an answer.
        """
        terms = sorted(set(tokenize(query)))
        if not terms or not self.chunks:
            return []
        postings, doc_freq = self._postings(terms)
        total = len(self.chunks)
        scores: dict[int, float] = {}
        matched: dict[int, set[str]] = {}
        for term in terms:
            posting = postings[term]
            df = doc_freq[term]
            if df == 0:
                continue
            informative = df <= _IDF_DF_RATIO_LIMIT * total
            idf = math.log(1.0 + (total - df + 0.5) / (df + 0.5))
            for position, tf in posting.items():
                length = self._lengths[position]
                denominator = tf + k1 * (1.0 - b + b * length / self._avgdl)
                scores[position] = scores.get(position, 0.0) + idf * tf * (k1 + 1.0) / denominator
                if informative:
                    matched.setdefault(position, set()).add(term)
        hits: list[SearchHit] = []
        for position, score in scores.items():
            if score < min_score:
                continue
            terms_matched = matched.get(position, set())
            if len(terms_matched) < min_terms:
                continue
            hits.append(
                SearchHit(
                    chunk=self.chunks[position],
                    score=score,
                    matched_terms=tuple(sorted(terms_matched)),
                )
            )
        hits.sort(key=lambda hit: (-hit.score, hit.chunk.doc_path, hit.chunk.page, hit.chunk.chunk_index))
        return hits[: max(0, top_k)]

    # -- verification ----------------------------------------------------
    def resolve_citation(self, citation: dict[str, Any]) -> tuple[bool, str]:
        """Check that a citation points at a chunk of the current index."""
        chunk_id = str(citation.get("chunk_id", ""))
        if not chunk_id:
            return False, "citation has no chunk_id"
        chunk = self.by_id.get(chunk_id)
        if chunk is None:
            return False, f"chunk_id {chunk_id} is not in the index"
        claimed_hash = str(citation.get("hash", "") or "")
        if claimed_hash and claimed_hash != chunk.doc_hash:
            return False, f"chunk {chunk_id} has hash {chunk.doc_hash}, citation claims {claimed_hash}"
        claimed_file = str(citation.get("file", "") or "")
        if claimed_file and claimed_file != chunk.file:
            return False, f"chunk {chunk_id} belongs to {chunk.file}, citation claims {claimed_file}"
        claimed_page = citation.get("page")
        if claimed_page is not None and int(claimed_page) != chunk.page:
            return False, f"chunk {chunk_id} is on page {chunk.page}, citation claims page {claimed_page}"
        return True, ""

    def document(self, doc_path: str) -> dict[str, Any] | None:
        for doc in self.meta.get("docs", []):
            if doc.get("doc_path") == doc_path:
                return doc
        return None


def build_index(
    *,
    project_root: Path,
    paths: list[str],
    index_dir: Path,
    extensions: list[str],
    chunk_chars: int = 1200,
    chunk_overlap: int = 200,
) -> LexicalIndex:
    return LexicalIndex.build(
        project_root=project_root,
        paths=paths,
        index_dir=index_dir,
        extensions=extensions,
        chunk_chars=chunk_chars,
        chunk_overlap=chunk_overlap,
    )


def load_index(index_dir: Path, *, verify: bool = True) -> LexicalIndex:
    return LexicalIndex.load(index_dir, verify=verify)


def search(index: LexicalIndex, query: str, **kwargs: Any) -> list[SearchHit]:
    return index.search(query, **kwargs)


def resolve_citation(index: LexicalIndex, citation: dict[str, Any]) -> tuple[bool, str]:
    return index.resolve_citation(citation)


def best_quote(text: str, query: str, *, max_chars: int = 400) -> str:
    """Pick the most query-relevant slice of a chunk, for extractive answers."""
    terms = set(tokenize(query))
    candidates = [part.strip() for part in _SENTENCE_SPLIT.split(normalize_text(text)) if part.strip()]
    if not candidates:
        return normalize_text(text)[:max_chars].strip()
    scored: list[tuple[float, int, str]] = []
    for position, candidate in enumerate(candidates):
        tokens = tokenize(candidate)
        overlap = len(terms.intersection(tokens))
        density = overlap / (len(tokens) or 1)
        scored.append((density, overlap, candidate))
    best = max(scored, key=lambda item: (item[0], item[1], -len(item[2])))
    return best[2][:max_chars].strip()

    return sha256_text(f"{doc_hash}:{page}:{index_in_page}:{text}")[:16]
