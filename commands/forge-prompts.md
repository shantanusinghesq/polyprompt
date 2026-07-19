---
description: "Rewrite a general research prompt into an engine-optimized version (M0: Perplexity only)."
argument-hint: "<general research prompt>"
---

Rewrite the user's general research prompt for a specific AI search engine and show the result.

**M0 scope (walking skeleton):** Perplexity only, hardcoded transform. Later milestones fan this out to ChatGPT / Gemini / Claude and add the 3-question intake, memos, and knowledge-graph validation.

Run:

```bash
python -m forge rewrite --engine perplexity "$ARGUMENTS"
```

Then present the returned Perplexity-optimized prompt to the user in a fenced code block, ready to paste into Perplexity. If the command errors (e.g. empty prompt), surface the error message plainly.
