"""M5 — private corpus push: git/gh orchestration via an injectable runner.

The runner is faked so the whole push path (init, repo-create, commit, push)
is exercised deterministically offline. Real subprocess behavior is out of
scope for these unit tests — that seam is a thin wrapper (SubprocessRunner).
"""

from pathlib import Path

from forge.push import RunResult, push_corpus


class FakeRunner:
    """Records argv calls and answers them by matching command prefixes.

    Rules are checked in insertion order; first match wins. Unmatched `git
    status` defaults to a dirty tree so commits proceed; everything else
    defaults to success.
    """

    def __init__(self):
        self.calls: list[list[str]] = []
        self._rules: list[tuple[tuple[str, ...], RunResult]] = []

    def when(self, *prefix, returncode=0, stdout="", stderr=""):
        self._rules.append((prefix, RunResult(returncode, stdout, stderr)))
        return self

    def __call__(self, argv, cwd):
        self.calls.append(list(argv))
        for prefix, result in self._rules:
            if tuple(argv[: len(prefix)]) == prefix:
                return result
        if argv[:2] == ["git", "status"]:
            return RunResult(0, stdout="?? memo.md\n")
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
    # repo doesn't exist yet; no local remote configured yet.
    return (
        FakeRunner()
        .when("gh", "repo", "view", returncode=1, stderr="not found")
        .when("git", "remote", "get-url", returncode=1)
    )


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
        runner = (
            FakeRunner()
            .when("gh", "repo", "view", returncode=0,
                  stdout="https://github.com/haremantra/corpus-repo")
            .when("git", "remote", "get-url", returncode=1)
        )
        res = push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert not runner.ran("gh", "repo", "create")
        assert runner.ran("git", "remote", "add")
        assert res.status == "pushed"

    def test_skips_remote_setup_when_origin_present(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        (corpus / ".git").mkdir()
        runner = FakeRunner().when(
            "git", "remote", "get-url", returncode=0,
            stdout="https://github.com/haremantra/corpus-repo",
        )
        res = push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert not runner.ran("gh", "repo", "view")
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
        assert memo.exists()  # local copy retained
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

    def test_clean_tree_is_noop(self, tmp_path):
        corpus = corpus_with_memo(tmp_path)
        (corpus / ".git").mkdir()
        runner = (
            FakeRunner()
            .when("git", "remote", "get-url", returncode=0,
                  stdout="https://github.com/haremantra/corpus-repo")
            .when("git", "status", returncode=0, stdout="")  # clean tree
        )
        res = push_corpus(corpus, "corpus-repo", runner=runner, message="m")
        assert res.status == "noop"
        assert not runner.ran("git", "commit")
