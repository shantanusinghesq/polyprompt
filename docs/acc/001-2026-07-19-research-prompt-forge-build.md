# Context Compression — 2026-07-19
**Focus:** research-prompt-forge build (M0–M3 done, M4 next)
**Token estimate before:** ~150k
**Token estimate after:** ~1.3k

## Decisions
- D: Build Claude Code plugin `research-prompt-forge` — one general research prompt → 4 engine-tuned rewrites (ChatGPT/Gemini/Claude/Perplexity) + explanation memos → knowledge graph that validates rewrites. Spec: `~/Projects/Bloom_playground/docs/prd/research-prompt-forge.md`.
- D: Fresh standalone repo `~/Projects/research-prompt-forge` (scratchpad D-09) — corpus is first-class, independently pushable.
- D: Python 3.11; deterministic core + golden-fixture tests (D-07); model work lives at the plugin/command layer, not the CLI.
- D: 8-milestone sequence M0–M7; critical path M0→M1→M2→M4→M6. Source: `Bloom_playground/docs/scratchpad-build-sequence-research-prompt-forge.md`.
- D: Confirmed technical decisions (PRD "Technical design decisions v1"): (1) mode auto-detect per run; (2) memo frontmatter = KG-ready tactics+tags; (3) improvement = knowledge graph validating rewrites (NOT fine-tuning/few-shot/profile-only); (4) repo private-by-default, explicit push; (5) 3-question intake (time period, depth, ambiguity); (6) monthly checkup vs vendor docs; (7) gh CLI+UI auth; (8) distinct reviewer, depth-of-reasoning ratings.
- D: Graph = git-native flat JSON edge-list; validation ADVISORY/non-blocking; k_min=5 support gate; Wilson-LB ≥0.7 → promote to required; seed edges `provenance:seed` (never counted as labels); archive-not-delete. (PRD Q1/Q4 + `poc-to-v1-graduation-criteria.md`.)
- D: Taxonomy = curated seed (18 tactics + 6 closed tag dims), reviewer-gated growth.
- D: One commit + version bump per milestone (user did not object to auto-commit; flagged twice).

## Current State
- Repo `~/Projects/research-prompt-forge`, branch `main`, version 0.3.0, 4 commits: M0 `6892df2`, M1 `8f5525d`, M2 `7577427`, M3 `a0e8ba9`. **48 tests passing.**
- M0–M3 complete; **M4 next** (harness task #5).
- Modules: `forge/{__init__,__main__,intake,ir,profile,rewrite,mode,taxonomy,memo,store}.py`; `forge/profiles/{chatgpt,gemini,claude,perplexity}.json`; `forge/taxonomy.v1.json`; `commands/forge-prompts.md`; `.claude-plugin/plugin.json`; `tests/test_m1_*,test_m2_*,test_m3_*`.
- **Memo frontmatter contract (M4 input):** JSON-valued lines between `---` fences — keys: schema_version, taxonomy_version, source_prompt_hash, engine, mode, mode_source, mode_reason, profile_version, tactics:[taxonomy ids], tags:{method,analysis_type,retrieval_type,subject_matter}, generated_at. Parse/render: `memo.parse_frontmatter` / `render_frontmatter`.
- Renderers (`rewrite.py`) emit taxonomy tactic IDs; `rewrite()` appends conditional `recency-constraint` (if recency) + `disambiguation` (if constraints).
- `mode.detect_mode(ir, model_fallback=None)` → `ModeDecision{mode,reason,source}`; margin≥2 deep, ≤−2 chat, else borderline→fallback or default deep-research. Threaded into RewriteResult + memo.
- `store.save_memo` dedupes on (source_prompt_hash, engine); default dir `research-memos/` (gitignored).
- CLI: `forge rewrite --engine all|<e> --time-period --depth --clarify --mode auto|deep-research|chat --memos DIR`; `forge intake`.
- gh 2.88.1 installed + authed as `haremantra` (M5 unblocked). `Bloom_playground` is NOT a git repo.
- Planning docs (in Bloom_playground/docs, untracked): prd/research-prompt-forge.md, scratchpad-build-sequence-research-prompt-forge.md, poc-to-v1-graduation-criteria.md.

## Open Questions
- Q: Tactic-taxonomy growth process (reviewer-gated promotion) — not built until M6.
- Q: Mode-detector accuracy eval needs M6 reviewer mode-correctness labels — not built.
- Q: Per-mode rendering deferred — renderers are mode-agnostic (chat mode still emits verbose prompt).
- Q: v1.0 graduation (G2/G3/G4/G5/G9) needs a soak period with real reviewer ratings — not reachable by code alone (`poc-to-v1-graduation-criteria.md`).

## Rejected Approaches
- X: Build inside Bloom_playground dir — rejected (D-09), corpus needs its own repo.
- X: Improvement via fine-tuning / few-shot / profile-only edits — rejected for KG validation.
- X: Graph DB / vector index for KG — rejected for v1; git-native edge-list.
- X: Emergent/open tactic labels — rejected (label drift); curated seed.
- X: All-4-engines M0 / horizontal layers / graph-first — rejected; walking-skeleton vertical slices.
- X: Always-commit / public corpus — rejected; local-default private push.
- X: Synthetic/LLM-bootstrapped graph edges — rejected (contaminates weighting); a-priori taxonomy seed instead.
- X: Pure-heuristic or pure-model mode detection — rejected; hybrid.

## Next Actions
1. **Start M4** (task #5): `forge/graph.py` (edge-list ingest + a-priori seed) + `forge/validate.py` (expected tactics, advisory flag).
2. Ingest `research-memos/*.md` frontmatter → tactic↔tag edges with (pos, neg, support); `provenance` field.
3. Cold-start: seed edges from taxonomy a-priori tactic↔tag mappings (`provenance:seed`), k_min=5 provisional gate — seeds never counted as labels.
4. Validator: for a run's IR tags, expected tactics = weight ≥ θ_high (0.7, Wilson-LB); flag missing/contra ADVISORY (non-blocking); wire into CLI `rewrite` output.
5. `tests/test_m4_*`: seeded graph flags a missing required tactic; below-gate/seed edges don't flag; validation never blocks. Bump 0.4.0, commit, mark task #5 done (unblocks M5).
6. Then M5 (gh push), M6 (review→edge weighting via Wilson-LB), M7 (monthly checkup).
