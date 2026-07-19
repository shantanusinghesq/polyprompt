"""Intermediate Representation (IR) of a research prompt, plus the M1 normalizer.

M0 shipped a stub. M1 adds `normalize(prompt, intake)` — a deterministic pass
that folds the raw prompt and the three-question intake answers into a
PromptIR. It stays intentionally light (no deep NLP): intake answers drive
recency and depth; a small keyword heuristic seeds source preferences. The
per-engine renderers do the linguistic framing on top of this IR.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from forge.intake import DEPTH_LABELS, IntakeAnswers

# keyword -> canonical source-preference label (insertion order preserved)
_SOURCE_HINTS = {
    "primary": "primary sources",
    "peer-review": "peer-reviewed sources",
    "peer review": "peer-reviewed sources",
    "academic": "academic sources",
    "official": "official sources",
    "cite": "inline citations",
    "source": "cite sources",
}

_YEAR_RE = re.compile(r"(20\d{2})\+?")


@dataclass
class PromptIR:
    """Structured form of a general research prompt (PRD §4)."""

    intent: str = ""
    topic: str = ""
    entities: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    output_format: str = ""
    depth: str = ""
    reasoning_layers: int = 0
    recency_window: str = ""
    source_preferences: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)


def normalize(prompt: str, intake: IntakeAnswers | None = None) -> PromptIR:
    """Fold a raw prompt + intake answers into a PromptIR.

    Raises:
        ValueError: if the prompt is empty or whitespace-only.
    """
    intake = intake or IntakeAnswers()
    core = " ".join(prompt.strip().split())
    if not core:
        raise ValueError("prompt must be non-empty")

    depth = intake.normalized_depth()

    recency = intake.time_period.strip()
    if not recency:
        match = _YEAR_RE.search(core)
        if match:
            recency = f"{match.group(1)}+"

    low = core.lower()
    sources: list[str] = []
    for keyword, label in _SOURCE_HINTS.items():
        if keyword in low and label not in sources:
            sources.append(label)

    constraints: list[str] = []
    if intake.clarifications.strip():
        constraints.append(intake.clarifications.strip())

    return PromptIR(
        intent=core,
        depth=DEPTH_LABELS[depth],
        reasoning_layers=depth,
        recency_window=recency,
        source_preferences=sources,
        constraints=constraints,
    )
