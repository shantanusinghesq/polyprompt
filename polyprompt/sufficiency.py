"""Sufficiency gate — should ingest run? (docs/scratchpad-memo-sufficiency-gate.md)

Pure, read-only assessment of whether the memos on disk hold enough *new,
non-redundant* evidence to justify updating the knowledge graph:

  1. Pending scan — memos not yet in graph.ingested (dedupe is the base gate).
  2. Promotion simulation (D-02) — pending labels are applied to a deepcopy of
     the graph; the gate fires only if the promoted set changes.
  3. Diversity veto (D-02 / RA-02) — a newly promotable edge needs evidence
     from >= DIVERSITY_MIN distinct prompt hashes; Wilson handles volume, not
     provenance diversity. Diversity is recomputed from the memo files at
     assess time (CoVE-01: the graph keeps no per-edge hash bookkeeping).
  4. Triage (D-03) — PROMOTE-READY / CONTESTED / NEEDS-MORE / DORMANT.
     Advisory only: CONTESTED annotates, never blocks (AA-03).

`sufficient` = a promotion is available OR pending memos >= MIN_PENDING_MEMOS
(hysteresis pre-check). assess() never mutates the graph — ingest stays the
single mutator (RA-04).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

from polyprompt.graph import K_MIN, EdgeKey, Graph
from polyprompt.memo import parse_frontmatter

MIN_PENDING_MEMOS = 3  # hysteresis: this many new memos is worth an ingest anyway
DIVERSITY_MIN = 3  # distinct prompt hashes required before a promotion counts

_REQUIRED_KEYS = ("source_prompt_hash", "engine", "mode", "tactics", "tags")


@dataclass
class Report:
    pending_memos: int
    pending_labels: int
    would_promote: list[EdgeKey]
    vetoed: list[EdgeKey]  # would promote, but under the diversity floor
    buckets: dict[str, list[EdgeKey]] = field(default_factory=dict)

    @property
    def sufficient(self) -> bool:
        return bool(self.would_promote) or self.pending_memos >= MIN_PENDING_MEMOS


def _scan_memos(directory: Path) -> list[dict]:
    """Parse every memo frontmatter in a directory, deduped on (hash, engine).
    Files without the full memo contract are skipped."""
    seen: set[tuple[str, str]] = set()
    frontmatters = []
    if not directory.exists():
        return frontmatters
    for path in sorted(directory.glob("*.md")):
        try:
            fm = parse_frontmatter(path.read_text())
        except ValueError:
            continue
        if any(k not in fm for k in _REQUIRED_KEYS):
            continue
        key = (fm["source_prompt_hash"], fm["engine"])
        if key in seen:
            continue
        seen.add(key)
        frontmatters.append(fm)
    return frontmatters


def _edges_touched(fm: dict) -> set[EdgeKey]:
    tags = dict(fm["tags"])
    tags["engine"] = fm["engine"]
    tags["mode"] = fm["mode"]
    return {
        (tactic, dimension, value)
        for tactic in fm["tactics"]
        for dimension, value in tags.items()
    }


def assess(memos_dir: Path | str, graph: Graph,
           diversity_min: int = DIVERSITY_MIN) -> Report:
    """Read-only sufficiency assessment. Never mutates `graph`."""
    memos_dir = Path(memos_dir)
    frontmatters = _scan_memos(memos_dir)
    pending = [
        fm for fm in frontmatters
        if (fm["source_prompt_hash"], fm["engine"]) not in graph.ingested
    ]
    pending_labels = sum(len(_edges_touched(fm)) for fm in pending)

    # Simulation: what would the promoted set look like after ingest?
    sim = copy.deepcopy(graph)
    for fm in pending:
        sim.ingest_memo(fm)
    before = {k for k, e in graph.edges.items() if e.promoted}
    after = {k for k, e in sim.edges.items() if e.promoted}
    newly = after - before

    # Diversity: distinct prompt hashes contributing to each edge, from files.
    hashes_per_edge: dict[EdgeKey, set[str]] = {}
    for fm in frontmatters:
        for key in _edges_touched(fm):
            hashes_per_edge.setdefault(key, set()).add(fm["source_prompt_hash"])
    would_promote = sorted(
        k for k in newly if len(hashes_per_edge.get(k, ())) >= diversity_min
    )
    vetoed = sorted(newly - set(would_promote))

    # Triage over the post-simulation view (advisory only, D-03).
    buckets: dict[str, list[EdgeKey]] = {
        "PROMOTE-READY": would_promote,
        "CONTESTED": [],
        "NEEDS-MORE": list(vetoed),
        "DORMANT": [],
    }
    for key, edge in sorted(sim.edges.items()):
        if key in newly or edge.status != "active":
            continue
        if edge.support == 0:
            buckets["DORMANT"].append(key)
        elif edge.support < K_MIN:
            buckets["NEEDS-MORE"].append(key)
        elif not edge.promoted and not edge.contra and edge.neg > 0:
            buckets["CONTESTED"].append(key)

    return Report(
        pending_memos=len(pending),
        pending_labels=pending_labels,
        would_promote=would_promote,
        vetoed=vetoed,
        buckets=buckets,
    )
