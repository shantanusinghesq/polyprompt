"""M3 — detected mode threads through rewrite, memo frontmatter, and CLI."""

from datetime import datetime

from polyprompt.__main__ import main
from polyprompt.intake import IntakeAnswers
from polyprompt.ir import normalize
from polyprompt.memo import build_memo
from polyprompt.mode import detect_mode
from polyprompt.profile import load_profile
from polyprompt.rewrite import rewrite
from polyprompt.taxonomy import load_taxonomy


def test_rewrite_uses_detected_mode():
    ir = normalize("What is the capital of France", IntakeAnswers(depth=1))
    decision = detect_mode(ir)
    result = rewrite(ir, load_profile("chatgpt"), decision)
    assert result.mode == "chat"
    assert result.mode_source == "rules"
    assert result.mode_reason


def test_rewrite_without_decision_falls_back_to_profile_default():
    ir = normalize("x", IntakeAnswers())
    result = rewrite(ir, load_profile("chatgpt"))
    assert result.mode == "deep-research"
    assert result.mode_source == "default"


def test_memo_records_mode_source_and_reason():
    tax = load_taxonomy()
    ir = normalize("What is the capital of France", IntakeAnswers(depth=1))
    decision = detect_mode(ir)
    result = rewrite(ir, load_profile("chatgpt"), decision)
    memo = build_memo("What is the capital of France", ir, result, tax, now=datetime(2026, 7, 19))
    assert memo.frontmatter["mode"] == "chat"
    assert memo.frontmatter["mode_source"] == "rules"
    assert memo.frontmatter["mode_reason"]


def test_cli_auto_detects_chat(capsys):
    rc = main(["rewrite", "--engine", "chatgpt", "--depth", "1", "What is the capital of France"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Detected mode: chat (rules)" in out


def test_cli_auto_detects_deep_research(capsys):
    rc = main([
        "rewrite", "--engine", "chatgpt", "--depth", "3", "--time-period", "2024+",
        "Compare and analyze the comprehensive trade-offs of X vs Y",
    ])
    out = capsys.readouterr().out
    assert "Detected mode: deep-research (rules)" in out


def test_cli_force_mode_overrides_detection(capsys):
    rc = main(["rewrite", "--engine", "chatgpt", "--mode", "chat", "Compare A and B"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "forced" in out
