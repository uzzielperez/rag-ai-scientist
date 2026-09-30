from __future__ import annotations

from rag_ai_scientist.harness.base import Profile

# No profiles ship with the package: the domain-free harness entry point is
# ``ras run`` (mode A-retrieval). Profiles remain an extension point —
# projects register their own with :func:`register`.
_PROFILES: dict[str, Profile] = {}


def register(profile: Profile) -> None:
    """Register a profile for the legacy ``harness`` commands."""
    _PROFILES[profile.name] = profile


def list_profiles() -> list[Profile]:
    return [_PROFILES[k] for k in sorted(_PROFILES)]


def get_profile(name: str) -> Profile:
    key = name.strip().lower()
    if key not in _PROFILES:
        known = ", ".join(sorted(_PROFILES)) or "none"
        raise KeyError(
            f"Unknown harness profile {name!r}. Registered profiles: {known}. "
            "This release ships no profiles; the gated loop is `ras run --mode A-retrieval`."
        )
    return _PROFILES[key]
