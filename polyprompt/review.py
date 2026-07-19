"""Reviewer loop — ratings govern the graph (PRD FR-7; M6).

A *distinct* reviewer records intent-fidelity + quality (1–5) with a
depth-of-reasoning explanation and a mode-correctness call. The review is
stored with the memo as a JSON sidecar (`<memo>.review.json`), and its
sentiment becomes graph labels over the memo's tactic <-> tag edges:

  positive  — both ratings >= 4 -> +1 pos per edge
  negative  — either rating <= 2 -> +1 neg per edge
  neutral   — anything else      -> recorded, no labels

Dedupe key is (source_prompt_hash, engine, reviewer): one vote per reviewer
per memo. Mode-correctness labels feed the mode-detector accuracy metric.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from polyprompt.graph import Graph

_SIDECAR_SUFFIX = ".review.json"


@dataclass
class Review:
    memo_filename: str
    reviewer: str
    intent_fidelity: int  # 1-5
    quality: int  # 1-5
    depth_explanation: str
    mode_correct: bool
    reviewed_at: str

    def __post_init__(self):
        if not self.reviewer.strip():
            raise ValueError("reviewer must be non-empty (FR-7: distinct reviewer)")
        for name in ("intent_fidelity", "quality"):
            value = getattr(self, name)
            if not 1 <= value <= 5:
                raise ValueError(f"{name} must be 1-5, got {value}")


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


def save_review(review: Review, directory: Path | str) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _sidecar_name(review.memo_filename)
    path.write_text(json.dumps(asdict(review), indent=2) + "\n")
    return path


def load_reviews(directory: Path | str) -> list[Review]:
    directory = Path(directory)
    reviews = []
    if not directory.exists():
        return reviews
    for path in sorted(directory.glob(f"*{_SIDECAR_SUFFIX}")):
        try:
            reviews.append(Review(**json.loads(path.read_text())))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return reviews


def apply_review(graph: Graph, frontmatter: dict, review: Review) -> str | None:
    """Turn one review into graph labels. Returns the sentiment applied, or
    None if this (hash, engine, reviewer) already voted."""
    key = (
        frontmatter["source_prompt_hash"],
        frontmatter["engine"],
        review.reviewer,
    )
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
    """Fraction of reviews marking the detected mode correct; None if no data."""
    if not reviews:
        return None
    return sum(1 for r in reviews if r.mode_correct) / len(reviews)
