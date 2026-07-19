# Architecture reference

Scannable, not narrative — for readers deciding whether to adopt, fork, or
contribute. If you want the story instead of the reference, read
`docs/EXPLAINER.md`. If you want the decision trail (options considered,
rejected, why), read `docs/acc/` and `docs/scratchpad-*.md`.

## Module dependency graph

```
__main__ (CLI) ─┬─> intake   ─> (leaf)
                ├─> ir        ─> intake
                ├─> mode      ─> ir
                ├─> profile   ─> (leaf)
                ├─> rewrite   ─> ir, mode, profile
                ├─> taxonomy  ─> (leaf)
                ├─> memo      ─> ir, rewrite, taxonomy
                ├─> store     ─> memo
                ├─> graph     ─> memo, taxonomy
                ├─> validate  ─> graph
                ├─> review    ─> graph
                ├─> sufficiency ─> graph, memo
                ├─> push      ─> (leaf; subprocess only)
                └─> checkup   ─> profile
```

Acyclic by construction — no module imports `__main__`, and there is no cycle
among `forge/*.py`. `intake` → `taxonomy` → `profile` are the only true
leaves (zero internal deps); everything else composes from there. 1,954 total
lines across 15 modules (`wc -l forge/*.py`); the largest single file is
`__main__.py` (386 lines — CLI argument wiring for 6 subcommands, deliberately
thin: every subcommand delegates to a pure function in its own module within
a few lines).

## Data flow (one full run)

```
raw prompt + 3 intake answers
        │  ir.normalize()               — deterministic, no I/O, no model call
        ▼
     PromptIR
        │  mode.detect_mode()           — rules first; model_fallback only on margin ties
        ▼
   ModeDecision {mode, reason, source}
        │  rewrite.rewrite() × 4 engines — one renderer per PlatformProfile.structure
        ▼
   RewriteResult {prompt, tactics: [taxonomy ids], mode, ...}
        │  memo.build_memo()
        ▼
   Memo {frontmatter (JSON), body (markdown)}
        │  store.save_memo()            — dedupe key (source_prompt_hash, engine)
        ▼
   research-memos/*.md  (local, gitignored, never auto-committed)
        │  graph.ingest_memo()          — explicit; not run on every rewrite
        ▼
   Graph { edges: {(tactic, dim, value): Edge(pos, neg, provenance, status)} }
        │  validate.validate()          — advisory only, next rewrite's tactics vs. graph
        ▼
   list[Flag]  (printed, never affects exit code or output)
```

## Core data contracts

### `PromptIR` (`forge/ir.py`)
| Field | Type | Notes |
|---|---|---|
| `intent` | `str` | whitespace-normalized original prompt |
| `depth` / `reasoning_layers` | `str` / `int` | from intake answer 2, defaults to `2` ("standard") |
| `recency_window` | `str` | from intake answer 1, or inferred from a `20\d{2}` in the prompt |
| `source_preferences` | `list[str]` | keyword-matched, insertion-order-preserved |
| `constraints` | `list[str]` | from intake answer 3 (free text) |

`normalize()` raises `ValueError` on an empty/whitespace-only prompt; that's
the only failure mode.

### Memo frontmatter (`forge/memo.py`)
JSON-valued lines between `---` fences (not YAML — chosen for zero
dependencies and lossless round-trip; see `render_frontmatter`/
`parse_frontmatter`).

```
schema_version, taxonomy_version, source_prompt_hash, engine, mode,
mode_source, mode_reason, profile_version, tactics: [taxonomy ids],
tags: {method, analysis_type, retrieval_type, subject_matter}, generated_at
```

`SCHEMA_VERSION = "1"` (`forge/memo.py:25`). No compatibility policy is
defined yet — treat any bump as breaking until one is written (tracked as an
open gap, see below).

### Graph edge (`forge/graph.py`)
| Field | Type | Meaning |
|---|---|---|
| `tactic, dimension, value` | `str` | composite key: e.g. `("role-framing", "engine", "chatgpt")` |
| `pos, neg` | `int` | label counts; `support = pos + neg` |
| `provenance` | `"seed" \| "label"` | seed edges always carry `pos=neg=0` |
| `status` | `"active" \| "archived"` | archive-not-delete; archived edges never promote |
| `weight` | computed | Wilson score lower bound of `pos / support` |
| `promoted` | computed | `status == "active" and support >= K_MIN and weight >= THETA_HIGH` |
| `contra` | computed | same gate, applied to the *negative* rate |

Graph JSON schema is `"schema_version": "1"` at the top level (distinct
counter from the memo schema version — don't conflate the two).
`load_graph()` on a file missing `status`/`reviewed` (pre-M6 schema) defaults
`status="active"` and `reviewed=set()` — this is the only backward-compat
path currently implemented, and it's implicit (default values), not an
explicit migration.

## Invariants (the guarantees this system actually holds)

These are stated once here; the narrative doc explains *why* each one exists.

1. **`ir.normalize()` and `rewrite.rewrite()` are pure and deterministic.** No
   network I/O, no model call, no wall-clock dependency. Same input → same
   output, every time. This is what makes the golden-fixture test strategy
   (`tests/test_m1_*.py` etc.) valid at all.
2. **Validation never blocks.** `validate.validate()` returns `list[Flag]`;
   nothing in `__main__._cmd_rewrite` branches the exit code on it. If you're
   extending this codebase, do not add a code path where a flag changes
   program behavior — that would violate a design decision held consistently
   since M4 (`docs/scratchpad-memo-sufficiency-gate.md`, D-03).
3. **Seed edges cannot self-promote.** `provenance="seed"` edges are created
   with `pos=neg=0` and stay that way unless real labels land on the same
   key — `Edge.promoted` requires `support >= K_MIN=5`, so a seed alone can
   never satisfy it (`forge/graph.py`, `Edge.promoted`, ~line 78).
4. **Archive, never delete.** `Graph.archive_contra()` flips `status` to
   `"archived"`; it never removes a key from `edges`. `required_tactics()`
   filters `status == "active"` — an archived edge is excluded from
   validation but remains on disk and in history.
5. **`sufficiency.assess()` is read-only.** It operates on `copy.deepcopy(graph)`
   and never mutates the caller's graph or touches disk. Verified by
   `tests/test_sufficiency.py::TestPromotionSimulation::test_assess_is_read_only`.
6. **The only code path that leaves the machine is `forge/push.py`, and only
   on explicit invocation.** No other module performs network I/O. `push`
   itself never deletes local memos — failure states (`"local"`, `"failed"`)
   always retain the local copy (`forge/push.py`, `PushResult.report`).
7. **Reviewer identity is part of the dedupe key.** `graph.reviewed` keys on
   `(source_prompt_hash, engine, reviewer)` — the same person re-reviewing
   the same memo is a no-op; a second, distinct reviewer's opinion counts
   (`forge/review.py`, `apply_review()`).

## Complexity / scale notes

- **Promotion simulation is O(edges).** `sufficiency.assess()` deep-copies
  the full graph and replays pending memos against it — fine for the current
  scale (a personal research corpus), not benchmarked past that. If you're
  evaluating this for a large shared corpus, this is the first thing to
  profile.
- **Graph persistence is a single flat JSON file**, loaded and rewritten in
  full on every mutation (`save_graph`/`load_graph` in `forge/graph.py`).
  This was an explicit design choice — git-native, diffable, no DB dependency
  (PRD Q1; `docs/acc/001-2026-07-19-research-prompt-forge-build.md`) — but it
  means write cost is O(total edges), not O(changed edges).
- **Memo corpus scan is O(files) per command.** `store.existing_keys()`,
  `sufficiency._scan_memos()`, and `push._corpus_files()` each glob and parse
  the full `research-memos/` directory. No caching or incremental index
  exists yet.

## Known gaps (honest, as of v0.8.0)

These are real absences, not oversights hidden from you:

- **No CI configuration.** `python -m pytest` (139 tests) must be run
  manually before every commit; nothing enforces this on push or PR.
- **No memo/graph schema migration tooling beyond implicit defaults.** A
  `schema_version` bump has no defined upgrade path.
- **No performance benchmarks.** The complexity notes above are structural
  reasoning, not measured numbers.
- **Per-mode rendering is not implemented.** Renderers are mode-agnostic —
  a `chat`-mode rewrite still emits the same verbose prompt shape as
  `deep-research` (tracked in `docs/acc/001-2026-07-19-research-prompt-forge-build.md`, Open Questions).
- **Gate thresholds are unvalidated defaults.** `K_MIN=5`, `THETA_HIGH=0.7`,
  `DIVERSITY_MIN=3`, `MIN_PENDING_MEMOS=3`, `STALE_DAYS=30` are engineering
  judgment calls, not derived from data — there hasn't been a real usage
  soak period yet to validate them (`docs/acc/002-2026-07-19-m4-m7-complete.md`, Open Questions).
