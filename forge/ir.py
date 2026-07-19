"""Intermediate Representation (IR) of a research prompt.

M0 stub: fields are placeholders and only `intent` is populated. The M1
three-question intake + normalizer will fill these in for real, and every
per-engine rewriter will consume the IR (not the raw prompt).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptIR:
    """Structured form of a general research prompt.

    Mirrors the IR sketched in the PRD (§4). M0 leaves everything but `intent`
    empty; do not rely on the other fields until M1.
    """

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

    @classmethod
    def stub_from_prompt(cls, prompt: str) -> "PromptIR":
        """M0 placeholder normalizer: collapse whitespace, store as intent.

        No real parsing yet — this exists so the M0 skeleton already threads a
        PromptIR through the pipeline, ready for M1 to make it meaningful.
        """
        return cls(intent=" ".join(prompt.strip().split()))
