# Research Prompt Forge

A Claude Code plugin that rewrites **one** general internet-research prompt into
versions optimized for each AI search engine — **ChatGPT, Gemini, Claude,
Perplexity** — and writes an explanation memo per rewrite. The memos accumulate
into a **knowledge graph of prompt-optimization tactics** that validates future
rewrites.

> Full spec: `../Bloom_playground/docs/prd/research-prompt-forge.md`
> Build sequence: `../Bloom_playground/docs/scratchpad-build-sequence-research-prompt-forge.md`
> Graduation criteria: `../Bloom_playground/docs/poc-to-v1-graduation-criteria.md`

## Status: M0 — walking skeleton

Proves the plugin plumbing end to end. **Perplexity only, hardcoded transform.**

| Milestone | State |
|-----------|-------|
| **M0** Scaffold walking skeleton | ✅ in progress |
| M1 Rewrite fan-out to 4 engines | ⬜ |
| M2 Memos + local save + taxonomy.v1 | ⬜ |
| M3 Mode auto-detector (hybrid) | ⬜ |
| M4 Knowledge graph + validator | ⬜ |
| M5 Private repo push (gh) | ⬜ |
| M6 Review loop → edge weighting | ⬜ |
| M7 Monthly profile checkup | ⬜ |

## Usage

```bash
python -m forge rewrite --engine perplexity "Compare 15-year TCO of heat pumps vs gas furnaces, cite 2024+ sources"
```

As a Claude Code plugin, invoke:

```
/forge-prompts Compare 15-year TCO of heat pumps vs gas furnaces, cite 2024+ sources
```

## Development

```bash
python -m pytest          # run the test suite (M0 exit test lives in tests/)
```

## Layout

```
.claude-plugin/plugin.json   # Claude Code plugin manifest
commands/forge-prompts.md    # /forge-prompts slash command
forge/
  __main__.py                # `forge` CLI
  ir.py                      # PromptIR (M0 stub; M1 fills it in)
  engines/perplexity.py      # M0 hardcoded transform
tests/                       # golden-fixture + schema tests
```
