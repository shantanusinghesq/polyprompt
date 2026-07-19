"""The three-question intake (PRD decision 5).

M0 had no intake. M1 collects three specificity inputs before rewriting:
  1. time period / recency window
  2. depth of issue-spotting / reasoning layers (1-3)
  3. clarifying questions if the request is still ambiguous (free text)

The `/forge-prompts` command asks these conversationally; the CLI accepts the
answers as flags. Mode auto-detection is deferred to M3 — M1 hardcodes
deep-research.
"""

from __future__ import annotations

from dataclasses import dataclass

QUESTIONS = (
    "1. Time period / recency: how recent must sources be? (e.g. '2024+', 'last 5 years', 'no constraint')",
    "2. Depth: how many layers of reasoning / issue-spotting? (1 = quick answer, 2 = standard, 3 = deep multi-layer)",
    "3. Ambiguity: anything to pin down — scope, definitions, audience? (free text; skip if already clear)",
)

DEPTH_LABELS = {1: "quick", 2: "standard", 3: "deep"}


@dataclass
class IntakeAnswers:
    """Answers to the three-question intake. Sensible defaults so the CLI is
    runnable even when the caller skips the questions."""

    time_period: str = ""
    depth: int = 2
    clarifications: str = ""

    def normalized_depth(self) -> int:
        return self.depth if self.depth in DEPTH_LABELS else 2
