"""M1 — intake + IR normalizer."""

import pytest

from polyprompt.intake import IntakeAnswers
from polyprompt.ir import normalize


def test_normalize_populates_from_intake():
    ir = normalize(
        "Compare A and B",
        IntakeAnswers(time_period="2024+", depth=3, clarifications="focus on the US market"),
    )
    assert ir.intent == "Compare A and B"
    assert ir.recency_window == "2024+"
    assert ir.reasoning_layers == 3
    assert ir.depth == "deep"
    assert "focus on the US market" in ir.constraints


def test_normalize_detects_year_when_no_time_period():
    ir = normalize("trends since 2023 in solar", IntakeAnswers())
    assert ir.recency_window == "2023+"


def test_normalize_source_hints():
    ir = normalize("give me cited primary sources on X", IntakeAnswers())
    assert "primary sources" in ir.source_preferences


def test_default_depth_is_standard():
    ir = normalize("x", IntakeAnswers())
    assert ir.reasoning_layers == 2
    assert ir.depth == "standard"


def test_out_of_range_depth_falls_back():
    ir = normalize("x", IntakeAnswers(depth=9))
    assert ir.reasoning_layers == 2


def test_normalize_rejects_empty():
    with pytest.raises(ValueError):
        normalize("   ", IntakeAnswers())
