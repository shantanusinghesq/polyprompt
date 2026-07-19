"""Monthly checkup — keep platform profiles current (PRD FR-8; M7).

The checkup is user-invoked. The *judgment* (reading vendor primary docs and
deciding what changed) happens at the command layer (/polyprompt-checkup, model-
assisted); this module is the deterministic core: a staleness report against
each profile's `last_checked`, and a version-stamped propose/apply pair for
profile diffs. Proposals never write; apply stamps `version` (YYYY.MM.N) and
`last_checked` together so every profile change is traceable to a checkup.

Profile dir override: FORGE_PROFILE_DIR env var (used by tests to sandbox
--apply; also handy for dry-running a proposed profile set).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from polyprompt.profile import ENGINES, _PROFILE_DIR

STALE_DAYS = 30  # monthly cadence

# Fields the checkup may change. Identity and stamps are managed, not settable.
_PROTECTED = ("engine", "version", "last_checked")


def profile_dir_default() -> Path:
    override = os.environ.get("FORGE_PROFILE_DIR", "")
    return Path(override) if override else _PROFILE_DIR


@dataclass
class ProfileStatus:
    engine: str
    version: str
    last_checked: str  # "" if never recorded
    days_since: int | None  # None if never recorded
    stale: bool
    doc_sources: list[str]


@dataclass
class Proposal:
    engine: str
    old_version: str
    new_version: str
    checked_on: str  # ISO date the checkup ran
    changes: dict[str, tuple]  # field -> (old, new)


def _read_profile(engine: str, profile_dir: Path) -> dict:
    path = profile_dir / f"{engine}.json"
    if not path.exists():
        raise ValueError(f"no profile for engine: {engine!r} in {profile_dir}")
    return json.loads(path.read_text())


def checkup_status(now: date, profile_dir: Path | None = None) -> list[ProfileStatus]:
    profile_dir = profile_dir or profile_dir_default()
    statuses = []
    for path in sorted(profile_dir.glob("*.json")):
        data = json.loads(path.read_text())
        last = data.get("last_checked", "")
        days = (now - date.fromisoformat(last)).days if last else None
        statuses.append(ProfileStatus(
            engine=data["engine"],
            version=data["version"],
            last_checked=last,
            days_since=days,
            stale=days is None or days > STALE_DAYS,
            doc_sources=data.get("doc_sources", []),
        ))
    return statuses


def next_version(current: str, now: date) -> str:
    """Version stamps are YYYY.MM.N: N increments within a month, resets on a
    new month."""
    prefix = f"{now.year:04d}.{now.month:02d}"
    if current.startswith(prefix + "."):
        n = int(current.rsplit(".", 1)[1]) + 1
    else:
        n = 0
    return f"{prefix}.{n}"


def propose_update(engine: str, updates: dict, now: date,
                   profile_dir: Path | None = None) -> Proposal:
    """Build a version-stamped diff proposal. Read-only — apply_update writes."""
    profile_dir = profile_dir or profile_dir_default()
    data = _read_profile(engine, profile_dir)

    protected = [k for k in updates if k in _PROTECTED]
    if protected:
        raise ValueError(f"protected fields are managed by the checkup: {protected}")
    unknown = [k for k in updates if k not in data]
    if unknown:
        raise ValueError(f"unknown profile fields: {unknown}")

    changes = {k: (data[k], v) for k, v in updates.items() if data[k] != v}
    if not changes:
        raise ValueError("no changes: proposed values match the current profile")

    return Proposal(
        engine=engine,
        old_version=data["version"],
        new_version=next_version(data["version"], now),
        checked_on=now.isoformat(),
        changes=changes,
    )


def apply_update(proposal: Proposal, profile_dir: Path | None = None) -> Path:
    """Write a proposal: changed fields + version + last_checked stamps."""
    profile_dir = profile_dir or profile_dir_default()
    data = _read_profile(proposal.engine, profile_dir)
    for field, (_old, new) in proposal.changes.items():
        data[field] = new
    data["version"] = proposal.new_version
    data["last_checked"] = proposal.checked_on
    path = profile_dir / f"{proposal.engine}.json"
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


__all__ = [
    "ENGINES",
    "STALE_DAYS",
    "ProfileStatus",
    "Proposal",
    "apply_update",
    "checkup_status",
    "next_version",
    "propose_update",
]
