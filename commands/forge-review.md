---
description: "Record a distinct reviewer's rating for an explanation memo; ratings weight the knowledge graph."
argument-hint: "<memo path>"
---

Capture an independent review of one explanation memo (PRD FR-7). The reviewer must be a **distinct person**, not the prompt author — ask who is reviewing.

**Collect from the reviewer:**
1. Intent fidelity (1–5): does the rewrite preserve what the original prompt asked?
2. Quality (1–5): is the rewrite genuinely better for its target engine?
3. Depth-of-reasoning explanation: a sentence or two justifying the ratings.
4. Mode correctness: was the detected mode (in the memo frontmatter) right?

**Run:**

```bash
python -m forge review "$ARGUMENTS" \
  --reviewer "<name>" \
  --intent <1-5> \
  --quality <1-5> \
  --explain "<explanation>" \
  --mode-correct   # or --mode-wrong
```

The review is stored with the memo as `<memo>.review.json`, and its sentiment updates the knowledge graph (`research-memos/graph.json` by default; override with `--graph`): both ratings ≥ 4 → positive labels; either ≤ 2 → negative labels; otherwise recorded with no labels. One vote per reviewer per memo. Sustained negatives archive an edge (never delete).

**Report:** the sentiment applied, any newly archived contra edges, and the running mode-detector accuracy the command prints.
