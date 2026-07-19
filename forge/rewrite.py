"""Profile-driven rewriters.

`rewrite(ir, profile)` dispatches on the profile's `structure` to a renderer
that assembles an engine-tuned prompt from the IR. Each renderer returns the
rewritten prompt plus the taxonomy **tactic IDs** it applied. Emitting IDs (not
free-text prose) keeps every rewrite graph-ready and avoids the label drift the
taxonomy decision (scratchpad D-08) was designed to prevent — the human-readable
rationale is looked up from the taxonomy at display / memo time.

M1 is deterministic template assembly — "the profile supplies guardrails" (PRD).
Model-driven phrasing polish is a later refinement. Mode is hardcoded to the
profile's `default_mode` until M3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from forge.ir import PromptIR
from forge.profile import PlatformProfile

_YEAR_RE = re.compile(r"(20\d{2})")


@dataclass
class RewriteResult:
    engine: str
    mode: str
    prompt: str
    tactics: list[str]  # taxonomy tactic IDs applied
    profile_version: str


def _recency_phrase(ir: PromptIR) -> str:
    return ir.recency_window or "no specific time constraint"


def _sources_phrase(ir: PromptIR) -> str:
    return ", ".join(ir.source_preferences) or "authoritative, primary sources where possible"


def _render_role_framed(ir: PromptIR, profile: PlatformProfile) -> tuple[str, list[str]]:
    """ChatGPT — explicit expert role + numbered constraints + structured output."""
    lines = [
        "You are an expert research analyst. Conduct deep research on the task below "
        "and produce a structured, well-cited report.",
        "",
        f"Task: {ir.intent}",
        "",
        "Constraints:",
        f"- Time frame: {_recency_phrase(ir)}",
        f"- Depth: {ir.depth} — {ir.reasoning_layers} layer(s) of analysis",
        f"- Sources: {_sources_phrase(ir)}",
    ]
    lines += [f"- {c}" for c in ir.constraints]
    lines += ["", "Deliverable: a structured report with clear sections, key findings, and inline citations."]
    tactics = ["role-framing", "explicit-constraints", "structured-output", "source-preference", "citation-demand"]
    return "\n".join(lines), tactics


def _render_research_plan(ir: PromptIR, profile: PlatformProfile) -> tuple[str, list[str]]:
    """Gemini — approvable research plan first, then breadth-first execution."""
    lines = [
        f"Research task: {ir.intent}",
        "",
        "First outline a brief research plan — the areas you'll investigate and the "
        "source types you'll consult — then carry it out.",
        "",
        "Scope:",
        f"- Recency: {_recency_phrase(ir)}",
        f"- Analytical depth: {ir.depth} ({ir.reasoning_layers} layer(s))",
        "- Breadth: survey multiple perspectives and source types",
        f"- Sources: {_sources_phrase(ir)}",
    ]
    lines += [f"- {c}" for c in ir.constraints]
    lines += ["", "Output: a comprehensive, well-organized synthesis with citations."]
    tactics = ["research-plan", "breadth-directive", "source-preference", "citation-demand"]
    return "\n".join(lines), tactics


def _render_xml_sections(ir: PromptIR, profile: PlatformProfile) -> tuple[str, list[str]]:
    """Claude — XML-delimited sections + explicit reasoning + faithfulness."""
    parts = [
        "<task>",
        ir.intent,
        "</task>",
        "",
        "<constraints>",
        f"- recency: {_recency_phrase(ir)}",
        f"- depth: {ir.depth} — reason through {ir.reasoning_layers} layer(s) before concluding",
        f"- sources: {_sources_phrase(ir)}",
    ]
    parts += [f"- {c}" for c in ir.constraints]
    parts += [
        "</constraints>",
        "",
        "<instructions>",
        "Research thoroughly, reason step by step, and synthesize a faithful, well-cited "
        "answer. Flag uncertainty explicitly rather than guessing.",
        "</instructions>",
    ]
    tactics = ["xml-structure", "reasoning-depth", "uncertainty-flagging", "source-preference", "citation-demand"]
    return "\n".join(parts), tactics


def _render_concise_query(ir: PromptIR, profile: PlatformProfile) -> tuple[str, list[str]]:
    """Perplexity — concise keyword query + source/recency operators + citations."""
    tail = [f"Prefer {_sources_phrase(ir)}"]
    match = _YEAR_RE.search(ir.recency_window or "")
    if match and any(op.startswith("after:") for op in profile.source_filter_syntax):
        tail.append(f"after:{int(match.group(1)) - 1}")
    elif ir.recency_window:
        tail.append(f"recency {ir.recency_window}")
    tail.append("Cite sources")
    text = f"{ir.intent.rstrip('.')}. " + ". ".join(tail) + "."
    tactics = ["concise-query", "source-filter-operators", "source-preference", "citation-demand"]
    return text, tactics


_RENDERERS = {
    "role-framed": _render_role_framed,
    "research-plan": _render_research_plan,
    "xml-sections": _render_xml_sections,
    "concise-query": _render_concise_query,
}


def rewrite(ir: PromptIR, profile: PlatformProfile) -> RewriteResult:
    renderer = _RENDERERS.get(profile.structure)
    if renderer is None:
        raise ValueError(f"no renderer for structure: {profile.structure!r}")
    text, tactics = renderer(ir, profile)

    # Conditional tactics that depend on the IR content, applied uniformly.
    if ir.recency_window and "recency-constraint" not in tactics:
        tactics = [*tactics, "recency-constraint"]
    if ir.constraints and "disambiguation" not in tactics:
        tactics = [*tactics, "disambiguation"]

    return RewriteResult(
        engine=profile.engine,
        mode=profile.default_mode,
        prompt=text,
        tactics=tactics,
        profile_version=profile.version,
    )
