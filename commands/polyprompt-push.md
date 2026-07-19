---
description: "Commit the local research-memo corpus to a private GitHub repo (explicit, opt-in)."
argument-hint: "[repo-slug]"
---

Push the accumulated explanation-memo corpus to a **private** GitHub repository. This is the only path that sends memos off the machine, and it is always explicit — memos are local-by-default (PRD FR-5) and never auto-committed.

**Preconditions:** `gh` is installed and authenticated (the auth prompt surfaces in the Claude Code UI). The corpus directory (`research-memos/`) is its own independent git repo — first-class and separately pushable from the plugin repo.

**Run the push:**

```bash
python -m polyprompt push --dir research-memos --repo "${ARGUMENTS:-polyprompt-corpus}"
```

What it does, in order: ensures `research-memos/` is a git repo (`git init` if needed); stages and commits the memos; ensures a **private** `origin` repo exists (creating it via `gh repo create --private` when absent — pass `--no-create` to refuse that); pushes.

**Report the outcome** from the `[status]` line:
- `pushed` — corpus reached the private repo.
- `noop` — nothing new since the last push.
- `local` — committed locally but **not** pushed (offline / auth / remote issue). The local copy is retained; tell the user to re-run once resolved. Exit code is non-zero.
- `failed` — no corpus to push (empty or missing directory).

On any failure the local memos are never lost — always surface that the copy is retained and what to fix.
