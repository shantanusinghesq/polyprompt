"""`python -m forge` / `forge` CLI entry point.

M1 subcommands:
  rewrite  — normalize a prompt (+ intake answers) and rewrite it for one or all engines
  intake   — print the three intake questions (the /forge-prompts command uses this)

The `/forge-prompts` plugin command asks the three questions, then shells out to
`forge rewrite` with the answers as flags.
"""

from __future__ import annotations

import argparse
import sys

from forge import __version__
from forge.intake import IntakeAnswers, QUESTIONS
from forge.ir import normalize
from forge.profile import ENGINES, load_all_profiles, load_profile
from forge.rewrite import RewriteResult, rewrite


def _format_result(result: RewriteResult) -> str:
    lines = [
        f"## {result.engine.upper()}  [mode: {result.mode} · profile {result.profile_version}]",
        "",
        result.prompt,
        "",
        "Adaptations:",
    ]
    lines += [f"  - {a}" for a in result.adaptations]
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

    if args.engine == "all":
        profiles = load_all_profiles()
        results = [rewrite(ir, profiles[engine]) for engine in ENGINES]
    else:
        results = [rewrite(ir, load_profile(args.engine))]

    print("\n\n".join(_format_result(r) for r in results))
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
