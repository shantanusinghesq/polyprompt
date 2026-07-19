# Research Prompt Forge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A CLI (and Claude Code plugin) that rewrites **one** general internet-research
prompt into versions optimized for each AI search engine — **ChatGPT, Gemini,
Claude, Perplexity** — and writes an explanation memo per rewrite. The memos
accumulate into a **knowledge graph of prompt-optimization tactics** that
validates future rewrites.

> Full engineering trail lives in-repo: `docs/EXPLAINER.md` (start here),
> `docs/acc/` (build-decision log), `docs/scratchpad-*.md` (individual decision
> records with rejected alternatives).

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

## Install

Requires Python 3.10+. No third-party runtime dependencies — the core is pure
stdlib (deliberately: see `docs/EXPLAINER.md` §3.2 on why the deterministic
core stays dependency-free).

```bash
git clone https://github.com/haremantra/research-prompt-forge.git
cd research-prompt-forge
pip install -e .          # installs the `forge` CLI (editable)
forge --version
```

That's the whole install, everywhere — it's a plain Python package, so the
steps above are identical whether you're typing them into a regular terminal
or an agentic coding tool's shell. The differences below are only about how
each tool *uses* the repo once it's cloned.

### If you're using an agentic coding CLI

**Codex, Gemini CLI, or Claude Code (as a bare CLI tool):** nothing special —
paste the three commands above into the agent's shell/bash tool and it runs
exactly like it would for you locally. These tools can `git clone` and `pip
install` on their own if you ask them to ("clone
`https://github.com/haremantra/research-prompt-forge` and set it up").

**Claude Code (as a plugin, for the `/forge-*` slash commands):** the repo
ships a plugin manifest (`.claude-plugin/plugin.json`) and slash commands
(`commands/*.md`). After cloning, either open Claude Code with this directory
as your project root (commands are picked up automatically), or add it as a
plugin from a local path:
```
/plugin marketplace add /path/to/research-prompt-forge
/plugin install research-prompt-forge
```
Either way you get `/forge-prompts`, `/forge-review`, `/forge-push`, and
`/forge-checkup` in addition to the bare `forge` CLI.

**Claude Desktop:** Desktop chat alone has no shell or `git` access — it can't
clone a repo by itself. Clone it in a regular terminal first (`git clone` +
`pip install -e .` above), then either run `forge` yourself and paste the
output into Desktop, or, if you have an MCP server with filesystem/shell
access configured, point it at the cloned directory so Desktop can drive it
directly.

**Perplexity:** not applicable here — Perplexity has no local shell or repo
access, and in this project it isn't a host for the tool at all. It's one of
the four **target engines** `forge` rewrites prompts *for* (see `--engine
perplexity` below). The way you'd actually use this tool with Perplexity is:
run `forge` anywhere else, then paste the Perplexity-tuned rewrite into
perplexity.ai yourself.

## Usage

**Day one — the core loop.** This is the only thing you need to try it once:

```bash
# all four engines, with the three-question intake answers as flags
forge rewrite --engine all \
  --time-period "2024+" --depth 3 \
  "Compare 15-year TCO of heat pumps vs gas furnaces for a cold-climate US home"

# a single engine
forge rewrite --engine claude "..."

# print the three intake questions
forge intake
```

As a Claude Code plugin, invoke `/forge-prompts` — same thing, conversational intake:

```
/forge-prompts Compare 15-year TCO of heat pumps vs gas furnaces for a cold-climate US home
```

**Later — optional, once you have a memo corpus.** None of these are needed
for the core loop above; they exist for building up and maintaining the
knowledge graph over time (see `docs/EXPLAINER.md` §3.6–3.11):

```bash
forge sufficiency          # read-only: is there enough new evidence to update the graph?
forge review <memo> --reviewer "..." --intent 5 --quality 5 --explain "..." --mode-correct
forge push --repo my-corpus    # explicit, opt-in: commit memos to a private GitHub repo
forge checkup               # monthly: are the 4 platform profiles still accurate?
```

Corresponding slash commands: `/forge-review`, `/forge-push`, `/forge-checkup`.

## Development

```bash
pip install -e ".[dev]"   # adds pytest
python -m pytest          # run the test suite (139 tests)
```

## Layout

```
LICENSE                      # MIT
pyproject.toml               # package metadata; `forge` console-script entry point
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
