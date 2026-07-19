"""M1 exit test — one prompt fans out to four distinct, engine-tuned variants."""

from forge.__main__ import main
from forge.intake import IntakeAnswers
from forge.ir import normalize
from forge.profile import ENGINES, load_all_profiles
from forge.rewrite import rewrite


def _results():
    ir = normalize(
        "Compare 15-year TCO of heat pumps vs gas furnaces",
        IntakeAnswers(time_period="2024+", depth=3),
    )
    profiles = load_all_profiles()
    return {engine: rewrite(ir, profiles[engine]) for engine in ENGINES}


def test_each_engine_produces_nonempty_tuned_prompt():
    for result in _results().values():
        assert result.prompt.strip()
        assert result.mode == "deep-research"
        assert result.adaptations


def test_engine_specific_markers():
    results = _results()
    assert "You are" in results["chatgpt"].prompt
    assert "research plan" in results["gemini"].prompt.lower()
    assert "<task>" in results["claude"].prompt
    assert "Cite sources" in results["perplexity"].prompt


def test_all_four_distinct():
    prompts = [r.prompt for r in _results().values()]
    assert len(set(prompts)) == 4


def test_perplexity_is_most_concise():
    results = _results()
    ppx_len = len(results["perplexity"].prompt)
    assert all(ppx_len <= len(results[e].prompt) for e in ("chatgpt", "gemini", "claude"))


def test_intent_preserved_in_all_engines():
    for result in _results().values():
        assert "heat pumps" in result.prompt.lower()


def test_recency_threads_into_rewrites():
    results = _results()
    # 2024+ recency should surface as a Perplexity operator (after:2023)
    assert "after:2023" in results["perplexity"].prompt


def test_cli_all_engines(capsys):
    rc = main(["rewrite", "--engine", "all", "--time-period", "2024+", "--depth", "3", "Compare X and Y"])
    out = capsys.readouterr().out
    assert rc == 0
    for engine in ("CHATGPT", "GEMINI", "CLAUDE", "PERPLEXITY"):
        assert engine in out


def test_cli_single_engine(capsys):
    rc = main(["rewrite", "--engine", "claude", "Compare X and Y"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "<task>" in out
    assert "CHATGPT" not in out


def test_cli_empty_prompt_errors(capsys):
    rc = main(["rewrite", "--engine", "all", "   "])
    err = capsys.readouterr().err
    assert rc == 2
    assert "error" in err.lower()
