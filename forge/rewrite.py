"""Profile-driven rewriters.

`rewrite(ir, profile)` dispatches on the profile's `structure` to a renderer
that assembles an engine-tuned prompt from the IR. Each renderer returns the
rewritten prompt plus the list of adaptations it applied (which becomes the
on-screen change summary now, and feeds the M2 explanation memo later).

M1 is deterministic template assembly — "the profile supplies guardrails"
(PRD). Model-driven phrasing polish ("the model fills phrasing") is a later
refinement; keeping M1 deterministic preserves the golden-fixture test gate.
Mode is hardcoded to the profile's `default_mode` until M3.
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
    adaptations: list[str]
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
    adaptations = [
        "Framed with an explicit expert role (ChatGPT responds to role priming)",
        "Converted requirements into a numbered constraint block",
        "Requested a structured, citation-bearing deliverable",
    ]
    return "\n".join(lines), adaptations


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
    adaptations = [
        "Prefaced with an approvable research-plan step (Gemini Deep Research surfaces a plan)",
        "Emphasized breadth across perspectives and source types",
        "Kept recency and depth explicit for the plan to honor",
    ]
    return "\n".join(lines), adaptations


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
    adaptations = [
        "Structured with XML-style tags (Claude parses delimited sections reliably)",
        "Added an explicit step-by-step reasoning + faithfulness instruction",
        "Requested explicit uncertainty flagging",
    ]
    return "\n".join(parts), adaptations


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
    adaptations = [
        "Compressed to a concise, keyword-forward query (Perplexity favors search-style phrasing)",
        "Appended source-preference and recency operators",
        "Requested inline citations",
    ]
    return text, adaptations


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
    text, adaptations = renderer(ir, profile)
    return RewriteResult(
        engine=profile.engine,
        mode=profile.default_mode,
        prompt=text,
        adaptations=adaptations,
        profile_version=profile.version,
    )
