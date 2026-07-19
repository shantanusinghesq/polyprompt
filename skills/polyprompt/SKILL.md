---
name: polyprompt
description: Use when the user pastes a research question and asks to optimize/tune it for ChatGPT, Gemini, Claude, or Perplexity, or asks "rewrite this prompt for each AI engine." Runs the bundled polyprompt engine via code execution to deterministically produce one tuned prompt variant per requested engine, each with its applied tactics listed. Do NOT use for general prompt-writing advice with no specific engine target — that's plain reasoning, not this skill.
---

# polyprompt — one prompt, tuned per engine

Deterministically rewrites one general research prompt into engine-specific
variants using a fixed tactic taxonomy (not free-form rephrasing). Source of
truth: https://github.com/haremantra/polyprompt.

## Input

The user's raw research prompt, plus (optional) which engine(s) they want:
`chatgpt`, `gemini`, `claude`, `perplexity`, or `all` (default: `all`).

If the user hasn't specified engines and it's ambiguous, ask once; otherwise
default to `all`.

## Process

1. Run the bundled CLI via code execution — do not hand-rewrite the prompt
   yourself, the value of this skill is the deterministic tactic engine, not
   free-form rephrasing:

   ```bash
   cd scripts && python3 -m polyprompt rewrite --engine <engine|all> "<the user's prompt>"
   ```

2. If the user's question implies extra context (a time window, a required
   depth, a source preference — e.g. "recent," "peer-reviewed only," "quick
   answer"), pass it through flags instead of editing the prompt text:
   `--time-period`, `--depth`, `--clarify`. Check `--help` if unsure:

   ```bash
   cd scripts && python3 -m polyprompt rewrite --help
   ```

3. Return the tool's output directly to the user: the detected mode
   (deep-research vs. chat) and, per engine, the tuned prompt plus its
   applied-tactics list. Don't summarize away the tactics list — it's the
   explanation of *why* the rewrite differs per engine.

## Scope note

This skill only runs the stateless rewrite engine (`rewrite`, `intake`,
`mode`, `taxonomy`). The full CLI also has `push`, `checkup`, and a
knowledge-graph review loop (`review`, `graph`) that accumulate evidence
across runs on local disk and push to a private GitHub repo — those need a
persistent filesystem and `gh` auth this sandbox doesn't have, so don't
attempt them here. For that workflow, point the user to the CLI:
`pip install -e .` from the repo above.

## Anti-Patterns

- Don't paraphrase the prompt yourself and skip the script — that defeats
  the point of a deterministic, versioned tactic taxonomy.
- Don't attempt `push`/`checkup`/`review` in this sandbox; they require
  state and auth that don't persist here.
