"""Text extraction and deterministic chunking.

Extraction is intentionally dumb and faithful: we keep the words the document
contains, including the line numbers of preprints, because every claim in the
harness must be traceable back to a page of the source. Chunking is a pure
function of the extracted text, so re-indexing the same inputs gives the same
chunks and the same chunk identifiers.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

TEXT_SUFFIXES = {".md", ".txt", ".tex", ".rst", ".org", ".csv", ".json", ".yaml", ".yml"}
PDF_SUFFIXES = {".pdf"}


class ExtractionError(RuntimeError):
    """Raised when a file in the corpus cannot be turned into text."""


# Characters that render differently in PDFs but mean the same thing to a
# reader and to a search query.
_GLYPH_MAP = {
    "\u2212": "-",  # minus sign
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00d7": " x ",
    "\u00b7": " ",
    "\u2192": " to ",
    "\u2190": " from ",
    "\u2264": " <= ",
    "\u2265": " >= ",
    "\u00b1": " +- ",
    "\u03bc": "mu",
    "\u03c0": "pi",
    "\u03c8": "psi",
    "\u03b8": "theta",
    "\u03b3": "gamma",
    "\u0393": "gamma",
    "\u03c6": "phi",
    "\u03b1": "alpha",
    "\u03b2": "beta",
    "\u03bb": "lambda",
    "\u03c3": "sigma",
    "\u0394": "delta",
    "\u03b7": "eta",
    "\u03bd": "nu",
    "\u03c7": "chi",
    "\u2126": "ohm",
    "\u00b0": " deg ",
}

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from",
    "had", "has", "have", "in", "into", "is", "it", "its", "of", "on", "or",
    "that", "the", "their", "then", "there", "these", "this", "those", "to",
    "was", "were", "which", "while", "with", "what", "when", "where", "how",
    "used", "use", "using", "does", "do", "did", "given", "give", "also",
}


@dataclass(frozen=True)
class Page:
    """One addressable unit of a document (a PDF page, a file, a section)."""

    number: int
    text: str
    locator: str = ""

    def __post_init__(self) -> None:
        if not self.locator:
            object.__setattr__(self, "locator", f"page {self.number}")


def normalize_text(text: str) -> str:
    """Fold glyph variants so that queries in plain ASCII can match the source."""
    text = unicodedata.normalize("NFKC", text or "")
    for src, dst in _GLYPH_MAP.items():
        if src in text:
            text = text.replace(src, dst)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    return text


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens with stopwords removed (no stemming)."""
    normalized = normalize_text(text).lower()
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return [t for t in tokens if t not in _STOPWORDS]


def _split_units(text: str) -> list[str]:
    """Split page text at sentence ends and line breaks, keeping order."""
    units = re.split(r"(?<=[.!?;:])\s+|\n", text)
    return [u.strip() for u in units if u.strip()]


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def chunk_text(
    pages: list[Page],
    *,
    chunk_chars: int = 1200,
    chunk_overlap: int = 200,
) -> list[dict]:
    """Deterministically split pages into chunks with stable identifiers.

    Chunk identifiers depend only on the document hash, the page number, the
    position within the page and the chunk text.
    """
    if chunk_chars < 200:
        raise ExtractionError("chunk_chars must be >= 200")
    if chunk_overlap < 0 or chunk_overlap >= chunk_chars:
        raise ExtractionError("chunk_overlap must be >= 0 and < chunk_chars")

    chunks: list[dict] = []
    for page in pages:
        units = _split_units(page.text)
        current: list[str] = []
        current_len = 0

        def emit(units_in_chunk: list[str]) -> None:
            body = "\n".join(units_in_chunk).strip()
            if body:
                chunks.append({"page": page.number, "locator": page.locator, "text": body})

        for unit in units:
            if current and current_len + len(unit) > chunk_chars:
                emit(current)
                tail: list[str] = []
                tail_len = 0
                for previous in reversed(current):
                    if tail_len >= chunk_overlap:
                        break
                    tail.insert(0, previous)
                    tail_len += len(previous) + 1
                current = tail
                current_len = tail_len
            current.append(unit)
            current_len += len(unit) + 1
        emit(current)
    return chunks


def extract_pages(path: Path) -> list[Page]:
    """Extract addressable pages from a supported file."""
    suffix = path.suffix.lower()
    if suffix in PDF_SUFFIXES:
        return _extract_pdf(path)
    if suffix in TEXT_SUFFIXES:
        raw = path.read_text(encoding="utf-8", errors="replace")
        return [Page(number=1, text=raw, locator="whole file")] if raw.strip() else []
    raise ExtractionError(
        f"Unsupported corpus file type: {path.name} ({suffix or 'no suffix'}). "
        f"Supported: {', '.join(sorted(PDF_SUFFIXES | TEXT_SUFFIXES))}"
    )


def _extract_pdf(path: Path) -> list[Page]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ExtractionError(
            "PDF extraction needs PyMuPDF. Install it with `pip install pymupdf` "
            "or convert the document to text."
        ) from exc

    pages: list[Page] = []
    with fitz.open(str(path)) as doc:
        for number, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            if text.strip():
                pages.append(Page(number=number, text=text))
    return pages


def iter_corpus_files(project_root: Path, paths: list[str], extensions: list[str]) -> list[Path]:
    """Expand configured corpus paths into a sorted, de-duplicated file list."""
    suffixes = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    files: list[Path] = []
    for raw in paths:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = (project_root / candidate).resolve()
        if candidate.is_file():
            files.append(candidate)
        elif candidate.is_dir():
            for suffix in sorted(suffixes):
                files.extend(sorted(p for p in candidate.rglob(f"*{suffix}") if p.is_file()))
    unique: dict[str, Path] = {}
    for path in files:
        try:
            key = str(path.resolve().relative_to(project_root))
        except ValueError:
            key = str(path.resolve())
        unique[key] = path.resolve()
    return [unique[key] for key in sorted(unique)]
