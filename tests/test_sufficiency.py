"""Sufficiency gate — pure assess() over memos + graph (scratchpad D-01..D-04)."""

from polyprompt.graph import Graph, seed_graph
from polyprompt.memo import render_frontmatter
from polyprompt.sufficiency import DIVERSITY_MIN, MIN_PENDING_MEMOS, assess
from polyprompt.taxonomy import load_taxonomy
from tests.test_m4_graph import make_frontmatter


def write_memos(directory, frontmatters):
    directory.mkdir(parents=True, exist_ok=True)
    for i, fm in enumerate(frontmatters):
        (directory / f"memo-{i}.md").write_text(render_frontmatter(fm) + "\nbody\n")
    return directory


def fm_for_edge(hash_, tactic="role-framing", engine="chatgpt"):
    return make_frontmatter(source_prompt_hash=hash_, tactics=[tactic], engine=engine)


class TestPendingScan:
    def test_empty_dir_insufficient(self, tmp_path):
        report = assess(tmp_path / "none", seed_graph(load_taxonomy()))
        assert report.pending_memos == 0
        assert report.would_promote == []
        assert not report.sufficient

    def test_already_ingested_memos_are_not_pending(self, tmp_path):
        fm = make_frontmatter()
        memos = write_memos(tmp_path / "m", [fm])
        graph = Graph(taxonomy_version="v1")
        graph.ingest_memo(fm)
        report = assess(memos, graph)
        assert report.pending_memos == 0
        assert not report.sufficient

    def test_pending_memo_threshold_gives_sufficiency(self, tmp_path):
        fms = [fm_for_edge(f"hash{i:02d}") for i in range(MIN_PENDING_MEMOS)]
        memos = write_memos(tmp_path / "m", fms)
        report = assess(memos, Graph(taxonomy_version="v1"))
        assert report.pending_memos == MIN_PENDING_MEMOS
        assert report.sufficient  # hysteresis pre-check, even with no promotion

    def test_below_threshold_and_no_promotion_insufficient(self, tmp_path):
        memos = write_memos(tmp_path / "m", [fm_for_edge("hash01")])
        report = assess(memos, Graph(taxonomy_version="v1"))
        assert report.pending_memos == 1
        assert not report.sufficient


class TestPromotionSimulation:
    def test_pending_labels_that_flip_promotion_are_detected(self, tmp_path):
        # edge at 7 positives; 3 pending memos with distinct hashes push it to 10/10
        graph = Graph(taxonomy_version="v1")
        for _ in range(7):
            graph.add_label("role-framing", "engine", "chatgpt")
        fms = [fm_for_edge(f"hash{i:02d}") for i in range(3)]
        memos = write_memos(tmp_path / "m", fms)
        report = assess(memos, graph)
        assert ("role-framing", "engine", "chatgpt") in report.would_promote
        assert report.sufficient

    def test_assess_is_read_only(self, tmp_path):
        graph = Graph(taxonomy_version="v1")
        for _ in range(7):
            graph.add_label("role-framing", "engine", "chatgpt")
        memos = write_memos(tmp_path / "m", [fm_for_edge(f"hash{i:02d}") for i in range(3)])
        assess(memos, graph)
        edge = graph.edges[("role-framing", "engine", "chatgpt")]
        assert edge.pos == 7  # unchanged
        assert graph.ingested == set()

    def test_diversity_veto_blocks_single_source_promotion(self, tmp_path):
        # one pending memo would flip the edge (8/8 ~ 0.676 < 0.7; 9/9 ~ 0.701),
        # but only 1 distinct hash < DIVERSITY_MIN
        graph = Graph(taxonomy_version="v1")
        for _ in range(8):
            graph.add_label("role-framing", "engine", "chatgpt")
        memos = write_memos(tmp_path / "m", [fm_for_edge("hash01")])
        report = assess(memos, graph)
        assert report.would_promote == []
        assert ("role-framing", "engine", "chatgpt") in report.vetoed
        assert DIVERSITY_MIN > 1


class TestTriage:
    def test_buckets(self, tmp_path):
        graph = seed_graph(load_taxonomy())  # dormant seeds
        # contested: mixed evidence past K_MIN, neither promoted nor contra
        for _ in range(6):
            graph.add_label("citation-demand", "mode", "deep-research")
        for _ in range(4):
            graph.add_label("citation-demand", "mode", "deep-research", positive=False)
        # needs-more: below K_MIN
        graph.add_label("decomposition", "analysis_type", "comparative")
        report = assess(tmp_path / "none", graph)
        assert ("citation-demand", "mode", "deep-research") in report.buckets["CONTESTED"]
        assert ("decomposition", "analysis_type", "comparative") in report.buckets["NEEDS-MORE"]
        assert len(report.buckets["DORMANT"]) > 0  # the seeds
