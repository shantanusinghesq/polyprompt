"""Explicit private-corpus push, with local retention on every failure.

All git/gh calls use the injected Runner. Privacy is verified against GitHub
metadata and *effective push URLs*, including pushurl/pushInsteadOf overrides.
An existing origin is not evidence that a destination is private or intended.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DEFAULT_REPO = "polyprompt-corpus"
_REPO_PART = r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
_REPO_RE = re.compile(rf"{_REPO_PART}(?:/{_REPO_PART})?")


@dataclass
class RunResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


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
    """Report subprocess failures without losing the caller's local corpus."""

    def __call__(self, argv: list[str], cwd: Path) -> RunResult:
        try:
            proc = subprocess.run(
                argv, cwd=str(cwd), capture_output=True, text=True, check=False,
                timeout=120,
            )
        except FileNotFoundError:
            return RunResult(127, stderr=f"{argv[0]}: command not found")
        except subprocess.TimeoutExpired:
            return RunResult(124, stderr=f"{argv[0]}: timed out after 120 seconds")
        except OSError as exc:
            return RunResult(126, stderr=f"{argv[0]}: {exc}")
        return RunResult(proc.returncode, proc.stdout, proc.stderr)


def make_runner() -> Runner:
    return SubprocessRunner()


def _corpus_files(directory: Path) -> list[Path]:
    return [p for p in directory.rglob("*") if p.is_file() and ".git" not in p.parts]


def _ensure_repo(directory: Path, runner: Runner) -> RunResult | None:
    if (directory / ".git").exists():
        return None
    result = runner(["git", "init", "-b", "main"], directory)
    if not result.ok:
        result = runner(["git", "init"], directory)
    return result


def _github_slug(url: str) -> str | None:
    """Accept standard GitHub HTTPS/SSH forms, never arbitrary hosts or helpers."""
    for prefix in ("https://github.com/", "git@github.com:", "ssh://git@github.com/"):
        if url.lower().startswith(prefix):
            slug = url[len(prefix):].rstrip("/")
            if slug.lower().endswith(".git"):
                slug = slug[:-4]
            if slug.count("/") == 1 and _REPO_RE.fullmatch(slug):
                return slug.casefold()
    return None


def _private_metadata(view: RunResult, repo: str) -> tuple[str, str] | None:
    if not view.ok:
        return None
    try:
        data = json.loads(view.stdout)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("isPrivate") is not True or data.get("visibility") != "PRIVATE":
        return None
    name, url = data.get("nameWithOwner"), data.get("url")
    if not isinstance(name, str) or not isinstance(url, str):
        return None
    if name.count("/") != 1 or not _REPO_RE.fullmatch(name):
        return None
    requested = repo.casefold()
    actual = name.casefold()
    if (actual if "/" in repo else actual.split("/")[1]) != requested:
        return None
    if _github_slug(url) != actual:
        return None
    return name, url


def _ensure_remote(directory: Path, repo: str, runner: Runner,
                   create_if_missing: bool) -> tuple[bool, str]:
    has_origin = runner(["git", "remote", "get-url", "origin"], directory).ok
    view_argv = ["gh", "repo", "view", repo, "--json",
                 "url,nameWithOwner,isPrivate,visibility"]
    view = runner(view_argv, directory)
    note = "verified existing private repo"
    if not view.ok:
        if has_origin or not create_if_missing:
            return False, "cannot verify private repo; check gh authentication and connectivity"
        created = runner(
            ["gh", "repo", "create", repo, "--private", "--source", str(directory.resolve()),
             "--remote", "origin"], directory,
        )
        if not created.ok:
            return False, f"could not create private repo: {created.stderr.strip()}"
        has_origin = True
        view = runner(view_argv, directory)
        note = "created and verified private repo"

    metadata = _private_metadata(view, repo)
    if metadata is None:
        return False, "destination is public, internal, mismatched, or not verifiably private"
    name, url = metadata
    if not has_origin:
        added = runner(["git", "remote", "add", "origin", url], directory)
        if not added.ok:
            return False, f"could not add remote: {added.stderr.strip()}"

    effective = runner(["git", "remote", "get-url", "--push", "--all", "origin"], directory)
    urls = effective.stdout.splitlines() if effective.ok else []
    if len(urls) != 1 or _github_slug(urls[0].strip()) != name.casefold():
        return False, "origin must have exactly one push URL matching the verified private repo"
    return True, note


def push_corpus(directory: Path | str, repo: str = DEFAULT_REPO, *,
                runner: Runner | None = None, message: str | None = None,
                create_if_missing: bool = True) -> PushResult:
    """Push new or previously unpushed commits; never delete local memos.

    A clean working tree still needs a push: an earlier commit may not have
    reached the remote. `committed` describes this invocation, not past work.
    """
    directory = Path(directory)
    runner = runner or make_runner()
    message = message or "corpus: memo update"

    def done(status, committed, pushed, note):
        return PushResult(status, committed, pushed, repo, directory, note,
                          message if committed else None)

    if not directory.is_dir():
        return done("failed", False, False,
                    f"nothing to push: corpus directory {directory} does not exist")
    if not _REPO_RE.fullmatch(repo):
        return done("failed", False, False, "repo must be a GitHub name or owner/name")
    if not _corpus_files(directory):
        return done("noop", False, False, f"nothing to push: no memos in {directory}")

    initialized = _ensure_repo(directory, runner)
    if initialized is not None and not initialized.ok:
        return done("failed", False, False,
                    f"git init failed (local copy retained): {initialized.stderr.strip()}")
    staged = runner(["git", "add", "-A"], directory)
    if not staged.ok:
        return done("failed", False, False,
                    f"git add failed (local copy retained): {staged.stderr.strip()}")
    status = runner(["git", "status", "--porcelain"], directory)
    if not status.ok:
        return done("failed", False, False,
                    f"git status failed (local copy retained): {status.stderr.strip()}")

    committed = bool(status.stdout.strip())
    if committed:
        commit = runner(["git", "commit", "-m", message], directory)
        if not commit.ok:
            return done("failed", False, False,
                        f"commit failed (local copy retained): {commit.stderr.strip()}")
    elif not runner(["git", "rev-parse", "--verify", "HEAD"], directory).ok:
        return done("noop", False, False, "nothing to push: no local commit")

    remote_ready, note = _ensure_remote(directory, repo, runner, create_if_missing)
    if not remote_ready:
        return done("local", committed, False,
                    f"not pushed ({note}). Local copy retained in {directory}; "
                    "re-run push when resolved.")
    push = runner(["git", "push", "-u", "origin", "HEAD"], directory)
    if not push.ok:
        return done("local", committed, False,
                    f"push failed: {push.stderr.strip()}. Local copy retained in "
                    f"{directory}; re-run push when resolved.")
    return done("pushed", committed, True,
                f"pushed corpus to private repo {repo} ({note})")
