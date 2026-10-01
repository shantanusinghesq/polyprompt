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

from polyprompt.ir import PromptIR
from polyprompt.mode import ModeDecision
from polyprompt.profile import PlatformProfile

_YEAR_RE = re.compile(r"(20\d{2})")


@dataclass
class RewriteResult:
    engine: str
    mode: str
    prompt: str
    tactics: list[str]  # taxonomy tactic IDs applied
    profile_version: str
    mode_source: str = "default"  # "rules" | "model" | "default" | "forced"
    mode_reason: str = "profile default (no detection)"


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


# Retrieval-stage helpers (Perplexity). A RAG engine embeds and keyword-matches
# the query BEFORE any generation, so narrative prose and asserted premises
# steer which documents come back, not merely how the answer reads.

_ASK_RE = re.compile(
    r"\b(what|how|which|why|who|whom|whose|compare|identify|list)\b", re.I
)
_SENT_RE = re.compile(r"(?<=[.?!])\s+")

# "where"/"when" are omitted above on purpose: in prose they are usually
# relativisers ("an exercise WHERE third parties were breached"), so including
# them misclassifies declarative premises as asks. The survivors still relativise
# after a preposition ("an exercise IN WHICH ...", "the basis ON WHICH ..."), so
# a marker is only an ask when it does not directly follow one.
_PREPOSITIONS = frozenset(
    """in of for to at by with on from after before during through under over
    into about against within across""".split()
)


def _is_ask(sentence: str) -> bool:
    """True when the sentence asks something, rather than merely relativising."""
    for match in _ASK_RE.finditer(sentence):
        preceding = re.findall(r"[A-Za-z']+", sentence[: match.start()])
        if not preceding or preceding[-1].lower() not in _PREPOSITIONS:
            return True
    return False

_STOPWORDS = frozenset(
    """a an the and or but of for to in on at by with from as is are was were be been
    being that this these those it its their there here all any both each few more most
    other some such no nor not only own same so than too very can will just should now
    do does did have has had they them he she his her you your we our i me my if then
    else while about across after before during over under between into respective like
    topics thing things etc""".split()
)


def _compress(text: str, seed: list[str], keep: int = 30) -> str:
    """Deterministic keyword compression: drop stopwords, dedupe, cap length.

    `seed` terms are pre-marked as seen so an entity prefix is not repeated.
    """
    seen = {
        word.lower()
        for item in seed
        for word in re.findall(r"[A-Za-z][A-Za-z0-9\-']+", item)
    }
    out: list[str] = []
    for raw in re.findall(r"[A-Za-z][A-Za-z0-9\-']+", text):
        word = raw.lower()
        if word in _STOPWORDS or len(word) < 3 or word in seen:
            continue
        seen.add(word)
        out.append(raw)
        if len(out) >= keep:
            break
    return " ".join(out)


def _clip(text: str, limit: int = 260) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat.rstrip(".")
    return flat[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "..."


def _split_ask_vs_premise(core: str) -> tuple[list[str], list[str]]:
    """Separate the questions from the declarative framing.

    Sentences carrying an ask-marker build the retrieval lead; declaratives are
    demoted to a claim-to-verify line. If nothing parses as an ask, fall back to
    the whole prompt as the lead and demote nothing.
    """
    sentences = [s.strip() for s in _SENT_RE.split(core) if s.strip()]
    ask = [s for s in sentences if _is_ask(s)]
    if not ask:
        return sentences, []
    return ask, [s for s in sentences if not _is_ask(s)]


def _site_operators(ir: PromptIR, profile: PlatformProfile) -> str:
    if not any(op.startswith("site:") for op in profile.source_filter_syntax):
        return ""
    domains = [d for e in ir.entities for d in profile.site_map.get(e, [])]
    if not domains:
        return ""
    return " OR ".join(f"site:{d}" for d in dict.fromkeys(domains))


def _render_concise_query(ir: PromptIR, profile: PlatformProfile) -> tuple[str, list[str]]:
    """Perplexity — retrieval-first: keyword lead, operators, demoted premise.

    Unlike the three chat renderers, this one must survive a retrieval stage.
    It therefore (a) leads with the compressed *asks* plus canonical entities,
    (b) scopes first-party claims with site:, (c) demotes declarative premises
    out of the lead, and (d) asks for per-entity decomposition, because one
    embedding cannot represent several sub-questions at once.
    """
    tactics = ["concise-query", "source-filter-operators", "source-preference",
               "citation-demand"]
    ask, premise = _split_ask_vs_premise(ir.intent)

    operators: list[str] = []
    match = _YEAR_RE.search(ir.recency_window or "")
    if match and any(op.startswith("after:") for op in profile.source_filter_syntax):
        operators.append(f"after:{int(match.group(1)) - 1}")
    elif ir.recency_window:
        operators.append(f"recency {ir.recency_window}")

    lead = " ".join(
        part
        for part in (
            " ".join(ir.entities),
            _compress(" ".join(ask), seed=ir.entities),
            " ".join(operators),
        )
        if part
    )
    blocks = [lead]

    sites = _site_operators(ir, profile)
    if sites:
        tactics.append("entity-site-scoping")
        scoped = f"First-party check: ({sites})"
        if operators:
            scoped = f"{scoped} {' '.join(operators)}"
        blocks.append(scoped)

    if premise:
        tactics.append("premise-demotion")
        blocks.append("Claim to verify, do not assume true: " + _clip(" ".join(premise)))

    if ir.constraints:
        tactics.append("disambiguation")
        blocks.append("Constraint: " + _clip(ir.constraints[0]))

    if len(ir.entities) > 1:
        tactics.append("decomposition")
        blocks.append("Search each separately: " + "; ".join(ir.entities) + ".")

    blocks.append(f"Prefer {_sources_phrase(ir)}. Cite sources.")
    return "\n".join(blocks), tactics


_RENDERERS = {
    "role-framed": _render_role_framed,
    "research-plan": _render_research_plan,
    "xml-sections": _render_xml_sections,
    "concise-query": _render_concise_query,
}


def rewrite(
    ir: PromptIR,
    profile: PlatformProfile,
    mode_decision: ModeDecision | None = None,
) -> RewriteResult:
    renderer = _RENDERERS.get(profile.structure)
    if renderer is None:
        raise ValueError(f"no renderer for structure: {profile.structure!r}")
    text, tactics = renderer(ir, profile)

    # Conditional tactics that depend on the IR content, applied uniformly.
    if ir.recency_window and "recency-constraint" not in tactics:
        tactics = [*tactics, "recency-constraint"]
    if ir.constraints and "disambiguation" not in tactics:
        tactics = [*tactics, "disambiguation"]

    if mode_decision is not None:
        mode = mode_decision.mode
        mode_source = mode_decision.source
        mode_reason = mode_decision.reason
    else:
        mode = profile.default_mode
        mode_source = "default"
        mode_reason = "profile default (no detection)"

    return RewriteResult(
        engine=profile.engine,
        mode=mode,
        prompt=text,
        tactics=tactics,
        profile_version=profile.version,
        mode_source=mode_source,
        mode_reason=mode_reason,
    )
