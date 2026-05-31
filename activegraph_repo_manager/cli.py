"""Command-line surface for local, offline repo-manager usage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from activegraph_repo_manager.demo_state import seed_keyless_demo_state
from activegraph_repo_manager.query import answer_question
from activegraph_repo_manager.state import DEFAULT_STATE_PATH, LocalStateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="activegraph-repo-manager",
        description="Offline, read-only command surface for the ActiveGraph repo-governance pack.",
    )
    parser.add_argument(
        "--state",
        default=str(DEFAULT_STATE_PATH),
        help="SQLite state path. Use ':memory:' only for programmatic tests.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_state_argument(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "--state",
            dest="command_state",
            default=None,
            help="SQLite state path. Overrides the global --state value.",
        )

    demo_parser = subparsers.add_parser(
        "demo",
        aliases=["keyless-demo"],
        help="Seed local state from offline fixtures.",
    )
    add_state_argument(demo_parser)
    demo_parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Print the deterministic state snapshot after seeding.",
    )

    ask_parser = subparsers.add_parser("ask", help="Answer a question from tracked local state.")
    add_state_argument(ask_parser)
    ask_parser.add_argument("question", nargs="+", help="Question to answer from local state.")

    status_parser = subparsers.add_parser("status", help="Show current repo-manager status from local state.")
    add_state_argument(status_parser)
    snapshot_parser = subparsers.add_parser("snapshot", help="Print a deterministic local-state snapshot.")
    add_state_argument(snapshot_parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    selected_state = args.command_state or args.state
    state_path = Path(selected_state) if selected_state != ":memory:" else selected_state

    with LocalStateStore(state_path) as store:
        if args.command in {"demo", "keyless-demo"}:
            result = seed_keyless_demo_state(store)
            if args.snapshot:
                result = {"seed_summary": result, "snapshot": store.deterministic_snapshot()}
        elif args.command == "ask":
            result = answer_question(" ".join(args.question), store)
        elif args.command == "status":
            result = answer_question("what is the current repo manager status?", store)
        elif args.command == "snapshot":
            result = store.deterministic_snapshot()
        else:
            parser.error(f"unknown command: {args.command}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
