---
description: "Rewrite a general research prompt into ChatGPT/Gemini/Claude/Perplexity-optimized versions."
argument-hint: "<general research prompt>"
---

Rewrite the user's general research prompt into a version optimized for each AI search engine, then show all four.

**Step 1 — run the three-question intake.** Ask the user these (skip Q3 if the prompt is already unambiguous):

```bash
python -m polyprompt intake
```

1. Time period / recency window
2. Depth of reasoning / issue-spotting (1 = quick, 2 = standard, 3 = deep)
3. Anything ambiguous to pin down (scope, definitions, audience)

**Step 2 — rewrite for all engines** with the collected answers, saving an explanation memo per rewrite:

```bash
python -m polyprompt rewrite --engine all \
  --time-period "<answer 1>" \
  --depth <answer 2> \
  --clarify "<answer 3>" \
  --memos research-memos \
  "$ARGUMENTS"
```

**Step 3 — present the output.** Show each engine's rewritten prompt in its own fenced code block (ready to paste), followed by its applied tactics. Each rewrite also writes an explanation memo (with knowledge-graph frontmatter) under `research-memos/`; report the memo paths. Note that all four run in `deep-research` mode (M1 default; per-run mode auto-detection arrives in M3). If `rewrite` errors (e.g. empty prompt), surface the message plainly.
