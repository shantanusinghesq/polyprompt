# What is Research Prompt Forge, actually?

*A humanized walkthrough — read the first section in a minute, then keep going as deep as you want. Every claim below points at the file that proves it, so if you're the skeptical type you can go check.*

---

## 1. The one-paragraph version

You have one research question. Different AI engines want it phrased differently — ChatGPT likes a role and a numbered list of constraints, Gemini likes to see a plan before it executes, Claude likes structured tags and explicit reasoning steps, Perplexity wants a short keyword query with search operators. **Research Prompt Forge takes your one plain-English question and hands back four versions, one tuned for each engine, plus a short note explaining *why* each version looks the way it does.** Every time it does this, it also writes down what it did in a form a computer can read later — so over time it builds a track record of which phrasing tricks actually work, and starts flagging when a rewrite skips a trick that's proven itself.

That's it. Everything below is "how," for whichever depth you want to stop at.

---

## 2. The shape of a run (30-second mental model)

```
your question
     ↓
  3 quick questions (how recent? how deep? anything ambiguous?)
     ↓
  normalize into a structured form (the "IR")
     ↓
  detect: is this a "deep research" question or a quick chat question?
     ↓
  4 engine-specific rewrites, each tagged with which tricks it used
     ↓
  4 explanation memos (markdown files) — the rationale + machine-readable tags
     ↓
  (optional, explicit) those memos accumulate into a knowledge graph
     ↓
  (optional, explicit) a human reviewer rates the memos, which reweights the graph
     ↓
  (optional, explicit) push the corpus to a private GitHub repo
```

Nothing in the last three steps happens automatically — they're all separate commands you run on purpose. The core loop (question → 4 rewrites → memos) is the only thing that happens every time.

---

## 3. Stage by stage

### 3.1 Intake — three questions, not twenty

Before rewriting anything, the tool asks three things (`polyprompt/intake.py`):

1. **Time period** — how recent do sources need to be?
2. **Depth** — quick answer, standard, or deep multi-layer reasoning? (1/2/3)
3. **Ambiguity** — anything worth pinning down before it goes further?

Why three and not more: this is a deliberate design decision (recorded in the project's original spec) — enough specificity to sharpen the rewrite without turning every question into a form to fill out. If you skip the questions, sensible defaults kick in (`depth=2`, "standard").

*For the curious:* the `/polyprompt-prompts` command asks these conversationally; the raw CLI takes them as flags (`--time-period`, `--depth`, `--clarify`).

### 3.2 IR — turning your sentence into structured data

"IR" stands for **intermediate representation** — the same idea compilers use: turn messy human input into a clean internal shape everything downstream can rely on, instead of every stage re-parsing your raw sentence. `polyprompt/ir.py`'s `normalize()` takes your prompt + the three intake answers and produces a `PromptIR`: intent, recency window, depth, a guessed list of source preferences (spotted from words like "peer-reviewed" or "official" in your question), and any constraints from your ambiguity answer.

This step is deliberately boring — no AI model involved, just deterministic text handling. That's on purpose: it's the seam every other stage depends on, so it needs to behave the same way every time you run it (that's also why it's covered by tests instead of "looks right to me").

### 3.3 Mode detection — is this "deep research" or "quick chat"?

Every engine has (at least) two gears: a slow, thorough deep-research mode and a fast chat mode. Forcing everything into deep-research wastes your time on quick questions; forcing everything into chat gives you shallow answers to hard questions. `polyprompt/mode.py`'s `detect_mode()` decides which gear fits, using a **hybrid** approach:

- **Rules first.** It scores signals from your IR — depth level, presence of a recency window, analytical keywords like "compare" or "evaluate" vs. quick-fact keywords like "what is" or "capital of," even sentence length — into a deep-vs-chat tally. If one side clearly wins (margin of 2+), that's the answer, no AI call needed.
- **Model fallback for the genuinely ambiguous.** If the rules are torn (a real "could go either way" case), the decision is handed to a plugged-in model call — but only then. This is a deliberate seam: the *rules* path stays 100% deterministic and testable; the *model* path only ever kicks in for the cases that actually need judgment.
- **Every decision carries its reasoning.** You'll see something like `rules: deep=3 chat=0 (reasoning_layers=3, recency, sources)` — not just an answer, but the tally that produced it.

### 3.4 The four rewrites — same idea, four accents

`polyprompt/rewrite.py` holds one renderer per engine, each built around a documented quirk of how that engine actually wants to be prompted:

| Engine | Renderer shape | What it leans on |
|---|---|---|
| ChatGPT | Role-framed | "You are an expert analyst," numbered constraints, structured-output ask |
| Gemini | Research-plan-first | Ask it to outline a plan, *then* survey broadly before answering |
| Claude | XML-delimited | `<task>`/`<constraints>`/`<instructions>` tags, explicit step-by-step reasoning, "flag uncertainty" |
| Perplexity | Concise query | Compress to a short keyword-style line, add search operators like `after:2023`, ask for citations |

Each renderer doesn't just produce text — it also returns the **list of tactic IDs it used** (e.g. `role-framing`, `citation-demand`, `xml-structure`). These aren't free-text descriptions; they're IDs from a fixed vocabulary (`polyprompt/taxonomy.v1.json`, 18 tactics total) precisely so nothing downstream has to guess what "used good structure" means later — it's a specific, lookupable ID every time.

### 3.5 Memos — the receipt for every rewrite

Every rewrite gets an **explanation memo**: a markdown file with a human-readable "why these adaptations" section, plus machine-readable frontmatter at the top (`polyprompt/memo.py`). The frontmatter carries the tactic IDs, the detected mode + reason, a hash of your original prompt (so re-running the same question doesn't create duplicate memos), and four descriptive tags derived from your question — is this qualitative or quantitative, comparative or exploratory, what subject area, etc.

These memos save locally to `research-memos/` by default and **never leave your machine automatically** — that's a hard privacy line the project holds throughout (more in §3.8).

### 3.6 The knowledge graph — tallying what actually works

Here's where it gets interesting. Every memo is one small piece of evidence: "for this kind of question, on this engine, in this mode, these tactics were used." `polyprompt/graph.py` accumulates that evidence into a graph — nodes are tactics and tags, edges record how many times a tactic showed up (or was rated well) alongside a given tag.

Two ideas worth understanding here:

- **A tactic only becomes "expected" once there's enough evidence, and that evidence is convincingly positive.** The math behind this is the [Wilson score interval](https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval) — think of it as "how confident are we in this ratio, given how few or many observations we have." Five positive labels out of five looks perfect, but it's thin evidence; the Wilson lower bound accounts for that and won't call it "proven" yet. Ten out of ten clears the bar. This means popularity alone (raw label count) can't force a promotion — the evidence has to be both *plentiful* (5+ observations) and *convincing* (Wilson lower bound ≥ 0.7).
- **Cold start isn't guessing — it's seeded.** Before any memo has ever been written, the graph starts with a small set of hand-picked "this tactic probably matters for this engine" associations, drawn from how each vendor documents their engine. These seed edges are marked as such and carry **zero counts** — they're structure, not evidence, so they can never accidentally "win" a promotion on their own. They exist so the validator (next section) has *something* to check against on day one, not nothing.

### 3.7 Validation — an advisor, never a gatekeeper

Once the graph has some promoted (well-evidenced) tactics, every future rewrite gets checked against it (`polyprompt/validate.py`): "for a ChatGPT rewrite in deep-research mode, history says `role-framing` should show up — did it?" If a promoted tactic is missing, you get a printed flag.

The important word is **advisory**. This never blocks a rewrite, never changes its exit code, never silently rewrites anything for you. It's a second opinion you can ignore. This is a deliberate stance, not an oversight — it shows up consistently everywhere validation-shaped logic exists in this project.

### 3.8 Review — a second, human opinion

`polyprompt/review.py` lets a **different person** than whoever wrote the prompt rate a memo: intent-fidelity and quality (1–5 each), a short explanation, and whether the detected mode was actually right. Why a distinct reviewer matters: someone rating their own rewrite is a much weaker signal than an independent second opinion — self-grading is exactly the kind of evidence the Wilson-LB math is designed to be skeptical of. High ratings turn into positive graph labels; low ratings turn into negative ones; middling ratings are recorded but don't move the graph either way.

If an edge accumulates **sustained** negative evidence (same Wilson-LB math, applied to the negative rate), it's marked contra and *archived* — not deleted. The distinction matters: archived means "we have real reason to believe this doesn't work, and the record of that stays visible," rather than quietly vanishing.

### 3.9 The sufficiency gate — "is it even worth checking the graph yet?"

Before you bother pushing new memos into the graph, it's worth asking: is there *actually* new, meaningfully-different evidence sitting in `research-memos/`, or would running the update just spin the wheels for no change? `polyprompt/sufficiency.py` answers this without touching anything (it's read-only): it simulates applying the pending memos to a *copy* of the graph and checks whether any tactic would actually flip status. It also refuses to count evidence that's suspiciously narrow — if every one of the pending labels traces back to the *same* original question asked five different ways, that's one data point wearing five hats, not five data points, so it won't count as sufficient on its own.

The output is a simple readiness verdict — enough new evidence to update the graph, or not yet.

### 3.10 Push — the one path off your machine, and it's opt-in

Everything above happens **entirely on your machine**. `polyprompt/push.py` is the *only* code path that can send memos anywhere else, and it only runs when you explicitly type the push command. It commits the memo corpus to its own **private** GitHub repository (creating it if it doesn't exist yet), and if anything about that fails — no network, no auth, whatever — your local memos are never touched or lost; you just get a clear report of what didn't work.

### 3.11 Checkup — keeping the four profiles from going stale

Each engine's quirks live in a small versioned file (`polyprompt/profiles/*.json`) — structure preference, length target, search-operator syntax, strengths. Vendors change these things over time. `polyprompt/checkup.py` is a periodic, human-driven ritual: it reports which profiles haven't been checked against the vendor's docs in a while, and gives you a way to propose a change (with a version stamp) that only gets written if you explicitly approve it.

---

## 4. Why does any of this matter? (the "so what")

If you only remember one thing: **this isn't just a prompt template engine — it's a system that gets *evidence-based* about which prompting tricks actually help, per engine, over time**, while treating "your research questions might be sensitive" as a hard constraint rather than an afterthought. The advisory-only validation, the seeded-but-zero-weight cold start, the distinct-reviewer requirement, and the explicit-opt-in push are all the same instinct showing up in different places: **never let the system quietly claim more confidence — or take more liberty with your data — than it's actually earned.**

## 5. Where to look next

- `README.md` — quickstart commands and file layout.
- `polyprompt/taxonomy.v1.json` — the full list of 18 tactics and their descriptions.
- `commands/*.md` — the actual slash-command scripts (`/polyprompt-prompts`, `/polyprompt-review`, `/polyprompt-push`, `/polyprompt-checkup`) if you want to see the exact steps Claude Code follows.
- `docs/acc/002-2026-07-19-m4-m7-complete.md` — a terse build log if you want the engineering decision trail instead of the narrative.
- `docs/scratchpad-memo-sufficiency-gate.md` — the decision record behind the sufficiency gate, including the options that were rejected and why.
