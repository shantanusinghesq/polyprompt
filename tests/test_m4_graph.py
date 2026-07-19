"""M4 — knowledge graph: edge-list, seeding, memo ingest, Wilson-LB weighting."""

import pytest

from polyprompt.graph import (
    K_MIN,
    THETA_HIGH,
    Graph,
    ingest_directory,
    load_graph,
    save_graph,
    seed_graph,
    wilson_lower_bound,
)
from polyprompt.memo import render_frontmatter
from polyprompt.taxonomy import load_taxonomy


def make_frontmatter(**overrides):
    fm = {
        "schema_version": "1",
        "taxonomy_version": "v1",
        "source_prompt_hash": "abc123def4567890",
        "engine": "chatgpt",
        "mode": "deep-research",
        "mode_source": "rules",
        "mode_reason": "test",
        "profile_version": "1",
        "tactics": ["role-framing", "citation-demand"],
        "tags": {
            "method": "mixed",
            "analysis_type": "descriptive",
            "retrieval_type": "synthesis",
            "subject_matter": "general",
        },
        "generated_at": "2026-07-19T00:00:00",
    }
    fm.update(overrides)
    return fm


class TestWilsonLowerBound:
    def test_zero_support_is_zero(self):
        assert wilson_lower_bound(0, 0) == 0.0

    def test_ten_of_ten_clears_theta(self):
        assert wilson_lower_bound(10, 10) == pytest.approx(0.7225, abs=1e-3)
        assert wilson_lower_bound(10, 10) >= THETA_HIGH

    def test_five_of_five_below_theta(self):
        assert wilson_lower_bound(5, 5) < THETA_HIGH

    def test_negatives_lower_the_bound(self):
        assert wilson_lower_bound(10, 15) < wilson_lower_bound(10, 10)


class TestSeedGraph:
    def test_seed_edges_are_seed_provenance_with_zero_counts(self):
        graph = seed_graph(load_taxonomy())
        assert len(graph.edges) > 0
        for edge in graph.edges.values():
            assert edge.provenance == "seed"
            assert edge.pos == 0 and edge.neg == 0

    def test_seed_edges_reference_valid_taxonomy_entries(self):
        taxonomy = load_taxonomy()
        graph = seed_graph(taxonomy)
        for edge in graph.edges.values():
            assert edge.tactic in taxonomy.tactic_ids()
            assert taxonomy.valid_tag(edge.dimension, edge.value)

    def test_seeds_never_promote_to_required(self):
        graph = seed_graph(load_taxonomy())
        tags = {
            "engine": "chatgpt",
            "mode": "deep-research",
            "retrieval_type": "synthesis",
        }
        assert graph.required_tactics(tags) == {}


class TestLabelsAndPromotion:
    def test_ten_positive_labels_promote(self):
        graph = Graph(taxonomy_version="v1")
        for _ in range(10):
            graph.add_label("concise-query", "retrieval_type", "factual-lookup")
        required = graph.required_tactics({"retrieval_type": "factual-lookup"})
        assert "concise-query" in required

    def test_five_positives_pass_gate_but_not_theta(self):
        graph = Graph(taxonomy_version="v1")
        for _ in range(K_MIN):
            graph.add_label("concise-query", "retrieval_type", "factual-lookup")
        assert graph.required_tactics({"retrieval_type": "factual-lookup"}) == {}

    def test_below_support_gate_never_promotes(self):
        graph = Graph(taxonomy_version="v1")
        for _ in range(K_MIN - 1):
            graph.add_label("concise-query", "retrieval_type", "factual-lookup")
        assert graph.required_tactics({"retrieval_type": "factual-lookup"}) == {}

    def test_negative_labels_hold_back_promotion(self):
        graph = Graph(taxonomy_version="v1")
        for _ in range(10):
            graph.add_label("concise-query", "retrieval_type", "factual-lookup")
        for _ in range(5):
            graph.add_label(
                "concise-query", "retrieval_type", "factual-lookup", positive=False
            )
        assert graph.required_tactics({"retrieval_type": "factual-lookup"}) == {}

    def test_labels_on_seeded_edge_accumulate_from_zero(self):
        graph = seed_graph(load_taxonomy())
        edge_key = next(iter(graph.edges))
        tactic, dimension, value = edge_key
        for _ in range(3):
            graph.add_label(tactic, dimension, value)
        edge = graph.edges[edge_key]
        assert edge.pos == 3
        # 3 labels < K_MIN: seed structure contributes nothing to the gate.
        assert tactic not in graph.required_tactics({dimension: value})


class TestMemoIngest:
    def test_ingest_creates_edges_for_all_dimensions(self):
        graph = Graph(taxonomy_version="v1")
        assert graph.ingest_memo(make_frontmatter()) is True
        # 2 tactics x (4 tag dims + engine + mode) = 12 edges, each pos=1
        assert len(graph.edges) == 12
        for edge in graph.edges.values():
            assert edge.pos == 1 and edge.neg == 0

    def test_ingest_dedupes_on_hash_and_engine(self):
        graph = Graph(taxonomy_version="v1")
        assert graph.ingest_memo(make_frontmatter()) is True
        assert graph.ingest_memo(make_frontmatter()) is False
        for edge in graph.edges.values():
            assert edge.pos == 1

    def test_same_prompt_different_engine_both_ingest(self):
        graph = Graph(taxonomy_version="v1")
        assert graph.ingest_memo(make_frontmatter()) is True
        assert graph.ingest_memo(make_frontmatter(engine="gemini")) is True

    def test_ingest_directory_reads_memo_files(self, tmp_path):
        fm = make_frontmatter()
        (tmp_path / "a.md").write_text(render_frontmatter(fm) + "\nbody\n")
        (tmp_path / "junk.md").write_text("no frontmatter here\n")
        graph = Graph(taxonomy_version="v1")
        assert ingest_directory(graph, tmp_path) == 1
        assert len(graph.edges) == 12


class TestPersistence:
    def test_round_trip(self, tmp_path):
        graph = seed_graph(load_taxonomy())
        graph.ingest_memo(make_frontmatter())
        for _ in range(6):
            graph.add_label("concise-query", "retrieval_type", "factual-lookup")
        path = tmp_path / "graph.json"
        save_graph(graph, path)
        loaded = load_graph(path)
        assert loaded.taxonomy_version == graph.taxonomy_version
        assert loaded.ingested == graph.ingested
        assert set(loaded.edges) == set(graph.edges)
        for key, edge in graph.edges.items():
            other = loaded.edges[key]
            assert (other.pos, other.neg, other.provenance) == (
                edge.pos,
                edge.neg,
                edge.provenance,
            )

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_graph(tmp_path / "nope.json")
