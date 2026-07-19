"""Local memo persistence with dedupe (PRD FR-4).

Memos are written to a directory (default `./research-memos/`). Dedupe key is
`(source_prompt_hash, engine)`: a memo for the same prompt+engine already on
disk is skipped, so re-running the same rewrite never duplicates memos. Pushing
this directory to the private corpus repo is M5's job — nothing here touches git.
"""

from __future__ import annotations

from pathlib import Path

from polyprompt.memo import Memo, parse_frontmatter

DEFAULT_DIR = "research-memos"


def existing_keys(directory: Path | str) -> set[tuple[str, str]]:
    """Scan a memo directory and return the set of (source_prompt_hash, engine)
    keys already present."""
    directory = Path(directory)
    keys: set[tuple[str, str]] = set()
    if not directory.exists():
        return keys
    for path in directory.glob("*.md"):
        try:
            frontmatter = parse_frontmatter(path.read_text())
        except ValueError:
            continue
        h = frontmatter.get("source_prompt_hash")
        engine = frontmatter.get("engine")
        if h and engine:
            keys.add((h, engine))
    return keys


def save_memo(memo: Memo, directory: Path | str,
              keys: set[tuple[str, str]] | None = None) -> tuple[Path, str]:
    """Write a memo unless its (hash, engine) key already exists.

    Returns (path, status) where status is 'written' or 'skipped'. If `keys` is
    supplied it is used (and updated) instead of rescanning — pass it when
    saving several memos in one run.
    """
    directory = Path(directory)
    key = (memo.frontmatter["source_prompt_hash"], memo.frontmatter["engine"])
    seen = keys if keys is not None else existing_keys(directory)
    path = directory / memo.filename

    if key in seen:
        return path, "skipped"

    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(memo.to_markdown())
    if keys is not None:
        keys.add(key)
    return path, "written"
