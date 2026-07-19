"""M2 — taxonomy loads, and every tactic the renderers can emit exists in it."""

from polyprompt.intake import IntakeAnswers
from polyprompt.ir import normalize
from polyprompt.profile import ENGINES, load_all_profiles
from polyprompt.rewrite import rewrite
from polyprompt.taxonomy import load_taxonomy


def test_taxonomy_loads():
    tax = load_taxonomy()
    assert tax.version == "v1"
    assert tax.tactic_ids()
    for dim in ("method", "analysis_type", "retrieval_type", "subject_matter", "engine", "mode"):
        assert dim in tax.tag_dimensions


def test_every_emitted_tactic_is_in_taxonomy():
    tax = load_taxonomy()
    # rich IR: recency + clarifications so conditional tactics also fire
    ir = normalize(
        "Compare cost of A vs B",
        IntakeAnswers(time_period="2024+", depth=3, clarifications="US market only"),
    )
    profiles = load_all_profiles()
    emitted = set()
    for engine in ENGINES:
        emitted.update(rewrite(ir, profiles[engine]).tactics)
    unknown = emitted - tax.tactic_ids()
    assert not unknown, f"renderers emit tactics missing from taxonomy: {unknown}"
    assert "recency-constraint" in emitted  # conditional fired
    assert "disambiguation" in emitted


def test_tactic_labels_resolve():
    tax = load_taxonomy()
    for tid in tax.tactic_ids():
        assert tax.label(tid)
        assert tax.describe(tid)
