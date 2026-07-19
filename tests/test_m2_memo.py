"""M2 — memo generation, frontmatter round-trip, and tag validity."""

from datetime import datetime

from forge.intake import IntakeAnswers
from forge.ir import normalize
from forge.memo import (
    build_memo,
    derive_tags,
    parse_frontmatter,
    prompt_hash,
    render_frontmatter,
    slugify,
)
from forge.profile import load_profile
from forge.rewrite import rewrite
from forge.taxonomy import load_taxonomy

_NOW = datetime(2026, 7, 19, 8, 30, 0)


def _memo(engine="chatgpt", prompt="Compare 15-year TCO of heat pumps vs gas furnaces"):
    tax = load_taxonomy()
    ir = normalize(prompt, IntakeAnswers(time_period="2024+", depth=3))
    result = rewrite(ir, load_profile(engine))
    return build_memo(prompt, ir, result, tax, now=_NOW), tax, ir, result


def test_frontmatter_has_required_fields():
    memo, _, _, result = _memo()
    fm = memo.frontmatter
    for key in (
        "schema_version", "taxonomy_version", "source_prompt_hash",
        "engine", "mode", "profile_version", "tactics", "tags", "generated_at",
    ):
        assert key in fm, f"missing frontmatter key: {key}"
    assert fm["engine"] == "chatgpt"
    assert fm["tactics"] == result.tactics


def test_frontmatter_round_trips():
    memo, _, _, _ = _memo()
    parsed = parse_frontmatter(memo.to_markdown())
    assert parsed == memo.frontmatter  # lossless


def test_tactics_are_taxonomy_ids():
    memo, tax, _, _ = _memo()
    assert set(memo.frontmatter["tactics"]) <= tax.tactic_ids()


def test_tags_are_valid_enum_values():
    memo, tax, _, _ = _memo()
    for dim, value in memo.frontmatter["tags"].items():
        assert tax.valid_tag(dim, value), f"{dim}={value} not in taxonomy enum"


def test_derived_tags_for_tco_comparison():
    ir = normalize("Compare 15-year TCO of heat pumps vs gas furnaces", IntakeAnswers())
    tags = derive_tags(ir)
    assert tags["method"] == "quantitative"      # cost/tco
    assert tags["analysis_type"] == "comparative"  # compare/vs
    assert tags["subject_matter"] == "energy"     # heat pump/furnace


def test_filename_convention():
    memo, _, _, _ = _memo()
    assert memo.filename == "2026-07-19-compare-15-year-tco-of-heat-pumps-vs-gas-furnaces-chatgpt.md"


def test_prompt_hash_is_stable_and_short():
    h1 = prompt_hash("Compare A and B")
    h2 = prompt_hash("Compare A and B")
    assert h1 == h2
    assert len(h1) == 16


def test_slugify():
    assert slugify("Compare A & B: TCO!!") == "compare-a-b-tco"
    assert slugify("   ") == "prompt"


def test_body_mentions_source_and_tactics():
    memo, tax, _, result = _memo()
    md = memo.to_markdown()
    assert "Explanation memo" in md
    assert "heat pumps" in md.lower()
    for tid in result.tactics:
        assert tid in md  # each tactic id documented
