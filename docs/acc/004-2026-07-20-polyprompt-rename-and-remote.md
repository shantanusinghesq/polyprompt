# Context Compression — 2026-07-20
**Focus:** forge → polyprompt rename, remote resolution, post-M0-M7 state
**Token estimate before:** ~35k
**Token estimate after:** ~1k

## Decisions
- D: Renamed package/CLI/commands from `forge` to `polyprompt` across directories, console script, slash commands, imports, docs, and CI — because the project is now published under that name (commit `6ac6d57`).
- D: Left `docs/acc/` build log (001–003) with old `forge-*` references untouched — because it is immutable history, not live docs.
- D: Added a claude.ai Skill and documented the "two-surface capability split" — because the plugin now spans two distinct surfaces (commit `b8a197a`).
- D: Added `HANDOFF.md` to `.gitignore` — session-local, not meant to be tracked (commit `21119a2`).
- D: Resolved ACC 003's open question ("no GitHub remote configured") — `origin` now points to `https://github.com/haremantra/polyprompt.git`, local branch tracks it and is up to date.

## Current State
- Package: `polyprompt` (renamed from `forge`), v0.8.0.
- Milestones M0–M7: all shipped.
- Tests: 139 passing.
- Working tree: clean, nothing uncommitted, nothing staged.
- Remote: `origin` = `github.com/haremantra/polyprompt.git`, branch tracking and up to date.
- HEAD: `21119a2`.

## Open Questions
- Q: Is CI green on the new `polyprompt` repo now that it's actually pushed to a real remote? — affects confidence in the rename being fully clean (untested on CI until confirmed).
- Q: v1.0 soak period not started (real prompts, distinct reviewer, mode-correctness labels) — affects readiness to call this production-validated rather than POC.
- Q: Gate thresholds (`K_MIN=5`, `THETA_HIGH=0.7`, etc.) are still unvalidated defaults — affects whether advisory gates (sufficiency, review loop) are tuned correctly.
- Q: Unclear whether the insights-review action item (cap agent fan-out ≤4 concurrent, add to global CLAUDE.md) was ever actioned — check `~/.claude/CLAUDE.md`.

## Rejected Approaches
(none carried forward this cycle)

## Next Actions
1. Confirm CI is green on `github.com/haremantra/polyprompt` post-push.
2. Check `~/.claude/CLAUDE.md` for the insights-review agent-fan-out-cap item; action if missing.
3. Start v1.0 soak period: run real prompts through a distinct reviewer, collect mode-correctness labels.
4. Validate gate thresholds (`K_MIN`, `THETA_HIGH`, etc.) against soak data rather than defaults.
