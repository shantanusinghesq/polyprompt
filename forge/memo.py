"""Explanation-memo generation with knowledge-graph frontmatter (PRD FR-4).

A memo pairs the human-readable rationale for a rewrite with machine-readable
frontmatter that M4's knowledge graph ingests. Frontmatter is written as
**JSON-valued lines** between `---` fences: each line is `key: <json>`, so it is
zero-dependency and losslessly round-trippable (see render/parse_frontmatter).

Tags (method / analysis_type / retrieval_type / subject_matter) are derived
deterministically from the IR by keyword heuristics — rough but stable; the
reviewer loop (M6) is where they get corrected.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime

from forge.ir import PromptIR
from forge.rewrite import RewriteResult
from forge.taxonomy import Taxonomy

SCHEMA_VERSION = "1"

_TAG_DIMENSIONS = ("method", "analysis_type", "retrieval_type", "subject_matter")


def prompt_hash(intent: str) -> str:
    return hashlib.sha256(intent.strip().encode("utf-8")).hexdigest()[:16]


def slugify(text: str, max_len: int = 50) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].strip("-") or "prompt"


def derive_tags(ir: PromptIR) -> dict[str, str]:
    """Deterministic tag heuristics over the IR intent. Values are guaranteed to
    be members of the taxonomy's closed enums."""
    low = f" {ir.intent.lower()} "

    if any(k in low for k in ("cost", "price", "tco", "roi", "%", "number", "metric", "how much", "rate")):
        method = "quantitative"
    elif any(k in low for k in ("why", "perspective", "opinion", "qualitative", "experience", "narrative")):
        method = "qualitative"
    else:
        method = "mixed"

    if any(k in low for k in ("compare", "versus", " vs ", "difference")):
        analysis = "comparative"
    elif any(k in low for k in ("why", "cause", "impact", "effect", "because", "lead to")):
        analysis = "causal"
    elif any(k in low for k in ("best", "should", "evaluate", "assess", "pros and cons", "worth")):
        analysis = "evaluative"
    elif any(k in low for k in ("explore", "overview", "landscape", "what is", "introduction")):
        analysis = "exploratory"
    else:
        analysis = "descriptive"

    if any(k in low for k in ("latest", "recent", "news", "track", "monitor", "update", "current")):
        retrieval = "monitoring"
    elif any(k in low for k in ("list", "examples", "options", "enumerate", "all the")):
        retrieval = "enumerative"
    elif any(k in low for k in ("compare", "analyze", "synthesize", "report", "explain", "assess")):
        retrieval = "synthesis"
    else:
        retrieval = "factual-lookup"

    buckets = {
        "energy": ("heat pump", "furnace", "solar", "energy", "grid", "battery", "hvac", "emissions"),
        "technology": ("software", " ai ", "model", "algorithm", "chip", "cloud", "api", "data"),
        "finance": ("cost", "price", "tco", "roi", "invest", "market", "stock", "budget", "tax"),
        "health": ("health", "clinical", "disease", "patient", "medical", "drug"),
        "policy": ("policy", "regulation", "law", "government", "subsidy", "tax credit"),
        "science": ("study", "experiment", "physics", "chemistry", "biology"),
        "business": ("company", "strategy", "customer", "revenue", "product", "startup"),
    }
    subject = "general"
    for name, keywords in buckets.items():
        if any(k in low for k in keywords):
            subject = name
            break

    return {
        "method": method,
        "analysis_type": analysis,
        "retrieval_type": retrieval,
        "subject_matter": subject,
    }


@dataclass
class Memo:
    frontmatter: dict
    body: str
    filename: str

    def to_markdown(self) -> str:
        return render_frontmatter(self.frontmatter) + "\n" + self.body


def render_frontmatter(frontmatter: dict) -> str:
    lines = ["---"]
    lines += [f"{key}: {json.dumps(value)}" for key, value in frontmatter.items()]
    lines.append("---")
    return "\n".join(lines) + "\n"


def parse_frontmatter(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing frontmatter opening fence")
    frontmatter: dict = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return frontmatter
        key, sep, value = line.partition(": ")
        if not sep:
            continue
        frontmatter[key.strip()] = json.loads(value)
    raise ValueError("unterminated frontmatter")


def _render_body(source_prompt: str, ir: PromptIR, result: RewriteResult,
                 taxonomy: Taxonomy, tags: dict[str, str]) -> str:
    lines = [
        f"# Explanation memo — {result.engine} rewrite",
        "",
        f"**Source prompt:** {source_prompt.strip()}",
        "",
        f"**Rewritten for {result.engine}** (mode: {result.mode}, profile {result.profile_version}):",
        "",
        "```",
        result.prompt,
        "```",
        "",
        "## Why these adaptations",
        "",
    ]
    lines += [f"- **{taxonomy.label(t)}** (`{t}`) — {taxonomy.describe(t)}" for t in result.tactics]
    lines += ["", "## Request tags (knowledge-graph associations)", ""]
    lines += [f"- {dim}: {tags[dim]}" for dim in _TAG_DIMENSIONS]
    lines.append("")
    return "\n".join(lines)


def build_memo(source_prompt: str, ir: PromptIR, result: RewriteResult,
               taxonomy: Taxonomy, now: datetime | None = None) -> Memo:
    now = now or datetime.now()
    tags = derive_tags(ir)
    frontmatter = {
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": taxonomy.version,
        "source_prompt_hash": prompt_hash(ir.intent),
        "engine": result.engine,
        "mode": result.mode,
        "profile_version": result.profile_version,
        "tactics": result.tactics,
        "tags": tags,
        "generated_at": now.isoformat(timespec="seconds"),
    }
    body = _render_body(source_prompt, ir, result, taxonomy, tags)
    filename = f"{now.strftime('%Y-%m-%d')}-{slugify(ir.intent)}-{result.engine}.md"
    return Memo(frontmatter=frontmatter, body=body, filename=filename)
