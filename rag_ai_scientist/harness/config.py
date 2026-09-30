"""Harness configuration: defaults, project config, explicit overrides.

Precedence (later wins): built-in defaults, the project config file, CLI
overrides. Overrides use dotted keys (``retrieval.min_score=4``) so that a
CORRECT iteration, a test and a human all change the run the same way, and the
resolved dictionary is what goes into the run's ``config.yaml`` and manifest.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILENAME = "configs/harness.yaml"
LEGACY_CONFIG_FILENAMES = ("configs/references.yaml", "configs/rag.yaml")

DEFAULTS: dict[str, Any] = {
    "run": {
        "name": "retrieval-verification",
        "mode": "A-retrieval",
        "max_attempts": 2,
    },
    "corpus": {
        "paths": ["docs/references/papers"],
        "extensions": [".pdf", ".md", ".txt"],
    },
    "index": {
        "chunk_chars": 1200,
        "chunk_overlap": 200,
    },
    "retrieval": {
        "top_k": 5,
        "min_score": 8.0,
        "min_terms": 2,
    },
    "questions": {
        "path": None,
        "tier1_min": 1.0,
        "tier23_min": 0.8,
    },
    "skills": {
        "generate": True,
        "mirror_to_cursor": False,
        "version": "0.1.0",
    },
    "budgets": {
        "max_steps": 40,
        "max_seconds": 900,
    },
}

SUPPORTED_MODES = ("A-retrieval", "A", "B", "C")


class ConfigError(RuntimeError):
    """Raised when configuration is missing, malformed or contradictory."""


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def parse_overrides(items: list[str]) -> dict[str, Any]:
    """Parse ``a.b=value`` strings into a nested dictionary."""
    overrides: dict[str, Any] = {}
    for raw in items or []:
        if "=" not in raw:
            raise ConfigError(f"Override {raw!r} is not of the form key.subkey=value")
        key, _, value = raw.partition("=")
        key = key.strip()
        if not key:
            raise ConfigError(f"Override {raw!r} has an empty key")
        cursor = overrides
        parts = key.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        try:
            parsed: Any = yaml.safe_load(value)
        except yaml.YAMLError:
            parsed = value
        cursor[parts[-1]] = parsed
    return overrides


def _flat_keys(data: dict[str, Any], prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in data.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict):
            keys |= _flat_keys(value, dotted + ".")
        else:
            keys.add(dotted)
    return keys


def _validate_known_keys(overrides: dict[str, Any]) -> None:
    unknown = _flat_keys(overrides) - _flat_keys(DEFAULTS)
    if unknown:
        raise ConfigError(
            "Unknown config override(s): "
            + ", ".join(sorted(unknown))
            + f". Known keys: {', '.join(sorted(_flat_keys(DEFAULTS)))}"
        )


def _legacy_corpus(config_path: Path) -> dict[str, Any] | None:
    """Derive corpus settings from the pre-harness ``configs/references.yaml``."""
    if not config_path.exists():
        return None
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    sources = data.get("sources") or []
    paths: list[str] = []
    extensions: set[str] = set()
    base = config_path.parent
    for source in sources:
        for raw in source.get("paths", []) or []:
            candidate = Path(raw)
            resolved = (base / candidate).resolve() if not candidate.is_absolute() else candidate
            if resolved.exists():
                try:
                    paths.append(str(resolved.relative_to(base.parent)))
                except ValueError:
                    paths.append(str(resolved))
                extensions.update(source.get("extensions", []) or [])
    if not paths:
        return None
    indexing = data.get("indexing") or {}
    return {
        "corpus": {
            "paths": sorted(set(paths)),
            "extensions": sorted(extensions) or DEFAULTS["corpus"]["extensions"],
        },
        "index": {
            "chunk_chars": int(indexing.get("chunk_size", DEFAULTS["index"]["chunk_chars"])),
            "chunk_overlap": int(indexing.get("chunk_overlap", DEFAULTS["index"]["chunk_overlap"])),
        },
    }


@dataclass
class HarnessConfig:
    """Fully resolved run configuration."""

    project_root: Path
    data_dir: Path
    raw: dict[str, Any]
    overrides: dict[str, Any] = field(default_factory=dict)
    config_path: Path | None = None
    config_sha256: str | None = None
    legacy_config_path: Path | None = None

    def get(self, dotted: str, default: Any = None) -> Any:
        cursor: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(cursor, dict) or part not in cursor:
                return default
            cursor = cursor[part]
        return cursor

    @property
    def mode(self) -> str:
        return str(self.get("run.mode"))

    @property
    def run_name(self) -> str:
        return str(self.get("run.name"))

    @property
    def max_attempts(self) -> int:
        return int(self.get("run.max_attempts"))

    @property
    def chunk_chars(self) -> int:
        return int(self.get("index.chunk_chars"))

    @property
    def chunk_overlap(self) -> int:
        return int(self.get("index.chunk_overlap"))

    @property
    def top_k(self) -> int:
        return int(self.get("retrieval.top_k"))

    @property
    def min_score(self) -> float:
        return float(self.get("retrieval.min_score"))

    @property
    def min_terms(self) -> int:
        return int(self.get("retrieval.min_terms"))

    @property
    def corpus_paths(self) -> list[str]:
        return [str(item) for item in self.get("corpus.paths", [])]

    @property
    def corpus_extensions(self) -> list[str]:
        return [str(item) for item in self.get("corpus.extensions", [])]

    @property
    def questions_path(self) -> Path | None:
        raw = self.get("questions.path")
        if not raw:
            return None
        path = Path(str(raw)).expanduser()
        return path if path.is_absolute() else (self.project_root / path)

    def absolute_corpus_paths(self) -> list[Path]:
        resolved: list[Path] = []
        for raw in self.corpus_paths:
            candidate = Path(raw).expanduser()
            resolved.append(
                candidate if candidate.is_absolute() else (self.project_root / candidate).resolve()
            )
        return resolved

    def with_overrides(self, overrides: dict[str, Any]) -> "HarnessConfig":
        if not overrides:
            return self
        _validate_known_keys(overrides)
        return HarnessConfig(
            project_root=self.project_root,
            data_dir=self.data_dir,
            raw=_deep_merge(self.raw, overrides),
            overrides=_deep_merge(self.overrides, overrides),
            config_path=self.config_path,
            config_sha256=self.config_sha256,
            legacy_config_path=self.legacy_config_path,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "mode": self.mode,
            "config_path": str(self.config_path) if self.config_path else None,
            "config_sha256": self.config_sha256,
            "overrides": self.overrides,
            "resolved": json.loads(json.dumps(self.raw, default=str)),
        }

    def sha256(self) -> str:
        payload = json.dumps(self.raw, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def environment(self) -> dict[str, Any]:
        return {"python": sys.version.split()[0], "platform": platform.platform()}
def load_config(
    *,
    project_root: Path,
    config_path: Path | None = None,
    mode: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> HarnessConfig:
    """Resolve the configuration for one run."""
    from rag_ai_scientist.project_paths import resolve_project_data_dir

    project_root = Path(project_root).resolve()
    if not project_root.exists():
        raise ConfigError(f"Project root does not exist: {project_root}")

    raw = json.loads(json.dumps(DEFAULTS))
    resolved_config_path: Path | None = None
    config_sha256: str | None = None
    legacy_used: Path | None = None

    explicit = config_path is not None
    candidate: Path | None = None
    if explicit:
        candidate = Path(config_path).expanduser()  # type: ignore[arg-type]
        if not candidate.is_absolute():
            candidate = (project_root / candidate).resolve()
        if not candidate.exists():
            raise ConfigError(f"Config file not found: {candidate}")
    elif (project_root / CONFIG_FILENAME).exists():
        candidate = project_root / CONFIG_FILENAME

    if candidate is not None:
        data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ConfigError(f"Config file {candidate} must contain a mapping at the top level.")
        unknown = _flat_keys(data) - _flat_keys(DEFAULTS)
        if unknown:
            raise ConfigError(
                f"Unknown key(s) in {candidate}: {', '.join(sorted(unknown))}. "
                f"Known keys: {', '.join(sorted(_flat_keys(DEFAULTS)))}"
            )
        raw = _deep_merge(raw, data)
        resolved_config_path = candidate
        config_sha256 = hashlib.sha256(candidate.read_bytes()).hexdigest()
    else:
        for legacy_name in LEGACY_CONFIG_FILENAMES:
            legacy_path = project_root / legacy_name
            legacy = _legacy_corpus(legacy_path)
            if legacy:
                raw = _deep_merge(raw, legacy)
                legacy_used = legacy_path
                break

    if overrides:
        _validate_known_keys(overrides)
        raw = _deep_merge(raw, overrides)
    if mode:
        if mode not in SUPPORTED_MODES:
            raise ConfigError(f"Unsupported mode {mode!r}. Supported: {', '.join(SUPPORTED_MODES)}")
        raw["run"]["mode"] = mode

    config = HarnessConfig(
        project_root=project_root,
        data_dir=resolve_project_data_dir(project_root),
        raw=raw,
        overrides=dict(overrides or {}),
        config_path=resolved_config_path,
        config_sha256=config_sha256,
        legacy_config_path=legacy_used,
    )
    if config.mode != "A-retrieval":
        raise ConfigError(
            f"Mode {config.mode!r} is not implemented in this release. "
            "v1 ships the retrieval-verification slice: --mode A-retrieval."
        )
    if config.chunk_overlap >= config.chunk_chars:
        raise ConfigError("index.chunk_overlap must be smaller than index.chunk_chars")
    return config


def write_config_yaml(config: HarnessConfig, destination: Path) -> Path:
    """Write the fully resolved configuration into the run directory."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_root": str(config.project_root),
        "mode": config.mode,
        "run_name": config.run_name,
        "resolved": config.raw,
        "overrides": config.overrides,
        "config_path": str(config.config_path) if config.config_path else None,
        "config_sha256": config.config_sha256,
    }
    destination.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    return destination

