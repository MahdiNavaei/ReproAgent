"""Minimal ReproAgent command-line interface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from reproagent import __version__
from reproagent.agentcase import AgentCaseError, load_agentcase, summarize_agentcase


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reproagent",
        description="Validate and inspect portable ReproAgent execution cases.",
    )
    parser.add_argument("--version", action="version", version=f"reproagent {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser("validate", help="Validate an .agentcase file")
    validate_parser.add_argument("case", help="Path to an .agentcase file")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect an .agentcase file")
    inspect_parser.add_argument("case", help="Path to an .agentcase file")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        case = load_agentcase(args.case)
    except AgentCaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate":
        print(f"valid AgentCase {case.case_id} (format {case.format_version})")
        return 0

    if args.command == "inspect":
        print(summarize_agentcase(case))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2
