from __future__ import annotations

import re

from rag_ai_scientist.harness.base import Profile
from rag_ai_scientist.harness.profiles.whest import WHEST_PROFILE

_PROFILES: dict[str, Profile] = {
    WHEST_PROFILE.name: WHEST_PROFILE,
}


def list_profiles() -> list[Profile]:
    return [ _PROFILES[k] for k in sorted(_PROFILES) ]


def register_profile(profile: Profile, *, replace: bool = False) -> None:
    key = profile.name.strip().lower()
    if key != profile.name or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", key):
        raise ValueError("Profile names must be lowercase letters, numbers, underscores, or hyphens.")
    if key in _PROFILES and not replace:
        raise ValueError(f"Harness profile {key!r} is already registered.")
    _PROFILES[key] = profile


def get_profile(name: str) -> Profile:
    key = name.strip().lower()
    if key not in _PROFILES:
        known = ", ".join(sorted(_PROFILES))
        raise KeyError(f"Unknown harness profile {name!r}. Known: {known}")
    return _PROFILES[key]
