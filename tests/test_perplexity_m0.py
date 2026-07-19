"""M0 exit test: the walking skeleton loads and returns a Perplexity-tuned string."""

import pytest

from forge.engines.perplexity import perplexity_transform
from forge.ir import PromptIR
from forge.__main__ import main


def test_perplexity_transform_returns_tuned_string():
    out = perplexity_transform("  test   prompt  ")
    assert out, "output must be non-empty"
    assert "test prompt" in out, "whitespace-collapsed core prompt preserved"
    assert "citations" in out.lower(), "Perplexity-leaning directive present"
    assert out.strip() != "test prompt", "output must actually be transformed"


def test_perplexity_transform_rejects_empty():
    with pytest.raises(ValueError):
        perplexity_transform("   ")


def test_ir_stub_captures_intent():
    ir = PromptIR.stub_from_prompt("  compare   A and B ")
    assert ir.intent == "compare A and B"
    assert ir.reasoning_layers == 0  # M0 stub leaves the rest empty


def test_cli_rewrite_exit_code_and_output(capsys):
    rc = main(["rewrite", "--engine", "perplexity", "test prompt"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "citations" in captured.out.lower()


def test_cli_rewrite_empty_prompt_errors(capsys):
    rc = main(["rewrite", "--engine", "perplexity", "   "])
    captured = capsys.readouterr()
    assert rc == 2
    assert "error" in captured.err.lower()
