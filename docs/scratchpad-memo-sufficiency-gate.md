# Scratchpad — Memo Sufficiency Gate (ingest trigger vs M7)
**Status:** Draft (pre-CoVE)
**Date opened:** 2026-07-19

Source: sholay session `20260719-091645-memo-sufficiency-gate-loop` (summary.md). Question: should a loop/conditional "sufficiency gate" that scans memos and decides whether enough new evidence exists to update the JSON graph be built **in lieu of or in addition to** M7?

### D-01 — Does the sufficiency gate replace M7 or sit alongside it?

**Options considered:**
- A: Gate **in addition to** M7 — gate governs label ingest from memos; M7 stays the monthly vendor-doc structural checkup.
- B: Gate **in lieu of** M7 — drop the calendar checkup; the gate is the only update trigger.
- C: M7 only, no gate — keep ingest unconditional as today.

**Accepted:** Option A — the two cover disjoint update types: the gate decides *when accumulated labels are worth ingesting*; M7 proposes *profile/seed structure diffs from vendor docs*. Neither can do the other's job.

**Rejected:** Option B
**Reasoning against B:** No amount of memo-scanning detects that a vendor changed its deep-research mode or prompt guidance — that information lives in external docs, not in the corpus. Dropping M7 leaves profiles to rot (FR-8 would go unmet).

**Rejected:** Option C
**Reasoning against C:** Unconditional ingest churns the graph file on every run and gives no answer to "is a decision available yet?" — the exact question the reviewer workflow needs before spending human rating effort.

**Assumption accepted:** Gate and M7 outputs never conflict (labels vs structure edit different parts of the graph/profiles).
**Assumption rejected:** "A calendar trigger is a proxy for evidence sufficiency" — rejected; time passing correlates with nothing when memo volume is bursty.

### D-02 — What is the sufficiency criterion?

| Criterion | A. Pending-label count | B. Distance-to-promotion simulation | C. Provenance-diversity floor |
|-----------|------------------------|--------------------------------------|-------------------------------|
| Implementation cost | Trivial (reuse dedupe set) | Moderate (graph copy + diff) | Trivial (distinct-hash count) |
| Fires exactly when a decision is available | No — blind to threshold proximity | **Yes** | No |
| Guards against low-quality evidence | No | No | **Yes** |
| Determinism / testability | High | High (pure function on copy) | High |
| False-fire risk | High (20 labels on dormant edges) | Low | n/a (it's a veto, not a trigger) |

**Options considered:**
- A: Count pending non-deduped labels; fire when `pending >= MIN_PENDING`.
- B: Simulate applying pending labels to a graph copy; fire only if the promoted set changes.
- C: Diversity floor as sole criterion (distinct hashes/reviewers per edge).

**Accepted:** Option B as trigger, with C as a conjunct veto (an edge only counts as promotable if distinct-hash support ≥ 3) and A retained as a cheap pre-check/hysteresis (`pending >= MIN_PENDING` short-circuits the simulation).

**Rejected:** Option A alone
**Reasoning against A:** A label on an edge at pos=4 is worth vastly more than the 20th label on a seed-only edge; a flat count fires on volume that changes nothing and stays silent when one label away from promotion.

**Rejected:** Option C alone
**Reasoning against C:** Diversity says whether evidence is trustworthy, not whether there is enough of it to move an edge — it can't trigger anything by itself.

**Assumption accepted:** Simulation is cheap: the graph is a small flat dict; copying and re-diffing promoted sets is O(edges).
**Assumption rejected:** "Wilson-LB already accounts for evidence diversity" — rejected; Wilson handles volume only. Five positives from one reviewer on one prompt hash pass the same gate as five independent ones (dedupe only guards (hash, engine) and (hash, engine, reviewer), not cross-prompt diversity).

### D-03 — What does the gate output: binary or triage?

**Options considered:**
- A: Binary ingest/skip.
- B: Four-bucket triage — PROMOTE-READY / NEEDS-MORE / CONTESTED / DORMANT — with the CLI's if/else reading `would_promote`.
- C: Triage where CONTESTED **blocks** auto-ingest.

**Accepted:** Option B — the triage is the report, the binary is derived from it (`report.would_promote`); CONTESTED edges annotate for human attention but never block.

**Rejected:** Option A
**Reasoning against A:** Throws away exactly the signal the reviewer needs — *which* edges are one label away vs oscillating near 0.7 — forcing a second tool to re-derive it.

**Rejected:** Option C
**Reasoning against C:** Blocking on contested edges makes ingest non-monotonic and violates the project's advisory-never-blocking validation stance (PRD Q4, M4 design); negatives are data, not a veto.

**Assumption accepted:** "Advisory, never blocking" from M4 validation extends naturally to the sufficiency gate.
**Assumption rejected:** "Oscillation near θ means the data is bad and ingest should pause" — rejected; oscillation is the graph doing its job (contra path exists for sustained negatives, M6).

### D-04 — Where does the gate run?

**Options considered:**
- A: Its own subcommand `forge sufficiency` (pure report + exit code), advisory print inside `forge push`.
- B: Automatically on every memo save (inside `rewrite --memos`).
- C: Only inside `forge push`.

**Accepted:** Option A — a pure `assess(memos, graph) -> Report` in `forge/sufficiency.py`, a standalone subcommand for scripting (`if forge sufficiency; then ...`), and a one-line advisory in the push flow where the user is already looking at corpus state.

**Rejected:** Option B
**Reasoning against B:** Rewrite-time is authoring-time; per-save assessment adds noise to every forge run and couples the inner loop to graph state it doesn't need.

**Rejected:** Option C
**Reasoning against C:** Push is about persistence, not graph decisions; hiding the gate there makes it uninvocable for the reviewer workflow (who reviews locally without pushing).

**Assumption accepted:** Exit code semantics (0 = would-promote / sufficient, 1 = insufficient) are enough for the user's literal while/if-else composition.
**Assumption rejected:** "The gate must mutate the graph to be useful" — rejected; `assess` is read-only, ingest remains the only mutator.

## Assumptions Register

### Accepted Assumptions
| ID | Assumption | Rationale | Decision |
|---|---|---|---|
| AA-01 | Gate (labels) and M7 (structure) never conflict | They edit disjoint artifacts | D-01 |
| AA-02 | Promotion simulation is O(edges) cheap | Flat dict edge-list, small corpus | D-02 |
| AA-03 | Advisory-never-blocking extends to the gate | Consistent with M4 validator stance | D-03 |
| AA-04 | Exit 0/1 suffices for shell composition | Matches user's while/if-else framing | D-04 |

### Rejected Assumptions
| ID | Assumption | Why Rejected | Decision |
|---|---|---|---|
| RA-01 | Calendar time proxies evidence sufficiency | Memo volume is bursty; time correlates with nothing | D-01 |
| RA-02 | Wilson-LB accounts for evidence diversity | It handles volume only; single-source positives pass identically | D-02 |
| RA-03 | Contested edges should pause ingest | Negatives are data; contra/archive path (M6) already handles sustained negatives | D-03 |
| RA-04 | Gate must mutate the graph | Read-only assess keeps ingest the single mutator | D-04 |

## CoVE Verification Questions
| ID | Question | Decision it affects |
|---|---|---|
| CoVE-01 | Does dedupe really only guard (hash, engine) for ingest and (hash, engine, reviewer) for reviews — i.e. no cross-prompt diversity guard exists? | D-02 |
| CoVE-02 | Is promotion state derivable from a graph copy without side effects (pure properties, no caching)? | D-02 |
| CoVE-03 | Does anything in the current CLI branch on validation output (which would contradict AA-03)? | D-03 |

## CoVE Answers

### CoVE-01 — dedupe scope
**FINDING:** YES. `Graph.ingest_memo` keys `self.ingested` on `(source_prompt_hash, engine)` (forge/graph.py:136) and `apply_review` keys `graph.reviewed` on `(hash, engine, reviewer)` (forge/review.py:87-91). No structure counts distinct hashes per edge — RA-02 stands; a diversity floor requires new bookkeeping (per-edge contributing-hash set or recount from memos at assess time).
**Impact:** Confirms D-02's conjunct is *not* free: `assess` should recompute diversity from the memo files it scans (it has them in hand) rather than extend the Edge schema. No new decision needed.

### CoVE-02 — promotion is pure
**FINDING:** YES. `Edge.promoted`, `Edge.weight`, `Edge.contra` are all computed properties over `pos/neg/status` (forge/graph.py:78-92); `required_tactics` reads them without mutation. A `copy.deepcopy(graph)` + replay of pending labels + set-diff of promoted keys is side-effect-free.
**Impact:** AA-02 holds; D-02's simulation design is implementable as specified.

### CoVE-03 — nothing blocks on validation today
**FINDING:** YES (nothing blocks). `_cmd_rewrite` prints advisory flags and unconditionally `return 0` after validation (forge/__main__.py — validation section ends in `save_graph` + return 0).
**Impact:** AA-03 confirmed; gate exit-code semantics (D-04) are the *scripting* surface, distinct from the never-blocking advisory print.
