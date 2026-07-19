# Context Compression — 2026-07-19
**Focus:** full session (docs overhaul + CI + claude-config repair; M4–M7 build covered in ACC 002)
**Token estimate before:** ~180k
**Token estimate after:** ~1.4k

## Decisions
- D: No M8 exists — PRD/build-sequence define only M0–M7, all shipped. Next-value work identified as documentation, not code (`docs/scratchpad-m8-vs-explainer.md`, CoVE-verified: grep for "M8" across all planning docs returns zero matches).
- D: `docs/EXPLAINER.md` written as progressive disclosure (plain-English → per-stage mechanism detail) rather than splitting by audience — same document, increasing depth.
- D: `docs/ARCHITECTURE.md` added as a separate scannable reference (module dep graph, data contracts, 7 stated invariants, complexity notes, honest gaps) — narrative and reference are different document shapes, not one extended doc. Prompted by maintainer-role review finding EXPLAINER reads beginner-friendly only through §1–2, then mid-level+ by §3.6 (Wilson-LB, advisory-vs-blocking architecture) — extending prose wouldn't fix that gap; a different document shape was needed.
- D: MIT license adopted; `LICENSE` + `pyproject.toml` `license` field added.
- D: Global `~/.claude/CLAUDE.md` was a missing symlink (target `~/claude-config/claude/CLAUDE.md` intact; likely lost during `_archived-context-20260713` cleanup) — relinked matching the repo's existing symlink pattern (settings.json, skills, scripts, statusline-command.sh all point into `~/claude-config/claude/`).
- D: `claude-config` repo: merged `origin/main` (4 remote commits — 14 vendored `mattpocock/skills`) with 6 local commits (CLAUDE.md fixes, statusline, settings, model-default change) — no conflicts, `git merge --no-edit` then pushed. Now at `609b179`, in sync.
- D: CI test run shadows `git`/`gh` with exit-127 stubs — verified NOT functionally required (grepped: every push-touching test injects a fake `Runner` or patches `forge.push.make_runner`, no test builds a real `SubprocessRunner`) — added anyway as a regression guard so a future dropped test seam fails loudly instead of silently passing or shelling out for real.

## Current State
- Repo `~/Projects/research-prompt-forge`, main, **v0.8.0, 139 tests passing**. Commits this session: `89b1574` (EXPLAINER+README refresh), `2ab74c2` (LICENSE+install docs+per-agent guide+pyproject sync), `b4262cf` (ARCHITECTURE.md+CONTRIBUTING.md), `54a15bf` (CI workflow).
- New files: `LICENSE` (MIT), `CONTRIBUTING.md`, `docs/EXPLAINER.md`, `docs/ARCHITECTURE.md`, `.github/workflows/ci.yml`, `docs/scratchpad-m8-vs-explainer.md`.
- `pyproject.toml`: version synced 0.3.0→0.8.0 (was 5 milestones stale), `license` field added.
- **`.github/workflows/ci.yml`**: matrix py3.10/3.11/3.12, `pip install -e ".[dev]"`, `forge --version` check, pytest with git/gh stubbed. Dry-run verified locally in clean venv before commit (139 passed).
- **README badge + clone URLs point at `github.com/haremantra/research-prompt-forge` — repo has NO remote configured** (`git remote -v` empty). CI will not actually run until pushed. Flagged explicitly to user, not yet actioned.
- `~/.claude/CLAUDE.md` is now `-> ~/claude-config/claude/CLAUDE.md` (symlink recreated; global instructions load again from next session).
- `claude-config` repo: `main` == `origin/main` @ `609b179`, clean.
- Insights-review run: snapshot saved `~/.claude/insights-history/2026-07-19-095936.json`, state.json 45 tracked items. Load-bearing pick surfaced but not actioned: cap adversarial-audit fan-out to ≤4 concurrent agents + guaranteed cleanup (recurring theme, cheapest fix). No global CLAUDE.md existed at review time (pre-fix) to encode this — worth adding now that the symlink is restored.
- Sholay session closed: `~/sholay-archive/20260719-091645-memo-sufficiency-gate-loop/` (gate ideation source, synthesized into `docs/scratchpad-memo-sufficiency-gate.md`).

## Open Questions
- Q: research-prompt-forge has no GitHub remote — badge/clone URLs are aspirational until pushed. User asked "is that a step you're handling yourself?" — unanswered at session end.
- Q: v1.0 graduation soak period still not started (carried from ACC 002) — real prompts, distinct reviewer, mode-correctness labels.
- Q: Gate thresholds (K_MIN=5, THETA_HIGH=0.7, DIVERSITY_MIN=3, MIN_PENDING_MEMOS=3, STALE_DAYS=30) remain unvalidated defaults.
- Q: Insights-review's load-bearing pick (bound adversarial-audit fan-out to ≤4 agents) was surfaced but never added to `~/.claude/CLAUDE.md` — the file didn't exist/wasn't linked at review time; now it is, so this is actionable.

## Rejected Approaches
- X: Inventing an "M8" milestone to keep building code — no spec basis; documentation was the actual gap.
- X: Extending `EXPLAINER.md` further to also serve experts — wrong document shape; reference docs need scanability, not more narrative depth.
- X: Splitting explainer into separate per-audience documents — user wants one continuous ramp, not a choice between docs.
- X: Force-push or rebase to resolve `claude-config` divergence — clean merge was possible (no conflicts, additive remote changes), so ordinary `git merge` was correct and safer.
- X: Fabricating Perplexity/Claude-Desktop repo-clone instructions — corrected instead: Perplexity is a rewrite *target*, not a host with shell access; Claude Desktop needs a terminal or MCP shell access, can't clone via chat alone.

## Next Actions
1. Decide whether to create the GitHub remote for research-prompt-forge and push (badge/clone URLs currently point at nothing).
2. Add the insights-review load-bearing pick to `~/.claude/CLAUDE.md` now that the symlink is fixed: cap adversarial-audit/exploration fan-out at ≤4 concurrent agents + guaranteed process cleanup.
3. If/when a soak period starts (real prompts + reviewer ratings), revisit the unvalidated gate thresholds noted in `docs/ARCHITECTURE.md`'s Known Gaps.
4. `~/.claude/insights-history/state.json` has `friction:uncontrolled-agent-fan-out-and-orphaned-processes` open — ack/resolve once #2 above lands (`/insights-review ack <id>`).
