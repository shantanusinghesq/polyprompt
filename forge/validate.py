"""Advisory rewrite validation against the knowledge graph (M4).

For a run's tags, the graph names the tactics that history says should be
present (promoted edges). Any of those missing from the applied tactic list
becomes a Flag. Validation is ADVISORY by design (PRD Q4): it informs the
output, never changes it and never blocks — callers must not branch exit
codes on flags.
"""

from __future__ import annotations

from dataclasses import dataclass

from forge.graph import Graph


@dataclass
class Flag:
    tactic: str
    dimension: str
    value: str
    weight: float
    support: int
    message: str
    severity: str = "advisory"


def validate(applied_tactics: list[str], tags: dict[str, str],
             graph: Graph) -> list[Flag]:
    """Flag promoted tactics missing from a rewrite. Never raises, never blocks."""
    applied = set(applied_tactics)
    flags = []
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
