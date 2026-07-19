"""M5 — `forge push` CLI wiring. The runner is patched so no network is hit."""

from forge.__main__ import main
from tests.test_m5_push import FakeRunner, corpus_with_memo, fresh_repo_runner


def patch_runner(monkeypatch, runner):
    monkeypatch.setattr("forge.push.make_runner", lambda: runner)


class TestPushCli:
    def test_push_success_exits_zero(self, tmp_path, monkeypatch, capsys):
        corpus = corpus_with_memo(tmp_path)
        patch_runner(monkeypatch, fresh_repo_runner())
        rc = main(["push", "--dir", str(corpus), "--repo", "corpus-repo"])
        assert rc == 0
        assert "pushed" in capsys.readouterr().out.lower()

    def test_offline_exits_nonzero_but_retains(self, tmp_path, monkeypatch, capsys):
        corpus = corpus_with_memo(tmp_path)
        runner = fresh_repo_runner().when("git", "push", returncode=1, stderr="offline")
        patch_runner(monkeypatch, runner)
        rc = main(["push", "--dir", str(corpus), "--repo", "corpus-repo"])
        assert rc == 1
        out = capsys.readouterr().out.lower()
        assert "retain" in out or "local" in out
        assert (corpus / "2026-07-19-x-chatgpt.md").exists()

    def test_default_repo_slug(self, tmp_path, monkeypatch, capsys):
        corpus = corpus_with_memo(tmp_path)
        runner = fresh_repo_runner()
        patch_runner(monkeypatch, runner)
        rc = main(["push", "--dir", str(corpus)])
        assert rc == 0
        assert "research-prompt-forge-corpus" in runner.call("gh", "repo", "view")

    def test_empty_corpus_exits_zero_noop(self, tmp_path, monkeypatch, capsys):
        corpus = tmp_path / "research-memos"
        corpus.mkdir()
        patch_runner(monkeypatch, FakeRunner())
        rc = main(["push", "--dir", str(corpus), "--repo", "corpus-repo"])
        assert rc == 0
        assert "nothing" in capsys.readouterr().out.lower()
