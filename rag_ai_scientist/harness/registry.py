from __future__ import annotations

from rag_ai_scientist.harness.base import Profile
from rag_ai_scientist.harness.profiles.whest import WHEST_PROFILE

_PROFILES: dict[str, Profile] = {
    WHEST_PROFILE.name: WHEST_PROFILE,
}


def list_profiles() -> list[Profile]:
    return [ _PROFILES[k] for k in sorted(_PROFILES) ]


def get_profile(name: str) -> Profile:
    key = name.strip().lower()
    if key not in _PROFILES:
        known = ", ".join(sorted(_PROFILES))
        raise KeyError(f"Unknown harness profile {name!r}. Known: {known}")
    return _PROFILES[key]
