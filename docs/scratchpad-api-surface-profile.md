# Scratchpad — API-surface profile (the missing taxonomy dimension)
**Status:** Draft (plan only — no code written)
**Date opened:** 2026-08-22
**Proposed milestone:** M8 — API surface

## The gap

polyprompt's taxonomy models two dimensions of "where is this prompt going":

- `engine` — `chatgpt | gemini | claude | perplexity` (`polyprompt/taxonomy.v1.json`, `tag_dimensions.engine`)
- `mode` — `deep-research | chat` (same file)

Both describe a **vendor's consumer product**: a chat box you paste into. Every
renderer in `polyprompt/rewrite.py:46-121` emits a prose string for a human to
paste. That is correct for what the four profiles currently claim to target,
and the existing rewrites are not defective for lacking schemas.

What is missing is the ability to say *which surface of the vendor* is the
destination. When the destination is the **developer API**, "structured output"
stops being a sentence and becomes a request field: a JSON Schema, a tool
schema, a forced tool choice, a system/user role split, a server-side search
tool declaration. polyprompt has no way to express that, because it has no
dimension for it — so the `structured-output` tactic silently means the
consumer thing everywhere.

This is a modeling gap, not a bug: nothing in the codebase is wrong, but the
taxonomy cannot represent a request the tool is otherwise well shaped to serve.

### The tactic-pair evidence

The clearest symptom is that four existing tactic IDs each name a *goal* that
has two completely different *mechanisms* depending on surface:

| Goal | Consumer mechanism (tactic today) | API mechanism (no tactic exists) |
|---|---|---|
| Machine-usable output | `structured-output` — "ask for a sectioned deliverable" | JSON Schema bound to the response field |
| Traceable claims | `citation-demand` — "require inline citations" | machine-readable citation / grounding metadata |
| Right output size | `length-target` — "signal desired length" | explicit max-output / effort / budget parameter |
| Constrained retrieval | `source-filter-operators` — `site:` / `after:` in the query text | server-side search tool with domain + recency params |

One ID, two mechanisms. The graph then accumulates evidence for
`structured-output` that mixes both meanings, which is exactly the label drift
the taxonomy decision (D-08, `docs/acc/001-...`) exists to prevent.

---

## D-01 — How is the API destination modelled?

**Options considered:**
- A: A new **orthogonal tag dimension** `surface: consumer | api`.
- B: New **engine values** — `chatgpt-api`, `gemini-api`, `claude-api`, `perplexity-api` (8 engines).
- C: New **mode values** — `mode: deep-research | chat | api`.

**Accepted:** Option A — `surface` is a third closed dimension alongside
`engine` and `mode`, and profile identity becomes `(engine, surface)`.

**Rejected:** Option B
**Reasoning against B:** `engine` is a *vendor identity*, and the whole
maintenance ritual is built on that reading — `checkup.py` refreshes one
profile per vendor against that vendor's docs, and the graph's
`("engine", "chatgpt")` edges accumulate cross-run evidence about ChatGPT.
Splitting the enum to 8 values splits every one of those edges in half and
throws away the evidence-sharing between two surfaces of the same vendor
(role framing works on both; that should stay one edge). It also doubles
`ENGINES` (`polyprompt/profile.py:18`), which is enumerated in the CLI
`--engine` choices, `load_all_profiles()`, and `checkup_status()`.

**Rejected:** Option C
**Reasoning against C:** `mode` and `surface` are genuinely independent — an
API call can be a single-shot completion *or* an agentic retrieval loop,
exactly as the consumer product can be chat or deep-research. Collapsing them
makes "deep research on the API" unrepresentable, which is the most valuable
cell in the matrix.

**Assumption accepted:** Two values (`consumer`, `api`) are enough. A third
(e.g. `batch`) can be added later; the dimension is a closed enum, extending it
is a taxonomy bump, not a redesign.
**Assumption rejected:** "Surface can be inferred from the prompt text" —
rejected; nothing in a research question says whether the asker has an API key.
It is a caller declaration, like `--engine`, not a detection like `--mode`.

---

## D-02 — Where do API profiles live on disk?

**Options considered:**
- A: `profiles/api/<engine>.json` subdirectory, consumer files unchanged.
- B: `profiles/<engine>.<surface>.json` — flat, symmetric, renames the 4 existing files.
- C: One file per engine holding both surfaces under a `surfaces` key.

**Accepted:** Option B, with a compatibility fallback: `load_profile(engine,
surface)` reads `<engine>.<surface>.json`, and if that is missing *and*
`surface == "consumer"`, falls back to `<engine>.json`.

**Rejected:** Option A
**Reasoning against A:** Two flat globs would silently miss the subdirectory —
`checkup.py:64` (`profile_dir.glob("*.json")`) would stop reporting staleness
for API profiles, and `skills/polyprompt/build.sh:19`
(`cp .../profiles/*.json`) would ship a skill zip with the API profiles
missing. The build's smoke test (`build.sh:25`) runs the *consumer* default, so
it would still pass — a silent-drift trap in exactly the place the build script
was written to prevent drift.

**Rejected:** Option C
**Reasoning against C:** `checkup.propose_update()` / `apply_update()` version-
stamp a whole file (`version`, `last_checked`); two surfaces sharing one file
either share one version stamp (wrong — they go stale independently, against
different vendor docs) or need a nested versioning scheme that every reader has
to learn.

**Assumption accepted:** The `surface` key *inside* the JSON is authoritative;
filenames are a lookup convenience. `checkup_status()` should report
`engine/surface` read from file contents, not parsed from the name.

---

## D-03 — What does an API-surface rewrite actually emit?

A consumer rewrite is a string. An API rewrite is a request body.

**Options considered:**
- A: Keep `RewriteResult.prompt: str`; render the request body as pretty-printed JSON into it.
- B: Add `RewriteResult.payload: dict | None` alongside `prompt`, where `prompt` holds the rendered JSON text.
- C: A separate `ApiRewriteResult` type with its own memo path.

**Accepted:** Option B.

```python
@dataclass
class RewriteResult:
    engine: str
    mode: str
    prompt: str                    # always the human-visible rendering
    tactics: list[str]
    profile_version: str
    mode_source: str = "default"
    mode_reason: str = "profile default (no detection)"
    surface: str = "consumer"      # NEW
    payload: dict | None = None    # NEW — api surface only; None on consumer
```

`prompt` staying the single rendering means `memo.py`, `store.py`, and the CLI
formatter need no structural change — only a fenced-code language hint
(```` ```json ````) in `_render_body` (`polyprompt/memo.py:126-149`). `payload`
exists so tests and future tooling can assert on structure rather than on
formatted text.

**Rejected:** Option A
**Reasoning against A:** Losing the dict means every test asserts against
whitespace-formatted JSON, and any downstream consumer has to re-parse a string
polyprompt already had structured.

**Rejected:** Option C
**Reasoning against C:** A parallel result type forks `build_memo`,
`save_memo`, `ingest_memo`, and `validate` — four modules gain a branch to
serve one field. The whole knowledge-graph loop keys off `tactics` + `tags`,
which are identical in shape on both surfaces.

**Assumption accepted:** Determinism is preserved (invariant 1,
`docs/ARCHITECTURE.md`). Payload dicts must be built in fixed key insertion
order and serialized with `json.dumps(payload, indent=2)` — no sets, no
clock-derived values, no `sort_keys` dependence.

---

## D-04 — Taxonomy versioning and the new tactic IDs

**Accepted:** `taxonomy.v2.json` — a strict superset of v1. Existing IDs keep
their exact meaning and description; nine API-mechanism tactics are added; the
`surface` tag dimension is added; each tactic gains an optional `surfaces`
list defaulting to `["consumer", "api"]`.

Never redefine an existing ID in place. Memos on disk carry
`taxonomy_version: "v1"` and graph edges reference IDs by string — silently
changing what `structured-output` means would retroactively rewrite the meaning
of every accumulated edge.

New tactics (all `"surfaces": ["api"]`):

| ID | Description |
|---|---|
| `response-schema` | Bind the response to a JSON Schema via the engine's structured-output field, so the caller parses instead of scrapes. |
| `schema-strictness` | Make the schema total — `additionalProperties: false`, all fields required — so validation is exact rather than best-effort. |
| `tool-schema` | Declare typed tool/function schemas the model may call. |
| `forced-tool-choice` | Pin tool choice so the model must emit the structured call instead of prose. |
| `system-role-separation` | Put invariant instructions in the system/developer role and the variable task in the user role. |
| `retrieval-tool-enable` | Enable the vendor's server-side search/grounding tool instead of asking for a search in prose. |
| `citation-metadata` | Request machine-readable citation/grounding metadata rather than prose footnotes. |
| `determinism-controls` | Pin the decode-time knobs the engine still exposes (seed / sampling / effort) so a run is reproducible. |
| `token-budgeting` | Bound output with the engine's explicit max-output or budget parameter rather than a prose length target. |

18 tactics → 27.

**Rejected:** A separate `taxonomy.api.v1.json`
**Reasoning:** `graph.seed_graph()` and `validate.validate()` both filter
against one `Taxonomy.tactic_ids()`; two vocabularies means two loaders, two
version stamps in memo frontmatter, and no way to express a tactic that is
valid on both surfaces (most of them are).

**Rejected:** Partitioning *every* tactic into consumer-only or api-only
**Reasoning:** Most consumer tactics work fine on the API — `role-framing` is
just system-prompt text there. Marking them consumer-only would be a false
claim. Only the nine mechanism-bound additions get a narrowed `surfaces` list;
everything else stays applicable to both, which is the honest default.

---

## D-05 — The dedupe-key collision (the load-bearing change)

**This is the part that breaks silently if missed.** The corpus is keyed on
`(source_prompt_hash, engine)` in four places:

- `polyprompt/store.py:240-279` — `existing_keys()` / `save_memo()`
- `polyprompt/graph.py:101,127` — `Graph.ingested`, `ingest_memo()`
- `polyprompt/sufficiency.py:63,89` — `_scan_memos()` dedupe, pending scan
- `polyprompt/review.py:83-90` — `(hash, engine, reviewer)`

The same prompt rewritten for `claude/consumer` and `claude/api` produces the
same key. Today's code would write the first memo and **silently skip the
second** with status `"skipped"` (`store.py:272`) — and the filename collides
too (`memo.py:170`: `{date}-{slug}-{engine}.md`).

**Options considered:**
- A: Widen the key to `(source_prompt_hash, engine, surface)`; widen the review key to 4 elements.
- B: Fold surface into the engine string — `"claude@api"`.
- C: Separate memo directories per surface.

**Accepted:** Option A.

- Memo `SCHEMA_VERSION` `"1"` → `"2"`; frontmatter gains a top-level `surface`
  key and `tags` gains `surface`.
- Graph `schema_version` `"1"` → `"2"`; `ingested` entries become 3-element,
  `reviewed` 4-element.
- Filename becomes `{date}-{slug}-{engine}-{surface}.md`.
- Read-side normalization (the same implicit-default style as the existing
  pre-M6 compat path in `load_graph`): every reader uses
  `frontmatter.get("surface", "consumer")`, and `load_graph()` widens a
  2-element `ingested` entry to `(hash, engine, "consumer")`. Old memos and
  old graph files keep working, and re-ingest is a no-op rather than a
  double-count.

**Rejected:** Option B
**Reasoning against B:** It puts a value into the `engine` tag dimension that
is not in the closed enum, so `taxonomy.valid_tag("engine", "claude@api")` is
false and `seed_graph()` would filter the edge out — while `ingest_memo()`,
which does not validate, would happily create it. Two code paths disagreeing
about whether a tag is legal is worse than a schema bump.

**Rejected:** Option C
**Reasoning against C:** `push._corpus_files()`, `sufficiency.assess()`, and
`ingest_directory()` all take one directory. Splitting the corpus means either
running every command twice or teaching three modules about a directory
convention — and the graph is deliberately one flat file (ARCHITECTURE.md,
"Complexity / scale notes").

**Assumption accepted:** `ARCHITECTURE.md` currently lists "no memo/graph
schema migration tooling beyond implicit defaults" as a known gap. This plan
does **not** close that gap — it adds a second implicit-default path in the
same style. That is a deliberate scope choice; if a real migration tool is
wanted, it is separate work and should be its own milestone.

---

## D-06 — What does `mode` mean on the API surface?

**Accepted:** Reuse `deep-research | chat` with a surface-specific rendering
contract, documented in each API profile's `notes`:

- `deep-research` + `api` → server-side retrieval tool declared, multi-step
  tool loop permitted, higher output budget.
- `chat` + `api` → single-shot, no server tool, tight output budget.

`mode.detect_mode()` (`polyprompt/mode.py:45`) reads only the `PromptIR` and
needs **no change** — the request's shape does not depend on which surface the
answer is fetched from.

**Rejected:** Adding `agentic` / `single-shot` as new `mode` values
**Reasoning:** They are synonyms for the two that exist, scoped to a surface
the `surface` dimension already names. Adding them doubles the mode enum,
splits `("mode", "deep-research")` graph evidence, and forces `detect_mode()`
to become surface-aware for no gain.

---

## D-07 — Default surface and CLI ergonomics

**Accepted:** `--surface {consumer,api,both}`, default `consumer`.

```
polyprompt rewrite --engine all "..."                    # unchanged: 4 consumer rewrites
polyprompt rewrite --engine claude --surface api "..."   # 1 API request body
polyprompt rewrite --engine all --surface both "..."     # 8 rewrites
polyprompt checkup --surface api                         # staleness for API profiles
```

Defaulting to `consumer` keeps every existing invocation, golden fixture, and
slash command byte-identical. `load_all_profiles()` keeps its current signature
and consumer-only return; a `surface` parameter is added with a
`"consumer"` default.

---

## Invariants to preserve

Carried from `docs/ARCHITECTURE.md` — the API surface must not weaken these:

1. **No network I/O.** polyprompt **emits** request payloads; it never sends
   them. `polyprompt/push.py` stays the only module that leaves the machine.
   This is the single most important guardrail in this milestone: "we model the
   API surface" must never drift into "we call the API." Worth adding as an
   explicit numbered invariant when implementing.
2. **`rewrite()` stays pure and deterministic.** No clock, no randomness, no
   network. Fixed key order in payload dicts.
3. **Validation stays advisory.** A missing `response-schema` tactic is a
   printed flag, never an exit code.
4. **Seed edges cannot self-promote.** New `("surface", ...)` seed rows carry
   `pos=neg=0` like every other seed.

---

## Vendor field names — what is verified and what is not

The API profiles are only as good as the vendor facts in them, and the repo
already has the right ritual for this: `doc_sources` + `last_checked` +
`polyprompt checkup`.

**Anthropic — verified** against the bundled `claude-api` reference:

- Structured output: `output_config: {format: {...}}` on `messages.create()`.
  The older top-level `output_format` parameter is deprecated.
- Tools: `tools: [{name, description, input_schema}]`; strict validation is
  `strict: true` as a **top-level field on the tool definition** (not on
  `tool_choice`), and requires `additionalProperties: false` plus `required`.
- Forcing a call: `tool_choice`.
- System prompt: top-level `system` parameter — a real role split, not a
  prose preamble.
- Server-side search: `{"type": "web_search_20260209", "name": "web_search"}`
  with `max_uses`, `allowed_domains` / `blocked_domains`, `user_location`
  (older models: `web_search_20250305`).

Two constraints that directly shape the renderer:

- **`temperature` / `top_p` / `top_k` are removed on current models and return
  400.** So `determinism-controls` on `claude/api` must render
  `output_config: {effort: ...}`, not sampling knobs. This kills any notion of
  a single portable "set temperature" tactic — the tactic names the *goal*, the
  profile names the mechanism.
- **Document `citations: {enabled: true}` is incompatible with
  `output_config.format` and returns 400.** So `citation-metadata` and
  `response-schema` genuinely conflict on this profile.

**OpenAI, Google, Perplexity — NOT verified here.** `platform.openai.com` and
`ai.google.dev` are blocked by this environment's egress proxy, so their exact
field paths could not be checked. Do **not** fill those three profiles from
memory. Stage 2 below runs the existing checkup ritual against each vendor's
primary docs and records `doc_sources` + `last_checked` — which is precisely
what that ritual is for.

### Tactic conflicts are a profile fact, not a renderer accident

The Claude citations/schema conflict above generalizes. Add to
`PlatformProfile`:

```json
"tactic_conflicts": [["citation-metadata", "response-schema"]]
```

with a deterministic resolution rule: prefer `response-schema`, and express
citations as a **field inside the schema** rather than as a document-citation
flag. The dropped tactic is then omitted from `RewriteResult.tactics`, so the
graph never records a tactic that was not actually applied.

---

## Proposed `PlatformProfile` additions

`_REQUIRED` (`polyprompt/profile.py:19-29`) gains `surface`. API profiles add:

| Field | Purpose | Example (claude/api) |
|---|---|---|
| `surface` | `consumer` \| `api` | `"api"` |
| `request_shape` | which renderer to dispatch | `"messages-tool-schema"` |
| `structured_output_field` | where a schema binds | `"output_config.format"` |
| `tool_field` | where tool schemas go | `"tools[].input_schema"` |
| `tool_choice_field` | how a call is forced | `"tool_choice"` |
| `strictness_field` | how a schema is made total | `"tools[].strict"` |
| `role_model` | system/user separation | `"top-level system + messages[]"` |
| `retrieval_tool` | server-side search declaration | `"web_search_20260209"` |
| `budget_field` | output bound | `"max_tokens"` / `"output_config.effort"` |
| `unsupported_params` | knobs that 400 on this vendor | `["temperature", "top_p", "top_k"]` |
| `tactic_conflicts` | pairs that cannot co-apply | `[["citation-metadata", "response-schema"]]` |

Existing consumer profiles gain only `"surface": "consumer"`; every other field
keeps its current value and meaning.

---

## Implementation plan (M8), staged

**Stage 1 — schema and identity. No behavioral change.**
- `taxonomy.v2.json`; `taxonomy.py:19` points at it; keep v1 on disk for provenance.
- `surface` tag dimension + 9 tactics + `surfaces` field.
- `profile.py`: `SURFACES`, `surface` in `_REQUIRED` and `PlatformProfile`,
  `load_profile(engine, surface="consumer")` with the consumer filename fallback.
- `memo.py`: `SCHEMA_VERSION = "2"`, `surface` in frontmatter and `_TAG_DIMENSIONS`
  (`:25,:27`), filename `:170`.
- `store.py`, `graph.py` (`:31,:101,:127`), `sufficiency.py` (`:33,:63,:89,:105`),
  `review.py` (`:83-98`): 3-tuple key, with read-side widening of short tuples.
- `graph.SEED_ASSOCIATIONS` (`:35`) gains:
  `("surface", "consumer", ["structured-output", "citation-demand"])` and
  `("surface", "api", ["response-schema", "system-role-separation", "retrieval-tool-enable"])`.

**Stage 2 — the four API profiles.**
- `profiles/{engine}.api.json`, each with `doc_sources` + `last_checked`.
- Claude's values are known (above). The other three are filled by running
  `polyprompt checkup` against vendor primary docs — do not guess.
- Rename the 4 consumer files to `{engine}.consumer.json` (fallback keeps
  `FORGE_PROFILE_DIR` sandboxes and any external profile dir working).

**Stage 3 — renderers and payload.**
- `RewriteResult.surface` + `.payload`.
- Four renderers registered in `_RENDERERS` (`rewrite.py:124`) under new
  `structure` names — the existing dispatch mechanism is unchanged, since 8
  profiles carry 8 distinct structure names. Guard: two profiles may share a
  structure name only if they genuinely share a renderer.
- Conflict resolution per `tactic_conflicts`; dropped tactics must not appear
  in `result.tactics`.
- Golden fixtures per (engine, surface).

**Stage 4 — CLI, skill, docs.**
- `--surface` on `rewrite` and `checkup` (`__main__.py:274-306`, `:362-374`).
- `checkup.py`: `_PROTECTED` (`:27`) gains `surface`; `checkup_status()`
  (`:61-76`) reports `engine/surface` from file contents; `propose_update()` /
  `apply_update()` take a surface.
- `build.sh:19` — verify the flat glob still catches every profile; extend the
  smoke test (`:25`) to run one API-surface rewrite so a missing profile fails
  the build loudly.
- `SKILL.md` — the description says "paste targets"; reword, since an API-surface
  rewrite is not pasted into a chat box.
- `README.md` layout + frontmatter contract; `ARCHITECTURE.md` data contracts,
  invariants (add the no-egress one), and known gaps.

---

## Test plan

**Existing assertions that will fail and must be updated deliberately** (not
patched around):

| Test | Line | Today | After |
|---|---|---|---|
| `test_m2_taxonomy.py` | `:12` | `tax.version == "v1"` | `"v2"` |
| `test_m4_graph.py` | `:129`, `:151` | `len(graph.edges) == 12` | `17` (5 new seed edges) |
| `test_m6_review.py` | `:74` | `len(graph.edges) == 12` | `17` |
| `test_m1_profiles.py` | `:22` | `len(structures) == 4` | scope per surface: 4 consumer + 4 api |

Baseline before any change: **139 passing** (`python -m pytest -q`, verified
2026-08-22).

**New tests:**
- Round-trip: a memo written at schema 2 parses, ingests, and dedupes on the
  3-tuple.
- Back-compat: a schema-1 memo and a schema-1 graph.json load, default to
  `surface="consumer"`, and re-ingest as a **no-op** (this is the regression
  that would silently double-count the whole corpus).
- Collision: same prompt + same engine + both surfaces writes **two** memos,
  neither `"skipped"`, distinct filenames.
- Determinism: `rewrite()` twice on the same IR yields byte-identical
  `json.dumps(payload)`.
- Purity guard: the API renderers make no network call — the CI job already
  shadows `git`/`gh`; consider the same treatment for any HTTP client import.
- Conflict: `claude/api` never emits both `citation-metadata` and
  `response-schema`.
- Validity: every tactic ID emitted by every renderer exists in the taxonomy
  (parametrize over all 8 profiles).

---

## Open questions

- **Q-01:** Should `validate.py` gain a structural self-check that the emitted
  payload matches a hand-authored vendor request schema? Leaning **no** for
  M8 — it is a second vendor-shaped artifact to keep fresh, and the checkup
  ritual already carries that cost once.
- **Q-02:** Does the diversity floor (`DIVERSITY_MIN = 3`, distinct prompt
  hashes, `sufficiency.py:105`) need a surface-aware variant? One prompt across
  two surfaces is 2 memos but 1 hash. The current code counts distinct hashes,
  so it is already conservative — confirm it does not accidentally become 2.
- **Q-03:** Does `chat` + `api` mean "no server-side retrieval tool" for all
  four vendors, or is that only true for some? Resolve during Stage 2.
- **Q-04:** Should the claude.ai Skill ship the API surface at all? It needs no
  persistent state, so technically yes — but the skill's stated value is tuning
  paste targets, and its description drives triggering. Decide with the
  SKILL.md rewrite in Stage 4.
- **Q-05:** `surface` is a caller declaration, not a detection. Is there ever a
  case for inferring it (e.g. the prompt asks for "a JSON object I can parse")?
  Leaning no — see D-01's rejected assumption.

## Rejected approaches (carry forward)

- **X:** New engine values (`chatgpt-api`, …) — splits vendor identity and
  halves every `("engine", ...)` graph edge. (D-01/B)
- **X:** `surface` as a third `mode` value — makes "deep research on the API"
  unrepresentable. (D-01/C)
- **X:** Folding surface into the engine string (`"claude@api"`) — injects a
  value the closed enum rejects, which `seed_graph()` filters out and
  `ingest_memo()` does not. (D-05/B)
- **X:** `profiles/api/` subdirectory — silently invisible to
  `checkup.py:64` and `build.sh:19`, and the build smoke test would not catch
  it. (D-02/A)
- **X:** A separate API taxonomy file — two vocabularies, two version stamps,
  no way to express a both-surface tactic. (D-04)
- **X:** Redefining `structured-output`'s description in place — retroactively
  rewrites the meaning of every accumulated edge. (D-04)
- **X:** Separate memo directories per surface — forks the corpus that
  `push`, `sufficiency`, and `ingest_directory` each treat as one. (D-05/C)
- **X:** Making polyprompt actually call the APIs — breaks the "push.py is the
  only egress" invariant and turns a deterministic, testable rewriter into a
  network client. Out of scope, permanently.
