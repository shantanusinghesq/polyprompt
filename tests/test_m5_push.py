"""M5 — private corpus push: git/gh orchestration via an injectable runner.

The runner is faked so the whole push path is exercised offline. The fake
models creation and remote setup, including the privacy metadata now required
before every push. No test shells out to real git or gh.
"""

import json
from pathlib import Path

from polyprompt.push import RunResult, push_corpus


class FakeRunner:
    """Records argv, applies explicit rules first, then models repo state."""

    def __init__(self, *, repo_exists=True, origin=None):
        self.calls: list[list[str]] = []
        self._rules: list[tuple[tuple[str, ...], RunResult]] = []
        self.repo_exists = repo_exists
        self.origin = origin

    def when(self, *prefix, returncode=0, stdout="", stderr=""):
        self._rules.append((prefix, RunResult(returncode, stdout, stderr)))
        return self

    def __call__(self, argv, cwd):
        self.calls.append(list(argv))
        for prefix, result in self._rules:
            if tuple(argv[: len(prefix)]) == prefix:
                return result
        if argv[:3] == ["gh", "repo", "view"]:
            if not self.repo_exists:
                return RunResult(1, stderr="not found")
            name = argv[3] if "/" in argv[3] else "haremantra/" + argv[3]
            return RunResult(0, json.dumps({
                "url": "https://github.com/" + name,
                "nameWithOwner": name, "isPrivate": True, "visibility": "PRIVATE",
            }))
        if argv[:3] == ["gh", "repo", "create"]:
            self.repo_exists = True
            name = argv[3] if "/" in argv[3] else "haremantra/" + argv[3]
            self.origin = "https://github.com/" + name
            return RunResult(0)
        if argv[:3] == ["git", "remote", "get-url"]:
            return RunResult(0, self.origin) if self.origin else RunResult(1)
        if argv[:3] == ["git", "remote", "add"]:
            self.origin = argv[4]
            return RunResult(0)
        if argv[:2] == ["git", "status"]:
            return RunResult(0, stdout="?? memo.md\n")
        if argv[:2] == ["git", "rev-parse"]:
            return RunResult(0, "a" * 40 + "\n")
        return RunResult(0)

    def ran(self, *prefix) -> bool:
        return any(tuple(c[: len(prefix)]) == prefix for c in self.calls)

    def call(self, *prefix) -> list[str]:
        for c in self.calls:
            if tuple(c[: len(prefix)]) == prefix:
                return c
        raise AssertionError(f"no call matched prefix {prefix}")


def corpus_with_memo(tmp_path) -> Path:
    corpus = tmp_path / "research-memos"
    corpus.mkdir()
    (corpus / "2026-07-19-x-chatgpt.md").write_text("---\nengine: \"chatgpt\"\n---\nbody\n")
    return corpus


def fresh_repo_runner() -> FakeRunner:
    return FakeRunner(repo_exists=False)


class TestHappyPath:
    def test_status_pushed(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        res = push_corpus(corpus, "corpus-repo", runner=fresh_repo_runner(), message="m")
        assert res.status == "pushed"
        assert res.committed and res.pushed

    def test_inits_repo_when_absent(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        runner = fresh_repo_runner()
        push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert runner.ran("git", "init")

    def test_skips_init_when_repo_exists(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        (corpus / ".git").mkdir()
        runner = fresh_repo_runner()
        push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert not runner.ran("git", "init")

    def test_creates_private_repo(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        runner = fresh_repo_runner()
        push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert runner.ran("gh", "repo", "create")
        assert "--private" in runner.call("gh", "repo", "create")

    def test_commits_and_pushes(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        runner = fresh_repo_runner()
        push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert runner.ran("git", "commit")
        assert runner.ran("git", "push")


class TestExistingRemoteRepo:
    def test_uses_existing_repo_without_recreating(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        runner = FakeRunner(repo_exists=True)
        res = push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert not runner.ran("gh", "repo", "create")
        assert runner.ran("git", "remote", "add")
        assert res.status == "pushed"

    def test_existing_origin_is_verified_without_reconfiguring(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        (corpus / ".git").mkdir()
        runner = FakeRunner(origin="https://github.com/haremantra/corpus-repo")
        res = push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert runner.ran("gh", "repo", "view")
        assert not runner.ran("git", "remote", "add")
        assert res.status == "pushed"


class TestOfflineFallback:
    def test_push_failure_keeps_local_and_reports(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        memo = corpus / "2026-07-19-x-chatgpt.md"
        runner = fresh_repo_runner().when(
            "git", "push", returncode=1, stderr="Could not resolve host github.com"
        )
        res = push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert res.status == "local"
        assert res.committed and not res.pushed
        assert memo.exists()
        assert "retain" in res.report.lower()
        assert "local" in res.report.lower()

    def test_missing_repo_without_create_retains_local(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        runner = fresh_repo_runner()
        res = push_corpus(
            corpus, "corpus-repo", runner=runner, message="m", create_if_missing=False
        )
        assert not runner.ran("gh", "repo", "create")
        assert not res.pushed
        assert res.status == "local"
        assert (corpus / "2026-07-19-x-chatgpt.md").exists()


class TestNothingToPush:
    def test_empty_corpus_is_noop(self, tmp_path):
        corpus = tmp_path / "research-memos"
        corpus.mkdir()
        runner = FakeRunner()
        res = push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert res.status == "noop"
        assert not res.committed
        assert not runner.ran("git", "commit")

    def test_missing_directory_fails_cleanly(self, tmp_path):
        res = push_corpus(
            tmp_path / "nope", "corpus-repo", runner=FakeRunner(), message="m"
        )
        assert res.status == "failed"
        assert not res.committed

    def test_clean_tree_pushes_existing_commits_without_recommitting(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        (corpus / ".git").mkdir()
        runner = FakeRunner(origin="https://github.com/haremantra/corpus-repo").when(
            "git", "status", returncode=0, stdout=""
        )
        res = push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert res.status == "pushed"
        assert not res.committed
        assert not runner.ran("git", "commit")
        assert runner.ran("git", "push")
