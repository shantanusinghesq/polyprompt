# Contributing

Short version: **write the failing test first.** Every module in this repo
was built that way, and PRs are expected to match that discipline — not
because it's dogma, but because the golden-fixture strategy (`tests/`) is
the only thing making `polyprompt/ir.py`, `polyprompt/mode.py`, and friends trustworthy
without needing to re-read them on every change.

## Setup

```bash
git clone https://github.com/haremantra/polyprompt.git
cd polyprompt
pip install -e ".[dev]"
python -m pytest -q     # should print "139 passed" (or however many exist now)
```

`.github/workflows/ci.yml` runs this same command (matrixed across Python
3.10/3.11/3.12) on every push and PR to `main` — run it locally first anyway;
waiting for CI to tell you a test broke is slower than knowing before you
push. CI also shadows `git`/`gh` with failing stubs during the test run, so
if a future test forgets to inject a fake `Runner` (see `polyprompt/push.py`), the
build fails loudly instead of silently succeeding or, worse, actually
shelling out — see the incident note under "subprocess-shelling module"
above.

## Before you write any code

1. Read `docs/ARCHITECTURE.md` — invariants section specifically. Several
   design decisions in this repo look "obviously improvable" out of context
   and are in fact deliberate (advisory-never-blocking validation,
   archive-not-delete, seed edges carrying zero weight). If you're about to
   change one of those, read the linked scratchpad/ACC decision record first
   — there's a good chance the alternative was already considered and
   rejected, with a documented reason. Propose changing the decision, don't
   silently route around it.
2. Check `docs/acc/*.md` (newest file, lexicographically) for the current
   state and open questions — it's the fastest way to know what's already
   in flight vs. actually open.

## Development loop (red-green-refactor, no exceptions)

This project follows strict TDD — every `polyprompt/*.py` module was built this
way, verified by watching each test fail before the implementation existed.
Match that pattern:

1. **Write the test first**, in the relevant `tests/test_<area>_*.py` file
   (or a new one, following the existing naming: `test_<milestone-or-area>_<module>.py`).
2. **Watch it fail for the right reason** — `python -m pytest tests/test_your_file.py -v`
   should fail because the behavior doesn't exist, not because of a typo.
3. **Write the minimal code to pass.** Don't add options, flags, or
   abstractions the test doesn't require — this codebase has a
   consistent "no speculative generality" bias (see any module's docstring
   for the tone: short, states the *why*, not the *what*).
4. **Run the full suite**, not just your new file — `python -m pytest -q`.
   Regressions in unrelated modules are the fastest way to get a PR bounced.
5. **If you touched a subprocess-shelling module** (`polyprompt/push.py` is the
   only one today), read the test seam pattern in `tests/test_m5_push.py`
   first. A previous session broke this seam and it created two real
   private GitHub repos before the mistake was caught — see the injectable
   `Runner` pattern and the git/gh-stubbed-off-`PATH` guard in the test
   suite, and don't bypass it.

## Code style

- No comments explaining *what* the code does — names should do that.
  Module-level docstrings explain *why* a design choice was made, when the
  reason isn't obvious from reading the code (see any `polyprompt/*.py` header
  for the calibration).
- Dataclasses over dicts for anything with a stable shape.
- Pure functions where the domain allows it — `ir.normalize()`,
  `rewrite.rewrite()`, `sufficiency.assess()` are all deterministic with no
  I/O; that purity is load-bearing for the test strategy, not incidental.
- New CLI subcommands go in `polyprompt/__main__.py` as a thin `_cmd_*` wrapper
  around a pure function living in its own module — follow the existing
  6-subcommand pattern, don't put logic directly in `_cmd_*`.

## Commit / PR conventions

- One logical change per commit; commit messages state *why*, not just
  *what* (the existing history is the reference — e.g. `git log --oneline`).
- Version bumps: `polyprompt/__init__.py` and `.claude-plugin/plugin.json` are
  kept in sync manually — bump both if your change is milestone-shaped.
  `pyproject.toml`'s `version` field should track the same number (this
  drifted once already; don't let it happen again).
- If your change affects the memo frontmatter schema or the graph JSON
  schema, you're making a breaking change until a compatibility policy
  exists (see `docs/ARCHITECTURE.md`, Known Gaps) — flag it loudly in the
  PR description, don't bump `schema_version` silently.

## What a good first PR looks like

Small, test-first, one module. Good starting points if you want to
contribute without deep context: the "Known gaps" list in
`docs/ARCHITECTURE.md` — CI configuration, a memo/graph schema migration
tool, or benchmarking the complexity claims are all real, scoped, and don't
require touching the core pipeline's invariants.

## What this project is not looking for

- New target engines beyond the current four — explicitly out of scope per
  the original spec (`docs/acc/001-2026-07-19-polyprompt-build.md`).
- Auto-executing rewritten prompts against the live engines — also
  explicitly out of scope; this tool produces prompts, it doesn't run them.
- Anything that makes validation blocking, or that sends memos off the
  machine outside the explicit `push` command — both are invariants, not
  defaults waiting to be reconsidered casually.

## Questions

Open an issue. If it's a design question rather than a bug, check whether
it's already answered in `docs/acc/` or `docs/scratchpad-*.md` first — a lot
of "why doesn't this do X" questions turn out to be documented, deliberate
rejections.
