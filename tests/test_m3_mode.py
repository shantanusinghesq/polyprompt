"""M3 — hybrid mode auto-detector: golden cases + escalation seam."""

from polyprompt.intake import IntakeAnswers
from polyprompt.ir import normalize
from polyprompt.mode import detect_mode


def _ir(prompt, **intake):
    return normalize(prompt, IntakeAnswers(**intake))


def test_clear_deep_research_by_rules():
    d = detect_mode(_ir("Compare and analyze the comprehensive trade-offs of X vs Y", depth=3, time_period="2024+"))
    assert d.mode == "deep-research"
    assert d.source == "rules"


def test_clear_chat_by_rules():
    d = detect_mode(_ir("What is the capital of France", depth=1))
    assert d.mode == "chat"
    assert d.source == "rules"


def test_short_factual_is_chat():
    d = detect_mode(_ir("Define entropy", depth=1))
    assert d.mode == "chat"
    assert d.source == "rules"


def test_borderline_defaults_deep_without_fallback():
    d = detect_mode(_ir("Overview of solar panel options", depth=2))
    assert d.source == "default"
    assert d.mode == "deep-research"


def test_borderline_escalates_to_model_fallback():
    calls = []

    def fallback(ir):
        calls.append(ir)
        return "chat"

    d = detect_mode(_ir("Overview of solar panel options", depth=2), model_fallback=fallback)
    assert d.source == "model"
    assert d.mode == "chat"
    assert calls, "model fallback should have been invoked"


def test_reason_is_always_populated():
    for prompt, depth in [("What is X", 1), ("Compare A vs B", 3), ("Overview of Y", 2)]:
        assert detect_mode(_ir(prompt, depth=depth)).reason
