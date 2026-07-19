# Research Prompt Forge

A Claude Code plugin that rewrites **one** general internet-research prompt into
versions optimized for each AI search engine — **ChatGPT, Gemini, Claude,
Perplexity** — and writes an explanation memo per rewrite. The memos accumulate
into a **knowledge graph of prompt-optimization tactics** that validates future
rewrites.

> Full spec: `../Bloom_playground/docs/prd/research-prompt-forge.md`
> Build sequence: `../Bloom_playground/docs/scratchpad-build-sequence-research-prompt-forge.md`
> Graduation criteria: `../Bloom_playground/docs/poc-to-v1-graduation-criteria.md`

## Status: v0.8.0 — M0–M7 complete

One general prompt → four engine-tuned variants + explanation memos, with per-run mode auto-detection (deep-research vs. chat), a knowledge graph that validates rewrites against accumulated evidence, a reviewer loop that weights that graph, a sufficiency gate that decides when new evidence is worth ingesting, and opt-in private-repo push + monthly profile checkups.

> New here? Start with **`docs/EXPLAINER.md`** — a plain-English walkthrough of the whole pipeline, stage by stage.

| Milestone | State |
|-----------|-------|
| **M0** Scaffold walking skeleton | ✅ done |
| **M1** Rewrite fan-out to 4 engines | ✅ done |
| **M2** Memos + local save + taxonomy.v1 | ✅ done |
| **M3** Mode auto-detector (hybrid) | ✅ done |
| **M4** Knowledge graph + validator | ✅ done |
| **M5** Private repo push (gh) | ✅ done |
| **M6** Review loop → edge weighting | ✅ done |
| **M7** Monthly profile checkup | ✅ done |
| *(post-M7)* Sufficiency gate — should ingest run? | ✅ done |

## Usage

```bash
# all four engines, with the three-question intake answers as flags
python -m forge rewrite --engine all \
  --time-period "2024+" --depth 3 \
  "Compare 15-year TCO of heat pumps vs gas furnaces for a cold-climate US home"

# a single engine
python -m forge rewrite --engine claude "..."

# print the three intake questions
python -m forge intake
```

As a Claude Code plugin, invoke `/forge-prompts` — it runs the three-question intake, then fans out to all four engines:

```
/forge-prompts Compare 15-year TCO of heat pumps vs gas furnaces for a cold-climate US home
```

Other commands: `/forge-review` (rate a memo, weight the graph), `/forge-push` (commit the corpus to a private repo), `/forge-checkup` (monthly profile freshness review). Or drive them directly:

```bash
python -m forge sufficiency          # is there enough new evidence to update the graph?
python -m forge review <memo> --reviewer "..." --intent 5 --quality 5 --explain "..." --mode-correct
python -m forge push --repo my-corpus
python -m forge checkup
```

## Development

```bash
python -m pytest          # run the test suite (M0 exit test lives in tests/)
```

## Layout

```
.claude-plugin/plugin.json   # Claude Code plugin manifest
commands/                    # /forge-prompts, /forge-review, /forge-push, /forge-checkup
forge/
  __main__.py                # `forge` CLI (rewrite, intake, review, push, sufficiency, checkup)
  intake.py                  # three-question intake
  ir.py                      # PromptIR + normalize()
  profile.py                 # PlatformProfile loader + validation
  rewrite.py                 # profile-driven renderers (emit taxonomy tactic IDs)
  mode.py                    # hybrid mode auto-detector (rules + model-fallback seam)
  taxonomy.py                # taxonomy loader
  taxonomy.v1.json           # seed vocabulary: tactics + closed tag dimensions
  memo.py                    # explanation-memo generation + KG frontmatter
  store.py                   # local save + dedupe on (prompt hash, engine)
  graph.py                   # knowledge graph: edge-list, Wilson-LB promotion, archive-not-delete
  validate.py                # advisory (never-blocking) rewrite validation against the graph
  review.py                  # distinct-reviewer ratings -> graph labels
  sufficiency.py             # read-only gate: is there enough new evidence to ingest?
  push.py                    # explicit, opt-in commit of the memo corpus to a private repo
  checkup.py                 # staleness report + version-stamped profile diffs
  profiles/*.json            # 4 versioned, hand-authored platform profiles (+ doc_sources, last_checked)
tests/                       # golden-fixture + schema tests (139 passing)
research-memos/              # generated memos (gitignored; pushed only via `forge push`)
docs/EXPLAINER.md            # plain-English, stage-by-stage walkthrough of the whole pipeline
```

## Memo frontmatter (the knowledge-graph contract)

Each memo is markdown with JSON-valued frontmatter between `---` fences:

```
schema_version, taxonomy_version, source_prompt_hash, engine, mode,
profile_version, tactics: [taxonomy ids], tags: {method, analysis_type,
retrieval_type, subject_matter}, generated_at
```

This is what `forge/graph.py` ingests to build tactic↔tag edges, `forge/validate.py` checks future rewrites against, and `forge/review.py` sidecar files (`<memo>.review.json`) attach ratings to. See `docs/EXPLAINER.md` §3.5–3.9 for how these fit together.
