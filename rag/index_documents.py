#!/usr/bin/env python3
"""Build a local Chroma vector database from configured references."""

from __future__ import annotations

import argparse
import errno
import hashlib
import re
import shutil
from pathlib import Path
from typing import Any

# sqlite workaround for lxplus-like environments
try:  # pragma: no cover
    __import__("pysqlite3")
    import sys

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except Exception:  # pragma: no cover
    pass

import ftfy
import fitz
import pymupdf4llm
import yaml
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pylatexenc.latex2text import LatexNodes2Text

try:
    from langchain_chroma import Chroma
except ImportError:  # pragma: no cover
    from langchain_community.vectorstores import Chroma


LATEX_CONVERTER = LatexNodes2Text(math_mode="text", strict_latex_spaces=False)


def _normalize_path(raw_path: str, base_dir: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def _iter_paths(config: dict[str, Any], config_path: Path) -> list[Path]:
    base_dir = config_path.parent
    collected: list[Path] = []
    for group in config.get("sources", []):
        for raw_path in group.get("paths", []):
            p = _normalize_path(raw_path, base_dir)
            if p.is_file():
                collected.append(p)
            elif p.is_dir():
                for ext in group.get("extensions", []):
                    collected.extend(sorted(p.rglob(f"*{ext}")))
    return sorted(set(collected))


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def _clean_latex_text(text: str) -> str:
    if not text:
        return ""
    text = ftfy.fix_text(text)
    replacements = {
        r"\\alpha": "alpha",
        r"\\beta": "beta",
        r"\\gamma": "gamma",
        r"\\delta": "delta",
        r"\\lambda": "lambda",
        r"\\mu": "mu",
        r"\\pi": "pi",
        r"\\sigma": "sigma",
        r"\\phi": "phi",
        r"\\pm": "+/-",
        r"\\times": "x",
        r"\\rightarrow": "->",
        r"\\to": "->",
        r"\\mathrm\{([^}]+)\}": r"\1",
        r"\\text\{([^}]+)\}": r"\1",
        r"\$": "",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    try:
        math_pattern = r"\$\$([^$]+)\$\$|\$([^$]+)\$|\\begin\{equation\}(.*?)\\end\{equation\}"

        def convert_math(match: re.Match[str]) -> str:
            content = match.group(1) or match.group(2) or match.group(3)
            try:
                return LATEX_CONVERTER.latex_to_text(content)
            except Exception:
                return content

        text = re.sub(math_pattern, convert_math, text, flags=re.DOTALL)
    except Exception:
        pass
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _extract_text(path: Path) -> str:
    if path.suffix.lower() != ".pdf":
        try:
            return _clean_latex_text(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return ""
    try:
        markdown_text = pymupdf4llm.to_markdown(str(path))
        return _clean_latex_text(markdown_text)
    except Exception:
        try:
            doc = fitz.open(path)
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
            return _clean_latex_text(text)
        except Exception:
            return ""


def _classify_document(path: Path, rules: dict[str, list[str]]) -> tuple[str, str]:
    path_str = str(path).lower()
    source_type = "other"
    for doc_type, hints in rules.items():
        if any(h.lower() in path_str for h in hints):
            source_type = doc_type
            break
    if source_type == "other":
        if path.suffix.lower() == ".py":
            source_type = "code"
        elif path.suffix.lower() in {".md", ".txt", ".rst"}:
            source_type = "documentation"
        elif path.suffix.lower() == ".pdf":
            source_type = "paper"
    category = {
        "paper": "published",
        "analysis_note": "internal",
        "code": "implementation",
        "documentation": "notes",
    }.get(source_type, "misc")
    return source_type, category


def _create_chunks(
    text: str,
    metadata: dict[str, Any],
    chunk_size: int,
    chunk_overlap: int,
    scientific_chunk_size: int,
    scientific_chunk_overlap: int,
) -> list[Document]:
    if not text.strip():
        return []
    if metadata.get("source_type") in {"paper", "analysis_note"}:
        chunk_size = scientific_chunk_size
        chunk_overlap = scientific_chunk_overlap
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n\n", "\n\n", "\n", ". ", " "],
        length_function=len,
    )
    chunks = splitter.split_text(text)
    docs: list[Document] = []
    for idx, chunk in enumerate(chunks):
        chunk_meta = dict(metadata)
        chunk_meta["chunk_index"] = idx
        chunk_meta["total_chunks"] = len(chunks)
        chunk_meta["content_hash"] = hashlib.md5(chunk.encode()).hexdigest()[:12]
        docs.append(Document(page_content=chunk, metadata=chunk_meta))
    return docs


def main() -> None:
    parser = argparse.ArgumentParser(description="Index references into Chroma.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=1500)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--collection-name", default="")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    indexing_cfg = config.get("indexing", {})
    collection_name = args.collection_name or indexing_cfg.get("collection_name", "rag-ai-scientist")
    chunk_size = int(indexing_cfg.get("chunk_size", args.chunk_size))
    chunk_overlap = int(indexing_cfg.get("chunk_overlap", args.chunk_overlap))
    scientific_chunk_size = int(indexing_cfg.get("scientific_chunk_size", 2000))
    scientific_chunk_overlap = int(indexing_cfg.get("scientific_chunk_overlap", 300))
    type_rules = indexing_cfg.get(
        "doc_type_rules",
        {
            "analysis_note": ["analysis_notes", "note"],
            "paper": ["papers", "publication"],
            "documentation": ["docs", "readme"],
        },
    )

    out_dir = Path(args.output_dir).resolve()
    if args.force and out_dir.exists():
        try:
            shutil.rmtree(out_dir)
        except OSError as e:
            if e.errno != errno.EBUSY:
                raise
            for p in sorted(out_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                try:
                    if p.is_file() or p.is_symlink():
                        p.unlink()
                    else:
                        shutil.rmtree(p)
                except OSError:
                    pass
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = _iter_paths(config, config_path)
    if not paths:
        raise SystemExit("No indexable paths found in config.")

    documents: list[Document] = []
    for path in paths:
        text = _extract_text(path)
        if not text:
            continue
        source_type, doc_category = _classify_document(path, type_rules)
        metadata = {
            "file": path.name,
            "doc_path": str(path),
            "doc_hash": _file_hash(path),
            "source_type": source_type,
            "doc_category": doc_category,
        }
        documents.extend(
            _create_chunks(
                text=text,
                metadata=metadata,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                scientific_chunk_size=scientific_chunk_size,
                scientific_chunk_overlap=scientific_chunk_overlap,
            )
        )

    if not documents:
        raise SystemExit("No readable documents found after extraction.")

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=str(out_dir),
        collection_name=collection_name,
    )
    unique_docs = len({doc.metadata["doc_path"] for doc in documents})
    print(
        f"Indexed {len(documents)} chunks from {unique_docs} documents "
        f"into collection '{collection_name}'."
    )


if __name__ == "__main__":
    main()
