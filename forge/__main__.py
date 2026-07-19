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
from forge.rewrite import RewriteResult, rewrite
from forge.store import existing_keys, save_memo
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
