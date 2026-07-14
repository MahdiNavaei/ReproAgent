"""ReproAgent command-line interface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from reproagent.agentcase import (
    AgentCaseError,
    atomic_dump_agentcase,
    load_agentcase,
    summarize_agentcase,
)

from reproagent import __version__
from reproagent.replay import ReplayError, mock_replay


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reproagent",
        description=(
            "Capture, validate, inspect, and safely replay portable ReproAgent execution cases."
        ),
    )
    parser.add_argument("--version", action="version", version=f"reproagent {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser("validate", help="Validate an .agentcase file")
    validate_parser.add_argument("case", help="Path to an .agentcase file")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect an .agentcase file")
    inspect_parser.add_argument("case", help="Path to an .agentcase file")

    replay_parser = subparsers.add_parser(
        "replay",
        help="Create a safe replay artifact without executing live providers or tools",
    )
    replay_parser.add_argument("case", help="Path to the source .agentcase file")
    replay_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic data-only mock replay",
    )
    replay_parser.add_argument(
        "--output",
        required=True,
        help="Path for the replayed .agentcase file",
    )
    replay_parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Explicitly permit replay of a non-complete capture; still executes no live behavior",
    )
    replay_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly allow replacement of an existing output file",
    )

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

    if args.command == "replay":
        if not args.mock:
            print("error: only explicit --mock replay is supported", file=sys.stderr)
            return 2
        try:
            replayed = mock_replay(case, allow_incomplete=args.allow_incomplete)
            atomic_dump_agentcase(
                replayed,
                args.output,
                overwrite=args.overwrite,
                create_parents=True,
            )
        except (AgentCaseError, ReplayError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(
            f"mock replay AgentCase {replayed.case_id} created from {case.case_id} at {args.output}"
        )
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2
