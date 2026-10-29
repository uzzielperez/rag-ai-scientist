from __future__ import annotations

from rag_ai_scientist.harness.base import Profile

# Built-in profiles live in rag_ai_scientist.harness.profiles and are loaded
# lazily by _load_builtins(); projects register their own with :func:`register`.
_PROFILES: dict[str, Profile] = {}


def register(profile: Profile) -> None:
    """Register a profile for the legacy ``harness`` commands."""
    _PROFILES[profile.name] = profile


def list_profiles() -> list[Profile]:
    _load_builtins()
    return [_PROFILES[k] for k in sorted(_PROFILES)]


def get_profile(name: str) -> Profile:
    key = name.strip().lower()
    if key not in _PROFILES:
        _load_builtins()
    if key not in _PROFILES:
        known = ", ".join(sorted(_PROFILES)) or "none"
        raise KeyError(
            f"Unknown harness profile {name!r}. Registered profiles: {known}. "
            "Built-in profiles live in rag_ai_scientist.harness.profiles."
        )
    return _PROFILES[key]


def _load_builtins() -> None:
    """Import bundled profile modules once; each module self-registers."""
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    _BUILTINS_LOADED = True
    import importlib

    for module in ("dali",):
        try:
            importlib.import_module(f"rag_ai_scientist.harness.profiles.{module}")
        except ImportError:  # a broken bundled profile must not break the registry
            continue


_BUILTINS_LOADED = False
