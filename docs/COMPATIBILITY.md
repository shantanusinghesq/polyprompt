# Compatibility and verification — September 6, 2026

This note documents the scoped fixes in PR #2. It supersedes older statements
that mode selection only annotates a rewrite or that any existing `origin` is
safe for private-corpus pushing. It does not introduce a new graph or memo schema.

## Preserved behavior

All six CLI subcommands and their flags remain available. The four-engine
fan-out, profile defaults, mode detector, offline deterministic core, taxonomy,
local memo saving, memo deduplication, graph ingestion, advisory validation,
archive-not-delete behavior, review sentiment rules, and profile checkup logic
are retained. No runtime dependency or automatic remote operation was added.

Memo and graph schemas remain version 1. Existing valid review sidecars remain
readable. Package and plugin version metadata remain 0.8.0: this is a bug-fix
branch, not the planned M8 API-surface milestone.

## Intentional behavior corrections

| Area | Correction | Compatibility boundary |
| --- | --- | --- |
| Rewrite fidelity | Every renderer carries clarification constraints, analytical depth, explicit IR output format, and exclusions. | Rendered text changes where it previously omitted supplied requirements. The CLI still supplies output requirements through the prompt or `--clarify`; no new flags are introduced. |
| Chat mode | Chat now requests a concise answer rather than merely changing metadata on a deep-research prompt. | Deep-research remains available, including explicit `--mode deep-research`. A mode label does not activate a provider UI or API feature. |
| Time windows | Perplexity retains the exact supplied recency string. Ranges and `before` constraints are not converted into an `after` query. | The existing profile-controlled operator for a simple `YYYY+` is retained. Operator tactics are recorded only when emitted; provider interpretation is not live-tested here. |
| XML sections | XML metacharacters in task and constraint content are escaped. | Section delimiters remain stable. This is structural escaping, not comprehensive prompt-injection prevention. |
| Reviews | The first review keeps `<memo>.review.json`; additional reviewers use `<memo>.<reviewer-sha256>.review.json`. | The existing directory loader reads both. Identical retries retain the original timestamp and return success. Conflicting repeat votes return CLI exit 2, leaving the stored vote and graph unchanged. Previously overwritten reviews cannot be reconstructed by this patch. |
| Private push | GitHub metadata must confirm the requested repository is private, and exactly one effective push URL must match it. New private repositories are verified after creation, too. | Public, internal, mismatched, multiple-destination, and unverifiable remotes are refused. Standard github.com HTTPS and SSH forms are supported; custom aliases, Enterprise hosts, and credential-bearing URLs are not certified by this check. Local data stays on disk. |
| Push retry | A clean tree with a local commit still attempts a verified push. | `pushed` may replace the old premature `noop`; both are success exit codes. `committed` describes only the current invocation. |
| Failure handling | Initialization, staging, and status failures stop the push. Subprocess timeouts and OS errors are reported. | Subprocess timeout is 120 seconds per call. Failure never authorizes a fallback to an unverified destination. |

New review payloads must have integer 1–5 scores, a Boolean mode judgment, a
nonempty explanation, and a basename rather than a path. Invalid existing
sidecars are not silently rewritten to fit the contract.

## Verification record

Baseline: `db6a6bbc57016dbeafedae41edd7863fe174c6c1`.

Tests-first commit: `7b4c2bee3c1dd732e348e5cfee2cf154c91019f8`.
CI run [34042393336](https://github.com/shantanusinghesq/polyprompt/actions/runs/34042393336)
reproduced the regressions. The inspected Python 3.10 log reported **53 failed,
142 passed**; every failure was in the new regression file. The other two
matrix jobs also failed their test steps, not package installation.

Implementation commit: `3270a4c5b1c55e95f273914199c2c647422f1086`.
CI run [34042927465](https://github.com/shantanusinghesq/polyprompt/actions/runs/34042927465)
passed on **Python 3.10, 3.11, and 3.12**, including editable installation and the
console entry point. The inspected Python 3.10 log reported **195 passed**.
The suite now contains 56 added regression cases. Existing push fixtures were
updated to model real privacy metadata and post-creation state; two earlier
expectations were intentionally corrected: trust in an unverified origin and
premature clean-tree no-op. No tests were skipped to obtain a green result.

CI keeps real git/gh commands shadowed during pytest. These checks exercise
file persistence and subprocess orchestration through injected fakes; they do
not upload a real corpus, invoke live target engines, or prove that every
operating environment is regression-free. Review the latest PR-head checks
before merging, rather than relying only on this historical verification record.

## Deferred: graph evidence semantics

`Graph.ingest_memo()` still counts generated memos as positive observations.
This is retained for compatibility, **not endorsed as independent evidence of
rewrite effectiveness**. Generation frequency is not a measured quality gain.
The sufficiency gate and Wilson scores must not be described as establishing
causal effectiveness from generated memos alone.

A separate migration should preserve historical files and snapshots, introduce
explicit evidence kinds (generated occurrence, independent review, measured
outcome), and rebuild certified quality counts only from attributable reviews
or evaluations. Existing aggregates cannot always be separated losslessly:
review sidecars may already have been overwritten. Unknown evidence should
remain unknown rather than being invented during migration. No such migration
or silent change to historical counts is included in this PR.

## Scope limits and rollout

Changes are isolated to `fix/preserve-functionality-and-evidence`; main is not
modified by preparing this PR. Merge is a separate decision. No production
corpus was read, pushed, or migrated during testing. Graph read-modify-write
transactions and multi-process corpus coordination remain outside this patch;
the new immutable review saves do not make the entire pipeline transactional.

The effective-URL check follows the documented `git remote get-url --push
--all` behavior, including URL rewrites. Metadata fields follow `gh repo view`:

- [Git remote documentation](https://git-scm.com/docs/git-remote)
- [GitHub CLI repository metadata](https://cli.github.com/manual/gh_repo_view)
