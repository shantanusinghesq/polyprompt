"""Deterministic, mode-aware prompt rendering with traceable tactic IDs.

User constraints, exact recency windows, exclusions, and requested output
formats survive every renderer. XML escaping protects section structure;
it is not a claim that prompt injection is solved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from html import escape

from polyprompt.ir import PromptIR
from polyprompt.mode import ModeDecision
from polyprompt.profile import PlatformProfile

_YEAR_RE = re.compile(r"(20\d{2})\+")


@dataclass
class RewriteResult:
    engine: str
    mode: str
    prompt: str
    tactics: list[str]
    profile_version: str
    mode_source: str = "default"
    mode_reason: str = "profile default (no detection)"


def _recency_phrase(ir: PromptIR) -> str:
    return ir.recency_window or "no specific time constraint"


def _sources_phrase(ir: PromptIR) -> str:
    return ", ".join(ir.source_preferences) or "authoritative, primary sources where possible"


def _render_role_framed(ir: PromptIR, profile: PlatformProfile,
                        mode: str = "deep-research") -> tuple[str, list[str]]:
    chat = mode == "chat"
    lines = [
        ("You are an expert research analyst. Answer the task directly and concisely."
         if chat else "You are an expert research analyst. Conduct deep research on the task below "
         "and produce a structured, well-cited report."),
        "", f"Task: {ir.intent}", "", "Constraints:",
        f"- Time frame: {_recency_phrase(ir)}",
        f"- Depth: {ir.depth} — {ir.reasoning_layers} layer(s) of analysis",
        f"- Sources: {_sources_phrase(ir)}",
    ]
    lines += [f"- {c}" for c in ir.constraints]
    deliverable = (ir.output_format or
                   ("a concise answer with inline citations where needed" if chat else
                    "a structured report with clear sections, key findings, and inline citations"))
    lines += ["", f"Deliverable: {deliverable}."]
    tactics = ["role-framing", "explicit-constraints", "structured-output", "source-preference", "citation-demand"]
    return "\n".join(lines), tactics


def _render_research_plan(ir: PromptIR, profile: PlatformProfile,
                          mode: str = "deep-research") -> tuple[str, list[str]]:
    chat = mode == "chat"
    lines = [f"Research task: {ir.intent}", "",
             ("Answer directly and concisely; no separate research-plan phase is needed."
              if chat else "First outline a brief research plan — the areas you'll investigate and the "
              "source types you'll consult — then carry it out."),
             "", "Scope:", f"- Recency: {_recency_phrase(ir)}",
             f"- Analytical depth: {ir.depth} ({ir.reasoning_layers} layer(s))"]
    if not chat:
        lines.append("- Breadth: survey multiple perspectives and source types")
    lines.append(f"- Sources: {_sources_phrase(ir)}")
    lines += [f"- {c}" for c in ir.constraints]
    output = ir.output_format or ("a concise answer with citations" if chat else
                                  "a comprehensive, well-organized synthesis with citations")
    lines += ["", f"Output: {output}."]
    tactics = (["structured-output"] if chat else ["research-plan", "breadth-directive"])
    tactics += ["source-preference", "citation-demand"]
    return "\n".join(lines), tactics


def _render_xml_sections(ir: PromptIR, profile: PlatformProfile,
                         mode: str = "deep-research") -> tuple[str, list[str]]:
    parts = ["<task>", escape(ir.intent, quote=False), "</task>", "", "<constraints>",
             f"- recency: {escape(_recency_phrase(ir), quote=False)}",
             f"- depth: {escape(ir.depth, quote=False)} — reason through {ir.reasoning_layers} layer(s) before concluding",
             f"- sources: {escape(_sources_phrase(ir), quote=False)}"]
    parts += [f"- {escape(c, quote=False)}" for c in ir.constraints]
    instruction = ("Answer directly and concisely with citations where needed. Flag uncertainty explicitly "
                   "rather than guessing." if mode == "chat" else
                   "Research thoroughly, reason step by step, and synthesize a faithful, well-cited "
                   "answer. Flag uncertainty explicitly rather than guessing.")
    parts += ["</constraints>", "", "<instructions>", instruction, "</instructions>"]
    tactics = ["xml-structure", "reasoning-depth", "uncertainty-flagging", "source-preference", "citation-demand"]
    return "\n".join(parts), tactics


def _render_concise_query(ir: PromptIR, profile: PlatformProfile,
                          mode: str = "deep-research") -> tuple[str, list[str]]:
    tail = [f"Prefer {_sources_phrase(ir)}"]
    tactics = ["concise-query", "source-preference", "citation-demand"]
    if ir.recency_window:
        tail.append(f"recency {ir.recency_window}")
        match = _YEAR_RE.fullmatch(ir.recency_window.strip())
        if match and any(op.startswith("after:") for op in profile.source_filter_syntax):
            tail.append(f"after:{int(match.group(1)) - 1}")
            tactics.append("source-filter-operators")
    tail.append(f"Depth: {ir.depth} ({ir.reasoning_layers} layer(s))")
    tail.extend(ir.constraints)
    if mode == "chat":
        tail.append("Answer concisely")
    tail.append("Cite sources")
    return f"{ir.intent.rstrip('.')}. " + ". ".join(tail) + ".", tactics


_RENDERERS = {
    "role-framed": _render_role_framed,
    "research-plan": _render_research_plan,
    "xml-sections": _render_xml_sections,
    "concise-query": _render_concise_query,
}


def rewrite(ir: PromptIR, profile: PlatformProfile,
            mode_decision: ModeDecision | None = None) -> RewriteResult:
    if mode_decision is not None:
        mode, source, reason = mode_decision.mode, mode_decision.source, mode_decision.reason
    else:
        mode, source, reason = profile.default_mode, "default", "profile default (no detection)"
    if mode not in ("chat", "deep-research"):
        raise ValueError(f"unsupported mode: {mode!r}")
    renderer = _RENDERERS.get(profile.structure)
    if renderer is None:
        raise ValueError(f"no renderer for structure: {profile.structure!r}")
    constraints = [*ir.constraints, *(f"Exclude: {e}" for e in ir.exclusions)]
    if ir.output_format:
        constraints.append(f"Output format: {ir.output_format}")
    render_ir = replace(ir, constraints=constraints)
    text, tactics = renderer(render_ir, profile, mode)
    if ir.recency_window:
        tactics.append("recency-constraint")
    if ir.constraints:
        tactics.append("disambiguation")
    if mode == "chat":
        tactics.append("length-target")
    return RewriteResult(engine=profile.engine, mode=mode, prompt=text,
                         tactics=list(dict.fromkeys(tactics)), profile_version=profile.version,
                         mode_source=source, mode_reason=reason)
