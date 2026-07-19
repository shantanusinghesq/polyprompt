"""Platform profiles — versioned, hand-authored config per engine.

Each engine has a JSON profile under `forge/profiles/`. A profile captures the
engine's documented quirks (structure preference, length target, source-filter
syntax, strengths) and the `default_mode` (M1 hardcodes `deep-research`; M3's
auto-detector will override per run). The monthly checkup (M7) refreshes these
files and bumps their `version`.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path

_PROFILE_DIR = Path(__file__).parent / "profiles"
ENGINES = ("chatgpt", "gemini", "claude", "perplexity")
_REQUIRED = (
    "engine",
    "version",
    "default_mode",
    "structure",
    "length",
    "source_filter_syntax",
    "strengths",
    "directives",
)


@dataclass
class PlatformProfile:
    engine: str
    version: str
    default_mode: str
    structure: str
    length: str
    source_filter_syntax: list[str]
    strengths: list[str]
    directives: list[str]
    notes: str = ""


def load_profile(engine: str) -> PlatformProfile:
    path = _PROFILE_DIR / f"{engine}.json"
    if not path.exists():
        raise ValueError(f"no profile for engine: {engine!r}")
    data = json.loads(path.read_text())
    missing = [key for key in _REQUIRED if key not in data]
    if missing:
        raise ValueError(f"profile {engine!r} missing required fields: {missing}")
    allowed = {f.name for f in dataclasses.fields(PlatformProfile)}
    return PlatformProfile(**{k: v for k, v in data.items() if k in allowed})


def load_all_profiles() -> dict[str, PlatformProfile]:
    return {engine: load_profile(engine) for engine in ENGINES}
