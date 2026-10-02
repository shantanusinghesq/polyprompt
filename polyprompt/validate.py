"""Advisory rewrite validation against the knowledge graph (M4).

For a run's tags, the graph names the tactics that history says should be
present (promoted edges). Any of those missing from the applied tactic list
becomes a Flag. Validation is ADVISORY by design (PRD Q4): it informs the
output, never changes it and never blocks — callers must not branch exit
codes on flags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from polyprompt.graph import Graph

# Textual signatures for tactics whose presence is checkable in the rendered
# prompt. A tactic ID in the applied list with no matching signature in the text
# is a provenance defect: the ledger claims a tactic the prompt does not carry,
# which would otherwise be ingested as positive evidence. Tactics absent from
# this map are not checked (no reliable single signature).
_EVIDENCE = {
    "citation-demand": re.compile(r"cite|citation", re.I),
    "source-filter-operators": re.compile(r"\b(site:|filetype:|after:|before:)", re.I),
    "entity-site-scoping": re.compile(r"\bsite:", re.I),
    "premise-demotion": re.compile(r"claim to verify", re.I),
    "decomposition": re.compile(r"separately|decompos|one per", re.I),
    "xml-structure": re.compile(r"<task>|<constraints>", re.I),
    "role-framing": re.compile(r"you are an?\b", re.I),
    "research-plan": re.compile(r"research plan|outline a .*plan", re.I),
    "uncertainty-flagging": re.compile(r"uncertain", re.I),
    "recency-constraint": re.compile(r"after:|before:|recency|time frame", re.I),
}


@dataclass
class Flag:
    tactic: str
    dimension: str
    value: str
    weight: float
    support: int
    message: str
    severity: str = "advisory"


def _content_present(prompt: str, text: str, probe_chars: int = 40) -> bool:
    """Is `text` actually in `prompt`? Probes a prefix, since renderers clip."""
    flat_prompt = " ".join(prompt.split()).lower()
    probe = " ".join(text.split())[:probe_chars].lower()
    return bool(probe) and probe in flat_prompt


def validate(applied_tactics: list[str], tags: dict[str, str],
             graph: Graph, prompt: str = "",
             constraints: list[str] | None = None) -> list[Flag]:
    """Flag tactic/rewrite mismatches. Never raises, never blocks.

    Two checks:
      - under-application: a promoted tactic the rewrite did not apply;
      - over-claiming: an applied tactic ID with no trace in the rendered text.
    """
    applied = set(applied_tactics)
    flags = []
    if prompt:
        missing_text = []
        if "disambiguation" in applied and constraints:
            if not any(_content_present(prompt, c) for c in constraints):
                missing_text.append("disambiguation")
        for tactic in sorted(applied):
            probe = _EVIDENCE.get(tactic)
            absent = (probe is not None and not probe.search(prompt)) or tactic in missing_text
            if absent:
                flags.append(
                    Flag(
                        tactic=tactic,
                        dimension="provenance",
                        value=tags.get("engine", ""),
                        weight=0.0,
                        support=0,
                        message=(
                            f"provenance: '{tactic}' is in the applied list but no "
                            "trace of it appears in the rendered prompt"
                        ),
                        severity="provenance",
                    )
                )
    for tactic, edge in sorted(graph.required_tactics(tags).items()):
        if tactic in applied:
            continue
        flags.append(
            Flag(
                tactic=tactic,
                dimension=edge.dimension,
                value=edge.value,
                weight=edge.weight,
                support=edge.support,
                message=(
                    f"advisory: '{tactic}' is expected for "
                    f"{edge.dimension}={edge.value} "
                    f"(weight {edge.weight:.2f}, support {edge.support}) "
                    "but was not applied"
                ),
            )
        )
    return flags
