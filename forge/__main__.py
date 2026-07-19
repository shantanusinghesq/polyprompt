"""`python -m forge` / `forge` CLI entry point.

M0: a single `rewrite --engine perplexity` subcommand. The `/forge-prompts`
plugin command shells out to this.
"""

from __future__ import annotations

import argparse
import sys

from forge import __version__
from forge.engines.perplexity import perplexity_transform

_ENGINES = {
    "perplexity": perplexity_transform,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forge",
        description="Research Prompt Forge — rewrite a general research prompt per engine.",
    )
    parser.add_argument("--version", action="version", version=f"forge {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    rewrite = sub.add_parser("rewrite", help="Rewrite a general prompt for a target engine.")
    rewrite.add_argument("prompt", help="The general research prompt to rewrite.")
    rewrite.add_argument(
        "--engine",
        default="perplexity",
        choices=sorted(_ENGINES),
        help="Target engine (M0: perplexity only).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "rewrite":
        try:
            print(_ENGINES[args.engine](args.prompt))
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0

    parser.error(f"unknown command: {args.command}")  # unreachable (required=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
