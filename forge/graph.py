"""Knowledge graph — git-native flat JSON edge-list (PRD Q1/Q4; M4).

Edges associate a taxonomy tactic with a (dimension, value) tag. Each edge
carries (pos, neg) label counts and a provenance marker. Weight is the Wilson
score lower bound of pos/(pos+neg): a promotion needs both support >= K_MIN
and weight >= THETA_HIGH before a tactic counts as *required* for a tag.

Cold start is an a-priori seed (provenance "seed") derived from the taxonomy
and vendor-doc expectations. Seed edges carry zero counts, so they can never
clear the support gate — seeds are structure, never labels
(poc-to-v1-graduation-criteria.md).

Memo ingest treats each saved memo as one positive observation per
tactic <-> tag pair, deduped on (source_prompt_hash, engine) so re-forging the
same prompt never double-counts. Reviewer labels (M6) will add negatives.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from forge.memo import parse_frontmatter
from forge.taxonomy import Taxonomy

K_MIN = 5  # minimum label support before an edge can promote
THETA_HIGH = 0.7  # Wilson lower bound needed to promote to required

_TAG_DIMENSIONS = ("method", "analysis_type", "retrieval_type", "subject_matter")

# A-priori tactic expectations per tag (dimension, value, tactics). These seed
# the graph's structure on cold start; they never contribute label counts.
SEED_ASSOCIATIONS: list[tuple[str, str, list[str]]] = [
    ("engine", "chatgpt", ["role-framing", "explicit-constraints", "structured-output"]),
    ("engine", "gemini", ["breadth-directive", "structured-output"]),
    ("engine", "claude", ["xml-structure", "uncertainty-flagging"]),
    ("engine", "perplexity", ["concise-query", "source-filter-operators"]),
    ("mode", "deep-research", ["research-plan", "citation-demand", "breadth-directive"]),
    ("mode", "chat", ["length-target"]),
    ("retrieval_type", "factual-lookup", ["concise-query"]),
    ("retrieval_type", "monitoring", ["recency-constraint"]),
    ("analysis_type", "comparative", ["decomposition"]),
]


def wilson_lower_bound(pos: int, n: int, z: float = 1.96) -> float:
    """Lower bound of the Wilson score interval for pos successes in n trials."""
    if n == 0:
        return 0.0
    phat = pos / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (centre - margin) / denom


@dataclass
class Edge:
    tactic: str
    dimension: str
    value: str
    pos: int = 0
    neg: int = 0
    provenance: str = "label"  # "seed" | "label"

    @property
    def support(self) -> int:
        return self.pos + self.neg

    @property
    def weight(self) -> float:
        return wilson_lower_bound(self.pos, self.support)

    @property
    def promoted(self) -> bool:
        return self.support >= K_MIN and self.weight >= THETA_HIGH


EdgeKey = tuple[str, str, str]  # (tactic, dimension, value)


@dataclass
class Graph:
    taxonomy_version: str
    edges: dict[EdgeKey, Edge] = field(default_factory=dict)
    ingested: set[tuple[str, str]] = field(default_factory=set)  # (hash, engine)

    def _edge(self, tactic: str, dimension: str, value: str, provenance: str) -> Edge:
        key = (tactic, dimension, value)
        if key not in self.edges:
            self.edges[key] = Edge(
                tactic=tactic, dimension=dimension, value=value, provenance=provenance
            )
        return self.edges[key]

    def add_label(self, tactic: str, dimension: str, value: str,
                  positive: bool = True) -> Edge:
        edge = self._edge(tactic, dimension, value, provenance="label")
        if positive:
            edge.pos += 1
        else:
            edge.neg += 1
        return edge

    def ingest_memo(self, frontmatter: dict) -> bool:
        """Count one memo as a positive observation per tactic <-> tag pair.

        Returns False (no-op) if this (source_prompt_hash, engine) was already
        ingested.
        """
        key = (frontmatter["source_prompt_hash"], frontmatter["engine"])
        if key in self.ingested:
            return False
        tags = dict(frontmatter.get("tags", {}))
        tags["engine"] = frontmatter["engine"]
        tags["mode"] = frontmatter["mode"]
        for tactic in frontmatter.get("tactics", []):
            for dimension, value in tags.items():
                self.add_label(tactic, dimension, value)
        self.ingested.add(key)
        return True

    def required_tactics(self, tags: dict[str, str]) -> dict[str, Edge]:
        """Tactics whose edge to any of the given tags has promoted
        (support >= K_MIN and Wilson-LB >= THETA_HIGH). Seed edges carry zero
        counts and therefore never appear here."""
        required: dict[str, Edge] = {}
        for edge in self.edges.values():
            if tags.get(edge.dimension) != edge.value or not edge.promoted:
                continue
            current = required.get(edge.tactic)
            if current is None or edge.weight > current.weight:
                required[edge.tactic] = edge
        return required


def seed_graph(taxonomy: Taxonomy) -> Graph:
    """Cold-start graph from the a-priori seed associations, filtered against
    the taxonomy so a stale seed entry can never introduce an invalid node."""
    graph = Graph(taxonomy_version=taxonomy.version)
    for dimension, value, tactics in SEED_ASSOCIATIONS:
        if not taxonomy.valid_tag(dimension, value):
            continue
        for tactic in tactics:
            if tactic in taxonomy.tactic_ids():
                graph._edge(tactic, dimension, value, provenance="seed")
    return graph


def ingest_directory(graph: Graph, directory: Path | str) -> int:
    """Ingest every parseable memo in a directory. Returns the number of memos
    newly counted (unparseable files and duplicates are skipped)."""
    directory = Path(directory)
    count = 0
    if not directory.exists():
        return count
    for path in sorted(directory.glob("*.md")):
        try:
            frontmatter = parse_frontmatter(path.read_text())
        except ValueError:
            continue
        if graph.ingest_memo(frontmatter):
            count += 1
    return count


def save_graph(graph: Graph, path: Path | str) -> None:
    payload = {
        "schema_version": "1",
        "taxonomy_version": graph.taxonomy_version,
        "ingested": sorted(list(k) for k in graph.ingested),
        "edges": [
            {
                "tactic": e.tactic,
                "dimension": e.dimension,
                "value": e.value,
                "pos": e.pos,
                "neg": e.neg,
                "provenance": e.provenance,
            }
            for e in sorted(
                graph.edges.values(), key=lambda e: (e.tactic, e.dimension, e.value)
            )
        ],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def load_graph(path: Path | str) -> Graph:
    data = json.loads(Path(path).read_text())
    graph = Graph(taxonomy_version=data["taxonomy_version"])
    graph.ingested = {(h, engine) for h, engine in data.get("ingested", [])}
    for entry in data.get("edges", []):
        key = (entry["tactic"], entry["dimension"], entry["value"])
        graph.edges[key] = Edge(**entry)
    return graph
