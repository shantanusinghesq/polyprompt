# Research Prompt Forge

A Claude Code plugin that rewrites **one** general internet-research prompt into
versions optimized for each AI search engine — **ChatGPT, Gemini, Claude,
Perplexity** — and writes an explanation memo per rewrite. The memos accumulate
into a **knowledge graph of prompt-optimization tactics** that validates future
rewrites.

> Full spec: `../Bloom_playground/docs/prd/research-prompt-forge.md`
> Build sequence: `../Bloom_playground/docs/scratchpad-build-sequence-research-prompt-forge.md`
> Graduation criteria: `../Bloom_playground/docs/poc-to-v1-graduation-criteria.md`

## Status: M1 — rewrite fan-out to 4 engines

One general prompt → four engine-tuned variants, each with a change summary. Mode is hardcoded to `deep-research` (auto-detection lands in M3).

| Milestone | State |
|-----------|-------|
| **M0** Scaffold walking skeleton | ✅ done |
| **M1** Rewrite fan-out to 4 engines | ✅ done |
| M2 Memos + local save + taxonomy.v1 | ⬜ |
| M3 Mode auto-detector (hybrid) | ⬜ |
| M4 Knowledge graph + validator | ⬜ |
| M5 Private repo push (gh) | ⬜ |
| M6 Review loop → edge weighting | ⬜ |
| M7 Monthly profile checkup | ⬜ |

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

## Development

```bash
python -m pytest          # run the test suite (M0 exit test lives in tests/)
```

## Layout

```
.claude-plugin/plugin.json   # Claude Code plugin manifest
commands/forge-prompts.md    # /forge-prompts slash command (runs intake, fans out)
forge/
  __main__.py                # `forge` CLI (rewrite, intake)
  intake.py                  # three-question intake
  ir.py                      # PromptIR + normalize()
  profile.py                 # PlatformProfile loader + validation
  rewrite.py                 # profile-driven per-structure renderers
  profiles/*.json            # 4 versioned, hand-authored platform profiles
tests/                       # golden-fixture + schema tests
```
