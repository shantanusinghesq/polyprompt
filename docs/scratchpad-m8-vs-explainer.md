# Scratchpad — Build M8 or write a humanized plugin explainer?
**Status:** Draft (pre-CoVE)
**Date opened:** 2026-07-19

### D-01 — Is there real "M8" work, or is the next unit of value a humanized explainer?

**Options considered:**
- A: Write a humanized explainer doc (vibe-coder → expert) — no new code.
- B: Invent an "M8" milestone (e.g. per-mode rendering, taxonomy growth process) and build it.
- C: Do both — explainer first, M8-shaped work only if the explainer surfaces a real gap.

**Accepted:** Option A now, with C as the standing default going forward — CoVE-01 (below) confirms no M8 was ever specified; inventing scope the PRD/build-sequence never asked for would be exactly the kind of unrequested feature work the project's own conventions warn against. The README is also concretely stale (frozen at M3, 13 modules out of date), which is a real, cheap-to-fix gap — higher value per hour than speculative new code right now.

**Rejected:** Option B
**Reasoning against B:** `docs/scratchpad-build-sequence-research-prompt-forge.md` and the PRD define exactly M0–M7, all shipped (v0.8.0, 139 tests, `docs/acc/002-2026-07-19-m4-m7-complete.md`). The only unresolved forward work already on record is the **soak period** (real prompts, real reviewer ratings) — a *usage* activity, not a *build* milestone. Manufacturing an M8 to keep building would be solving a code problem where there isn't one.

**Rejected:** Option C as a hard gate before starting
**Reasoning against C (as a blocker):** Waiting to see "does the explainer reveal a gap" before starting is unnecessary — the explainer is valuable on its own regardless of whether it turns up gaps; treating it as pure a means to an end undersells it. Accepted as a *sequel* posture instead (explainer now; M8-shaped work only if reading forces one to light up), not as a precondition.

**Assumption accepted:** The user's "M8" is shorthand for "keep going / next thing," not a citation to a real planning artifact — verified by CoVE-01.
**Assumption rejected:** "More code is always the next milestone" — rejected; a finished, tested pipeline with a stale README is under-documented, not under-built.

### D-02 — What form should the explainer take?

| Criterion | A. Rewrite README.md in place | B. Standalone EXPLAINER.md (layered) | C. Multiple docs (one per audience) |
|-----------|-------------------------------|----------------------------------------|--------------------------------------|
| Discoverability | High (first file anyone opens) | Medium (needs a README link) | Low (fragments attention) |
| Serves "vibe coder → expert" span in one read | Poor — README convention expects terse | **Good — progressive disclosure in one doc** | Good per-section, bad for skimming |
| Maintenance burden | Low (one file) | Low (one file) | High (N files drift independently) |
| Keeps README's existing job (quickstart/layout) intact | No — bloats it | **Yes — README stays terse, links out** | Yes |

**Accepted:** Option B — a new `docs/EXPLAINER.md`, written as **progressive disclosure**: starts with a plain-English "what this is and why" a vibe coder can read in 60 seconds, then descends through the pipeline stage by stage (intake → IR → rewrite → memo → graph → validate → review → sufficiency → push → checkup) with just enough code/schema detail at each stage for an expert to verify the claim against the file. README gets a one-line pointer, not a rewrite.

**Rejected:** Option A
**Reasoning against A:** READMEs are conventionally scannable-in-30-seconds documents (install/usage/layout); stretching one to also teach the *why* behind Wilson-LB promotion, advisory-never-blocking validation, and the sufficiency gate's diversity veto would make it useless as a quick-reference and still not build genuine understanding.

**Rejected:** Option C
**Reasoning against C:** The explicit ask is "humanized... suitable for a vibe coder to expert" — i.e. one continuous ramp, not separate documents the reader has to choose between. Splitting by audience also means two docs go stale independently; this project already has one stale doc (README) from a previous milestone-boundary miss.

**Assumption accepted:** Progressive disclosure (plain language first, mechanism detail later in the same document) can serve both audiences without patronizing the expert or losing the beginner — the same technique the codebase itself already uses in docstrings (e.g. `forge/graph.py`'s module docstring explains Wilson-LB in one sentence before the code defines it).
**Assumption rejected:** "A vibe coder and an expert need genuinely different documents" — rejected for this artifact; they need different *depths of the same document*, reachable by reading further, not by picking a different file.

### D-03 — Does the explainer also need to fix the stale README, or is that separate scope?

**Options considered:**
- A: Refresh README's status table + layout section as part of this same pass (it's already open, already stale, directly adjacent).
- B: Leave README as-is; file a separate note for later.

**Accepted:** Option A — the milestone table showing "M4–M7 ⬜" is actively wrong (all four are ✅, plus the sufficiency gate which isn't in the sequence at all) and would mislead exactly the vibe-coder reader the explainer is written for if they hit it first. Fixing it is minutes of work already touching this area.

**Rejected:** Option B
**Reasoning against B:** Deferring a known-wrong status table for "later" when the fix is a five-line diff and the file is already open is the kind of avoidable second pass the project's git/verification discipline (seen throughout M4–M7 commits) argues against.

**Assumption accepted:** A short README update (status table + layout list) is in scope as "finishing the stale-doc problem the explainer surfaced," not scope creep beyond the ask.

## Assumptions Register

### Accepted Assumptions
| ID | Assumption | Rationale | Decision |
|---|---|---|---|
| AA-01 | "M8" is shorthand, not a real planning citation | No M8 in PRD/build-sequence (CoVE-01) | D-01 |
| AA-02 | Progressive disclosure serves both audiences in one doc | Matches existing docstring style in the codebase | D-02 |
| AA-03 | README status-table fix is in-scope, not creep | Directly adjacent, already-open, minutes of work | D-03 |

### Rejected Assumptions
| ID | Assumption | Why Rejected | Decision |
|---|---|---|---|
| RA-01 | More code is always the next milestone | Pipeline is fully built and tested; the real gap is documentation, not features | D-01 |
| RA-02 | Explainer must be justified by a gap it later reveals | It has standalone value regardless | D-01 |
| RA-03 | Vibe coder and expert need separate documents | They need different depths of the same document | D-02 |

## CoVE Verification Questions
| ID | Question | Decision it affects |
|---|---|---|
| CoVE-01 | Does any planning doc (PRD, build-sequence, graduation criteria) define an "M8"? | D-01 |
| CoVE-02 | Is the README's milestone table actually out of date, and by how much? | D-03 |

## CoVE Answers

### CoVE-01 — does M8 exist anywhere?
**FINDING:** NO. `grep -n -i "M8"` across `Bloom_playground/docs/scratchpad-build-sequence-research-prompt-forge.md`, `prd/research-prompt-forge.md`, and `poc-to-v1-graduation-criteria.md` returns zero matches. The build sequence table (build-sequence doc, lines 13–24) defines exactly M0 through M7, all of which are shipped per `docs/acc/002-2026-07-19-m4-m7-complete.md`.
**Impact:** Confirms D-01's Option A/C — there is no spec to build against for "M8"; any such work would be invented scope.

### CoVE-02 — is the README stale?
**FINDING:** YES, materially. `README.md:13` still reads "Status: M3 — hybrid mode auto-detector" and the table (lines 17–26) marks M4, M5, M6, M7 as ⬜ (not started) when all four are ✅ done at v0.8.0. The Layout section (lines 55–74) lists only M0–M2 modules and omits `graph.py`, `validate.py`, `push.py`, `review.py`, `sufficiency.py`, `checkup.py` — six of twelve `forge/` modules are undocumented there. The Memo frontmatter section (lines 76–84) is still accurate (unchanged since M2) but incomplete without a graph/review pointer.
**Impact:** Confirms D-03 — this isn't a hypothetical staleness risk, it's actively wrong and worth fixing in the same pass.

## Next Actions
1. Write `docs/EXPLAINER.md` — progressive disclosure, plain-English opener through to per-stage mechanism detail, covering the full pipeline (intake → IR → rewrite → memo → graph → validate → review → sufficiency → push → checkup).
2. Refresh `README.md`: status table (M0–M7 ✅, note the sufficiency gate as a post-M7 addition), Layout section (add the six missing modules + new commands), one-line pointer to `docs/EXPLAINER.md`.
3. Do not open new milestone code (no M8) — next code-shaped work only if soak-period usage or the explainer-writing process itself surfaces a real gap.
