"""`python -m forge` / `forge` CLI entry point.

Subcommands:
  rewrite  — normalize a prompt (+ intake answers), rewrite for one/all engines,
             and optionally write explanation memos (--memos DIR)
  intake   — print the three intake questions (the /forge-prompts command uses this)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from forge import __version__
from forge.graph import ingest_directory, load_graph, save_graph, seed_graph
from forge.intake import IntakeAnswers, QUESTIONS
from forge.ir import normalize
from forge.memo import build_memo, derive_tags
from forge.mode import ModeDecision, detect_mode
from forge.profile import ENGINES, load_all_profiles, load_profile
from forge.push import DEFAULT_REPO, push_corpus
from forge.review import Review, apply_review, load_reviews, mode_accuracy, save_review
from forge.rewrite import RewriteResult, rewrite
from forge.store import existing_keys, save_memo
from forge.sufficiency import assess
from forge.taxonomy import Taxonomy, load_taxonomy
from forge.validate import validate


def _format_result(result: RewriteResult, taxonomy: Taxonomy) -> str:
    lines = [
        f"## {result.engine.upper()}  [mode: {result.mode} ({result.mode_source}) · "
        f"profile {result.profile_version}]",
        "",
        result.prompt,
        "",
        "Tactics applied:",
    ]
    lines += [f"  - {taxonomy.label(t)} ({t})" for t in result.tactics]
    return "\n".join(lines)


def _cmd_rewrite(args: argparse.Namespace) -> int:
    intake = IntakeAnswers(
        time_period=args.time_period or "",
        depth=args.depth,
        clarifications=args.clarify or "",
    )
    try:
        ir = normalize(args.prompt, intake)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    taxonomy = load_taxonomy()

    if args.mode == "auto":
        decision = detect_mode(ir)
    else:
        decision = ModeDecision(mode=args.mode, reason="forced via --mode", source="forced")
    print(f"Detected mode: {decision.mode} ({decision.source}) — {decision.reason}\n")

    if args.engine == "all":
        profiles = load_all_profiles()
        results = [rewrite(ir, profiles[engine], decision) for engine in ENGINES]
    else:
        results = [rewrite(ir, load_profile(args.engine), decision)]

    print("\n\n".join(_format_result(r, taxonomy) for r in results))

    if args.memos:
        directory = Path(args.memos)
        keys = existing_keys(directory)
        print("\n\nMemos:")
        for result in results:
            memo = build_memo(args.prompt, ir, result, taxonomy)
            path, status = save_memo(memo, directory, keys)
            print(f"  [{status}] {path}")

    if args.graph:
        graph_path = Path(args.graph)
        graph = load_graph(graph_path) if graph_path.exists() else seed_graph(taxonomy)
        if args.memos:
            ingested = ingest_directory(graph, Path(args.memos))
            print(f"\nGraph: ingested {ingested} new memo(s)")
        base_tags = derive_tags(ir)
        print("\nValidation (advisory, never blocking):")
        any_flags = False
        for result in results:
            tags = {**base_tags, "engine": result.engine, "mode": result.mode}
            for flag in validate(result.tactics, tags, graph):
                any_flags = True
                print(f"  [{result.engine}] {flag.message}")
        if not any_flags:
            print("  no advisory flags")
        save_graph(graph, graph_path)
        print(f"Graph saved: {graph_path}")

    return 0


def _cmd_intake(_args: argparse.Namespace) -> int:
    print("\n".join(QUESTIONS))
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    from datetime import datetime

    from forge.memo import parse_frontmatter

    memo_path = Path(args.memo)
    try:
        frontmatter = parse_frontmatter(memo_path.read_text())
    except (OSError, ValueError) as exc:
        print(f"error: cannot read memo {memo_path}: {exc}", file=sys.stderr)
        return 2

    try:
        review = Review(
            memo_filename=memo_path.name,
            reviewer=args.reviewer,
            intent_fidelity=args.intent,
            quality=args.quality,
            depth_explanation=args.explain,
            mode_correct=args.mode_correct,
            reviewed_at=datetime.now().isoformat(timespec="seconds"),
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    sidecar = save_review(review, memo_path.parent)
    print(f"Review saved: {sidecar}")

    graph_path = Path(args.graph)
    taxonomy = load_taxonomy()
    graph = load_graph(graph_path) if graph_path.exists() else seed_graph(taxonomy)
    verdict = apply_review(graph, frontmatter, review)
    if verdict is None:
        print(f"Graph: already reviewed by {args.reviewer} — no new labels")
    else:
        print(f"Graph: applied {verdict} labels")
        for edge in graph.archive_contra():
            print(
                f"  archived contra edge: {edge.tactic} <-> "
                f"{edge.dimension}={edge.value} (neg {edge.neg}/{edge.support})"
            )
    save_graph(graph, graph_path)
    print(f"Graph saved: {graph_path}")

    accuracy = mode_accuracy(load_reviews(memo_path.parent))
    if accuracy is not None:
        print(f"Mode accuracy: {accuracy:.0%} over reviewed memos in {memo_path.parent}")
    return 0


def _fmt_edge(key) -> str:
    tactic, dimension, value = key
    return f"{tactic} <-> {dimension}={value}"


def _cmd_sufficiency(args: argparse.Namespace) -> int:
    graph_path = Path(args.graph)
    graph = load_graph(graph_path) if graph_path.exists() else seed_graph(load_taxonomy())
    report = assess(Path(args.memos), graph)

    print(f"Pending: {report.pending_memos} memo(s), {report.pending_labels} label(s)")
    for bucket in ("PROMOTE-READY", "CONTESTED", "NEEDS-MORE", "DORMANT"):
        keys = report.buckets.get(bucket, [])
        print(f"{bucket}: {len(keys)}")
        # DORMANT is mostly seeds — count only keeps the report readable.
        if bucket != "DORMANT":
            for key in keys:
                print(f"  - {_fmt_edge(key)}")
    for key in report.vetoed:
        print(f"note: {_fmt_edge(key)} would promote but is under the "
              "diversity floor (advisory)")

    if report.sufficient:
        print("sufficient: run ingest (forge rewrite --graph / graph ingest)")
        return 0
    print("insufficient: not enough new evidence to move the graph")
    return 1


def _cmd_push(args: argparse.Namespace) -> int:
    directory = Path(args.dir)
    from datetime import datetime

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = args.message or f"corpus: memo update ({stamp})"
    # Let push_corpus build the runner internally (via forge.push.make_runner)
    # so the test seam that patches make_runner takes effect.
    result = push_corpus(
        directory,
        args.repo,
        message=message,
        create_if_missing=not args.no_create,
    )
    print(f"[{result.status}] {result.report}")

    # Advisory sufficiency line (D-04): only when a graph lives in the corpus.
    graph_json = directory / "graph.json"
    if graph_json.exists():
        report = assess(directory, load_graph(graph_json))
        state = "sufficient" if report.sufficient else "insufficient"
        print(f"Sufficiency (advisory): {state} — {report.pending_memos} pending "
              f"memo(s), {len(report.would_promote)} promotion(s) available")

    # pushed / noop are successful outcomes; local / failed are not (but the
    # local copy is always retained — FR-5).
    return 0 if result.status in ("pushed", "noop") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forge",
        description="Research Prompt Forge — rewrite a general research prompt per engine.",
    )
    parser.add_argument("--version", action="version", version=f"forge {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    rewrite_p = sub.add_parser("rewrite", help="Rewrite a general prompt for one or all engines.")
    rewrite_p.add_argument("prompt", help="The general research prompt to rewrite.")
    rewrite_p.add_argument(
        "--engine",
        default="all",
        choices=[*ENGINES, "all"],
        help="Target engine, or 'all' (default).",
    )
    rewrite_p.add_argument("--time-period", default="", help="Intake Q1: recency window (e.g. '2024+').")
    rewrite_p.add_argument(
        "--depth", type=int, default=2, choices=[1, 2, 3], help="Intake Q2: reasoning layers (default 2)."
    )
    rewrite_p.add_argument("--clarify", default="", help="Intake Q3: free-text disambiguation.")
    rewrite_p.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "deep-research", "chat"],
        help="Mode: 'auto' (detect, default) or force deep-research / chat.",
    )
    rewrite_p.add_argument(
        "--memos",
        default="",
        metavar="DIR",
        help="Write an explanation memo per rewrite to DIR (e.g. research-memos).",
    )
    rewrite_p.add_argument(
        "--graph",
        default="",
        metavar="PATH",
        help="Knowledge-graph JSON file: ingest memos (with --memos), validate "
        "rewrites (advisory), and save. Seeded from the taxonomy if missing.",
    )
    rewrite_p.set_defaults(func=_cmd_rewrite)

    intake_p = sub.add_parser("intake", help="Print the three intake questions.")
    intake_p.set_defaults(func=_cmd_intake)

    review_p = sub.add_parser(
        "review",
        help="Record a distinct reviewer's rating for a memo and update the graph.",
    )
    review_p.add_argument("memo", help="Path to the memo .md file to review.")
    review_p.add_argument("--reviewer", required=True, help="Reviewer name (distinct person).")
    review_p.add_argument("--intent", type=int, required=True, choices=range(1, 6),
                          metavar="1-5", help="Intent-fidelity rating.")
    review_p.add_argument("--quality", type=int, required=True, choices=range(1, 6),
                          metavar="1-5", help="Quality rating.")
    review_p.add_argument("--explain", required=True,
                          help="Depth-of-reasoning explanation for the ratings.")
    mode_group = review_p.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--mode-correct", dest="mode_correct", action="store_true",
                            help="The detected mode was right for this prompt.")
    mode_group.add_argument("--mode-wrong", dest="mode_correct", action="store_false",
                            help="The detected mode was wrong.")
    review_p.add_argument("--graph", default="research-memos/graph.json", metavar="PATH",
                          help="Knowledge-graph JSON to update (default: research-memos/graph.json).")
    review_p.set_defaults(func=_cmd_review)

    push_p = sub.add_parser(
        "push",
        help="Commit the local memo corpus to a private GitHub repo (explicit, opt-in).",
    )
    push_p.add_argument(
        "--dir", default="research-memos", metavar="DIR",
        help="Corpus directory to push (default: research-memos).",
    )
    push_p.add_argument(
        "--repo", default=DEFAULT_REPO, metavar="SLUG",
        help=f"Private repo slug or owner/slug (default: {DEFAULT_REPO}).",
    )
    push_p.add_argument("--message", default="", help="Override the commit message.")
    push_p.add_argument(
        "--no-create", action="store_true",
        help="Fail instead of creating the private repo if it does not exist.",
    )
    push_p.set_defaults(func=_cmd_push)

    suff_p = sub.add_parser(
        "sufficiency",
        help="Assess whether enough new memo evidence exists to update the graph "
        "(read-only; exit 0 = sufficient, 1 = insufficient).",
    )
    suff_p.add_argument("--memos", default="research-memos", metavar="DIR",
                        help="Memo directory to scan (default: research-memos).")
    suff_p.add_argument("--graph", default="research-memos/graph.json", metavar="PATH",
                        help="Graph JSON to assess against (default: research-memos/graph.json).")
    suff_p.set_defaults(func=_cmd_sufficiency)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
