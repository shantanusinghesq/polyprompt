"""Private corpus push (PRD FR-5; M5).

Memos are local-by-default (see store.py); this module is the *only* path that
sends them off the machine, and it does so exclusively via an explicit command.
The corpus directory (`research-memos/`) is its own independent git repo with a
**private** GitHub remote — first-class and separately pushable (scratchpad
D-09). Push failure never loses data: the local copy is always retained and the
outcome is reported.

All git/gh calls go through an injected `Runner`, so the orchestration is
deterministic and testable offline. The real runner is a thin subprocess
wrapper; tests inject a fake.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DEFAULT_REPO = "research-prompt-forge-corpus"


@dataclass
class RunResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


# A runner executes an argv in a working directory and returns a RunResult.
Runner = Callable[[list[str], Path], RunResult]


@dataclass
class PushResult:
    status: str  # "pushed" | "local" | "noop" | "failed"
    committed: bool
    pushed: bool
    repo: str
    directory: Path
    report: str
    commit_message: str | None = None


class SubprocessRunner:
    """Real runner. A missing binary (git/gh not installed) surfaces as exit
    127 rather than an exception, so push_corpus can report it like any other
    failed command."""

    def __call__(self, argv: list[str], cwd: Path) -> RunResult:
        try:
            proc = subprocess.run(
                argv, cwd=str(cwd), capture_output=True, text=True, check=False
            )
        except FileNotFoundError:
            return RunResult(127, stderr=f"{argv[0]}: command not found")
        return RunResult(proc.returncode, proc.stdout, proc.stderr)


def make_runner() -> Runner:
    return SubprocessRunner()


def _corpus_files(directory: Path) -> list[Path]:
    return [
        p
        for p in directory.rglob("*")
        if p.is_file() and ".git" not in p.parts
    ]


def _ensure_repo(directory: Path, runner: Runner) -> RunResult | None:
    """git init only when the corpus isn't already a repo. Returns the init
    result, or None if no init was needed."""
    if (directory / ".git").exists():
        return None
    result = runner(["git", "init", "-b", "main"], directory)
    if not result.ok:  # older git without -b: retry plain init
        result = runner(["git", "init"], directory)
    return result


def _ensure_remote(directory: Path, repo: str, runner: Runner,
                   create_if_missing: bool) -> tuple[bool, str]:
    """Make `origin` point at the private corpus repo, creating it if absent.
    Returns (remote_ready, note)."""
    if runner(["git", "remote", "get-url", "origin"], directory).ok:
        return True, "origin already configured"

    view = runner(["gh", "repo", "view", repo, "--json", "url", "-q", ".url"], directory)
    if view.ok:
        url = view.stdout.strip() or repo
        added = runner(["git", "remote", "add", "origin", url], directory)
        if added.ok:
            return True, f"linked existing repo {repo}"
        return False, f"could not add remote: {added.stderr.strip()}"

    if not create_if_missing:
        return False, f"repo {repo} not found and --no-create set"

    created = runner(
        ["gh", "repo", "create", repo, "--private", "--source", str(directory),
         "--remote", "origin"],
        directory,
    )
    if created.ok:
        return True, f"created private repo {repo}"
    return False, f"could not create repo {repo}: {created.stderr.strip()}"


def push_corpus(directory: Path | str, repo: str = DEFAULT_REPO, *,
                runner: Runner | None = None, message: str | None = None,
                create_if_missing: bool = True) -> PushResult:
    """Commit the corpus directory and push it to the private repo.

    Never deletes or moves memos; on any failure the local copy is retained and
    the reason is reported. Status: 'pushed' (reached the remote), 'local'
    (committed but not pushed — retained + reported), 'noop' (nothing new), or
    'failed' (no corpus to push).
    """
    directory = Path(directory)
    runner = runner or make_runner()
    message = message or "corpus: memo update"

    def done(status, committed, pushed, note):
        return PushResult(
            status=status,
            committed=committed,
            pushed=pushed,
            repo=repo,
            directory=directory,
            report=note,
            commit_message=message if committed else None,
        )

    if not directory.exists():
        return done("failed", False, False,
                    f"nothing to push: corpus directory {directory} does not exist")
    if not _corpus_files(directory):
        return done("noop", False, False,
                    f"nothing to push: no memos in {directory}")

    _ensure_repo(directory, runner)
    runner(["git", "add", "-A"], directory)

    if not runner(["git", "status", "--porcelain"], directory).stdout.strip():
        return done("noop", False, False,
                    "nothing to push: corpus already up to date")

    commit = runner(["git", "commit", "-m", message], directory)
    if not commit.ok:
        return done("failed", False, False,
                    f"commit failed (local copy retained): {commit.stderr.strip()}")

    remote_ready, note = _ensure_remote(directory, repo, runner, create_if_missing)
    if not remote_ready:
        return done(
            "local", True, False,
            f"committed locally but not pushed ({note}). "
            f"Local copy retained in {directory}; re-run push when resolved.",
        )

    push = runner(["git", "push", "-u", "origin", "HEAD"], directory)
    if not push.ok:
        return done(
            "local", True, False,
            f"committed locally but push failed: {push.stderr.strip()}. "
            f"Local copy retained in {directory}; re-run push when online.",
        )

    return done("pushed", True, True, f"pushed corpus to private repo {repo} ({note})")
