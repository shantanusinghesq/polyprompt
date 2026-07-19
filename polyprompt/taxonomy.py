"""Taxonomy loader — the controlled vocabulary of prompt-optimization tactics
and the closed tag dimensions (PRD decision 2; scratchpad D-08).

Two layers:
  - tactics: the "how" (id -> label + description); a curated seed grown only
    via reviewer-gated promotion.
  - tag_dimensions: the "when" (closed enums the memo tags must draw from).

This vocabulary is the contract M4's knowledge graph ingests, so renderer
tactic IDs and derived tags are validated against it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_TAXONOMY_PATH = Path(__file__).parent / "taxonomy.v1.json"


@dataclass
class Taxonomy:
    version: str
    tactics: dict[str, dict]  # id -> {"label", "description"}
    tag_dimensions: dict[str, list[str]]

    def tactic_ids(self) -> set[str]:
        return set(self.tactics)

    def label(self, tactic_id: str) -> str:
        entry = self.tactics.get(tactic_id)
        return entry["label"] if entry else tactic_id

    def describe(self, tactic_id: str) -> str:
        entry = self.tactics.get(tactic_id)
        return entry["description"] if entry else ""

    def valid_tag(self, dimension: str, value: str) -> bool:
        return value in self.tag_dimensions.get(dimension, [])


def load_taxonomy() -> Taxonomy:
    data = json.loads(_TAXONOMY_PATH.read_text())
    tactics = {
        t["id"]: {"label": t["label"], "description": t["description"]}
        for t in data["tactics"]
    }
    return Taxonomy(
        version=data["version"],
        tactics=tactics,
        tag_dimensions=data["tag_dimensions"],
    )
