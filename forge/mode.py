"""Hybrid mode auto-detector (PRD FR-3; scratchpad D-05).

Decides per run whether a request should target an engine's **deep-research**
mode or standard **chat**. Rules-first over the IR; genuinely borderline cases
escalate to an injectable `model_fallback` (a real model call at the plugin
layer, a stub in tests — this is the seam that keeps the golden gate
deterministic). Every decision carries a reason and a source, recorded on the
rewrite and in the memo frontmatter.

Mode currently *annotates* the rewrite (renderers stay mode-agnostic in M3);
per-mode rendering is a later refinement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from forge.ir import PromptIR

# request phrasing that leans deep-research
_DEEP_KEYWORDS = (
    "compare", "versus", " vs ", "analyze", "analyse", "synthesize", "synthesise",
    "comprehensive", "evaluate", "assess", "report", "in depth", "deep dive",
    "trade-off", "tradeoff", "implications",
)
# request phrasing that leans a quick factual chat answer
_FACTUAL_KEYWORDS = (
    "what is", "who is", "who was", "when did", "when was", "define",
    "definition of", "how many", "how much is", "capital of", "date of",
    "meaning of",
)

_DEEP = "deep-research"
_CHAT = "chat"


@dataclass
class ModeDecision:
    mode: str
    reason: str
    source: str  # "rules" | "model" | "default" | "forced"


def detect_mode(
    ir: PromptIR,
    model_fallback: Callable[[PromptIR], str] | None = None,
) -> ModeDecision:
    """Return a mode decision for the request.

    Rules resolve clear cases (|margin| >= 2). Borderline cases escalate to
    `model_fallback` if provided; otherwise they default to deep-research (the
    heavy-research user's safer default) with source 'default'.
    """
    low = f" {ir.intent.lower()} "
    deep = 0
    chat = 0
    factors: list[str] = []

    if ir.reasoning_layers >= 3:
        deep += 2
        factors.append("reasoning_layers=3")
    elif ir.reasoning_layers <= 1:
        chat += 2
        factors.append("reasoning_layers=1")

    if ir.recency_window:
        deep += 1
        factors.append("recency")
    if ir.source_preferences:
        deep += 1
        factors.append("sources")
    if ir.constraints:
        deep += 1
        factors.append("constraints")
    if any(k in low for k in _DEEP_KEYWORDS):
        deep += 1
        factors.append("analysis-keyword")
    if any(k in low for k in _FACTUAL_KEYWORDS):
        chat += 2
        factors.append("factual-keyword")
    if len(ir.intent.split()) < 6 and not ir.recency_window and not ir.source_preferences:
        chat += 1
        factors.append("very-short")

    margin = deep - chat
    base = f"deep={deep} chat={chat} ({', '.join(factors) or 'no strong signals'})"

    if margin >= 2:
        return ModeDecision(_DEEP, f"rules: {base}", "rules")
    if margin <= -2:
        return ModeDecision(_CHAT, f"rules: {base}", "rules")

    if model_fallback is not None:
        mode = model_fallback(ir)
        return ModeDecision(mode, f"borderline ({base}) -> model", "model")

    return ModeDecision(_DEEP, f"borderline ({base}); defaulted to deep-research", "default")
