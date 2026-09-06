"""Reviewer ratings govern the graph; their persisted evidence is immutable.

The first review keeps the legacy <memo>.review.json name. Additional reviewers
use a reviewer-hashed sidecar, so legacy readers here continue to work. A retry
is idempotent; changing an already-counted vote is rejected rather than leaving
the graph and its evidence in disagreement.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from polyprompt.graph import Graph

_SIDECAR_SUFFIX = ".review.json"


@dataclass
class Review:
    memo_filename: str
    reviewer: str
    intent_fidelity: int
    quality: int
    depth_explanation: str
    mode_correct: bool
    reviewed_at: str

    def __post_init__(self):
        if not isinstance(self.reviewer, str) or not self.reviewer.strip():
            raise ValueError("reviewer must be non-empty (FR-7: distinct reviewer)")
        if (not isinstance(self.memo_filename, str) or not self.memo_filename.strip()
                or self.memo_filename in (".", "..")
                or any(c in self.memo_filename for c in ("/", "\\", "\x00"))):
            raise ValueError("memo_filename must be a filename, not a path")
        for name in ("intent_fidelity", "quality"):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 5:
                raise ValueError(f"{name} must be an integer 1-5, got {value!r}")
        if type(self.mode_correct) is not bool:
            raise ValueError("mode_correct must be a boolean")
        if not isinstance(self.depth_explanation, str) or not self.depth_explanation.strip():
            raise ValueError("depth_explanation must be non-empty")


def sentiment(review: Review) -> str:
    lowest = min(review.intent_fidelity, review.quality)
    if lowest >= 4:
        return "positive"
    if lowest <= 2:
        return "negative"
    return "neutral"


def _sidecar_name(memo_filename: str) -> str:
    stem = memo_filename[:-3] if memo_filename.endswith(".md") else memo_filename
    return stem + _SIDECAR_SUFFIX


def _vote(review: Review) -> dict:
    data = asdict(review)
    data.pop("reviewed_at")
    return data


def save_review(review: Review, directory: Path | str) -> Path:
    """Preserve every reviewer and never overwrite an already-counted vote."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    legacy = directory / _sidecar_name(review.memo_filename)
    digest = hashlib.sha256(review.reviewer.encode("utf-8")).hexdigest()
    stem = legacy.name[:-len(_SIDECAR_SUFFIX)]
    keyed = directory / f"{stem}.{digest}{_SIDECAR_SUFFIX}"

    for _ in range(3):
        for path in (legacy, keyed):
            if path.is_symlink():
                raise ValueError(f"refusing symlink review sidecar: {path.name}")
            if not path.exists():
                continue
            try:
                existing = Review(**json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"invalid existing review; retained {path.name}") from exc
            if (existing.memo_filename, existing.reviewer) == (review.memo_filename, review.reviewer):
                if _vote(existing) != _vote(review):
                    raise ValueError("review already recorded with different values; original retained")
                return path
            if path == keyed:
                raise ValueError("review sidecar identity conflict; original retained")
        path = legacy if not legacy.exists() else keyed
        try:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(asdict(review), indent=2) + "\n")
        except FileExistsError:
            continue
        return path
    raise ValueError("review sidecar changed concurrently; retry without modifying the original")


def load_reviews(directory: Path | str) -> list[Review]:
    directory = Path(directory)
    reviews = []
    if not directory.exists():
        return reviews
    for path in sorted(directory.glob(f"*{_SIDECAR_SUFFIX}")):
        try:
            reviews.append(Review(**json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, TypeError, ValueError):
            continue
    return reviews


def apply_review(graph: Graph, frontmatter: dict, review: Review) -> str | None:
    """One vote per (source prompt, engine, reviewer), unchanged from M6."""
    key = (frontmatter["source_prompt_hash"], frontmatter["engine"], review.reviewer)
    if key in graph.reviewed:
        return None
    graph.reviewed.add(key)
    verdict = sentiment(review)
    if verdict == "neutral":
        return verdict
    tags = dict(frontmatter.get("tags", {}))
    tags["engine"] = frontmatter["engine"]
    tags["mode"] = frontmatter["mode"]
    positive = verdict == "positive"
    for tactic in frontmatter.get("tactics", []):
        for dimension, value in tags.items():
            graph.add_label(tactic, dimension, value, positive=positive)
    return verdict


def mode_accuracy(reviews: list[Review]) -> float | None:
    if not reviews:
        return None
    return sum(1 for r in reviews if r.mode_correct) / len(reviews)
