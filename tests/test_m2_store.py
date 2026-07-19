"""M2 — local persistence + dedupe on (source_prompt_hash, engine)."""

from datetime import datetime

from polyprompt.__main__ import main
from polyprompt.intake import IntakeAnswers
from polyprompt.ir import normalize
from polyprompt.memo import build_memo
from polyprompt.profile import load_profile
from polyprompt.rewrite import rewrite
from polyprompt.store import existing_keys, save_memo
from polyprompt.taxonomy import load_taxonomy

_NOW = datetime(2026, 7, 19, 8, 30, 0)


def _make_memo(prompt, engine):
    tax = load_taxonomy()
    ir = normalize(prompt, IntakeAnswers(time_period="2024+", depth=2))
    result = rewrite(ir, load_profile(engine))
    return build_memo(prompt, ir, result, tax, now=_NOW)


def test_save_writes_then_dedupes(tmp_path):
    memo = _make_memo("Compare A vs B", "chatgpt")

    path, status = save_memo(memo, tmp_path)
    assert status == "written"
    assert path.exists()

    # same prompt + engine -> skipped
    _, status2 = save_memo(memo, tmp_path)
    assert status2 == "skipped"

    assert len(list(tmp_path.glob("*.md"))) == 1


def test_different_engine_not_deduped(tmp_path):
    save_memo(_make_memo("Compare A vs B", "chatgpt"), tmp_path)
    _, status = save_memo(_make_memo("Compare A vs B", "claude"), tmp_path)
    assert status == "written"
    assert len(list(tmp_path.glob("*.md"))) == 2


def test_existing_keys_reads_frontmatter(tmp_path):
    memo = _make_memo("Compare A vs B", "gemini")
    save_memo(memo, tmp_path)
    keys = existing_keys(tmp_path)
    assert (memo.frontmatter["source_prompt_hash"], "gemini") in keys


def test_cli_writes_four_memos(tmp_path, capsys):
    rc = main([
        "rewrite", "--engine", "all",
        "--time-period", "2024+", "--depth", "3",
        "--memos", str(tmp_path),
        "Compare 15-year TCO of heat pumps vs gas furnaces",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.count("[written]") == 4
    assert len(list(tmp_path.glob("*.md"))) == 4


def test_cli_rerun_dedupes(tmp_path, capsys):
    args = [
        "rewrite", "--engine", "all",
        "--memos", str(tmp_path),
        "Compare 15-year TCO of heat pumps vs gas furnaces",
    ]
    main(args)
    capsys.readouterr()
    main(args)  # second run
    out = capsys.readouterr().out
    assert out.count("[skipped]") == 4
    assert len(list(tmp_path.glob("*.md"))) == 4
