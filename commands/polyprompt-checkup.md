---
description: "Monthly profile checkup: review vendor docs and propose version-stamped platform-profile updates."
argument-hint: "[engine]"
---

Keep the four platform profiles current against vendor primary documentation (PRD FR-8). User-invoked, roughly monthly.

**Step 1 — staleness report:**

```bash
python -m polyprompt checkup
```

This lists each engine's profile version, when it was last checked (STALE after 30 days), and the vendor doc URLs to review.

**Step 2 — review the primary docs** for each stale engine (or just `$ARGUMENTS` if given): fetch the listed `doc:` URLs and compare against the profile fields (`structure`, `length`, `source_filter_syntax`, `strengths`, `directives`, `notes`, `default_mode`, `doc_sources`). Look for: changed deep-research behavior, new/removed search operators, new prompt-structure guidance, changed verbosity sweet spots.

**Step 3 — propose (never silently apply).** For each real change, build a version-stamped proposal and show the user the diff:

```bash
python -m polyprompt checkup --engine <engine> \
  --set field='<json value>' [--set field2='<json>'...]
```

The output shows `old_version -> new_version` (stamped `YYYY.MM.N`) and every field's old → new value. `engine`, `version`, and `last_checked` cannot be set — they are managed stamps.

**Step 4 — apply only with user approval:** re-run the same command with `--apply`. This writes the profile with the new version and today's `last_checked`.

If the docs show no changes for an engine, say so — an explicit "no change, profiles current" is a valid checkup outcome (do not invent diffs). Note: profile *structure* updates are this checkup's job; label ingest is governed separately by the sufficiency gate (`polyprompt sufficiency`).
