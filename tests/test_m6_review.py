"""M6 — review capture and edge weighting from reviewer labels."""

import json

import pytest

from polyprompt.graph import Graph
from polyprompt.review import (
    Review,
    apply_review,
    load_reviews,
    mode_accuracy,
    save_review,
    sentiment,
)
from tests.test_m4_graph import make_frontmatter


def make_review(**overrides):
    kw = dict(
        memo_filename="2026-07-19-x-chatgpt.md",
        reviewer="alex",
        intent_fidelity=5,
        quality=4,
        depth_explanation="covers all three layers of the causal chain",
        mode_correct=True,
        reviewed_at="2026-07-19T12:00:00",
    )
    kw.update(overrides)
    return Review(**kw)


class TestSentiment:
    def test_high_ratings_positive(self):
        assert sentiment(make_review()) == "positive"

    def test_low_rating_negative(self):
        assert sentiment(make_review(quality=2)) == "negative"

    def test_middling_neutral(self):
        assert sentiment(make_review(intent_fidelity=3, quality=4)) == "neutral"

    def test_rejects_out_of_range(self):
        with pytest.raises(ValueError):
            make_review(quality=6)
        with pytest.raises(ValueError):
            make_review(intent_fidelity=0)

    def test_rejects_empty_reviewer(self):
        with pytest.raises(ValueError):
            make_review(reviewer="  ")


class TestSidecar:
    def test_save_and_load_round_trip(self, tmp_path):
        review = make_review()
        path = save_review(review, tmp_path)
        assert path.name == "2026-07-19-x-chatgpt.review.json"
        assert json.loads(path.read_text())["reviewer"] == "alex"
        loaded = load_reviews(tmp_path)
        assert len(loaded) == 1
        assert loaded[0] == review

    def test_load_skips_junk(self, tmp_path):
        (tmp_path / "bad.review.json").write_text("not json")
        assert load_reviews(tmp_path) == []


class TestApplyReview:
    def test_positive_review_adds_positive_labels(self):
        graph = Graph(taxonomy_version="v1")
        assert apply_review(graph, make_frontmatter(), make_review()) == "positive"
        # 2 tactics x 6 dims, each pos=1
        assert len(graph.edges) == 12
        assert all(e.pos == 1 and e.neg == 0 for e in graph.edges.values())

    def test_negative_review_adds_negative_labels(self):
        graph = Graph(taxonomy_version="v1")
        assert apply_review(graph, make_frontmatter(), make_review(quality=1)) == "negative"
        assert all(e.neg == 1 and e.pos == 0 for e in graph.edges.values())

    def test_neutral_review_adds_no_labels(self):
        graph = Graph(taxonomy_version="v1")
        assert apply_review(graph, make_frontmatter(), make_review(quality=3)) == "neutral"
        assert graph.edges == {}

    def test_duplicate_review_is_ignored(self):
        graph = Graph(taxonomy_version="v1")
        apply_review(graph, make_frontmatter(), make_review())
        assert apply_review(graph, make_frontmatter(), make_review()) is None
        assert all(e.pos == 1 for e in graph.edges.values())

    def test_second_reviewer_counts(self):
        graph = Graph(taxonomy_version="v1")
        apply_review(graph, make_frontmatter(), make_review())
        assert apply_review(graph, make_frontmatter(), make_review(reviewer="sam")) == "positive"
        assert all(e.pos == 2 for e in graph.edges.values())


class TestModeAccuracy:
    def test_accuracy_fraction(self):
        reviews = [make_review(), make_review(reviewer="b", mode_correct=False)]
        assert mode_accuracy(reviews) == 0.5

    def test_empty_is_none(self):
        assert mode_accuracy([]) is None
