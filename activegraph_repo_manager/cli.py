"""Command-line surface for local, offline repo-manager usage."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from activegraph_repo_manager.demo_state import seed_keyless_demo_state
from activegraph_repo_manager.monitoring import write_monitoring_artifacts
from activegraph_repo_manager.query import answer_question
from activegraph_repo_manager.state import DEFAULT_STATE_PATH, LocalStateIngestAdapter, LocalStateStore
from activegraph_repo_manager.tools.github import github_readonly_client_from_token, sync_github_readonly


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
    sync_parser = subparsers.add_parser("sync", help="Sync live GitHub read-only state into local SQLite.")
    add_state_argument(sync_parser)
    sync_parser.add_argument("--owner", required=True, help="GitHub repository owner to read.")
    sync_parser.add_argument("--repo", required=True, help="GitHub repository name to read.")
    token_group = sync_parser.add_mutually_exclusive_group()
    token_group.add_argument("--token-env", help="Name of the environment variable containing the GitHub token.")
    token_group.add_argument("--token", help="Explicit GitHub token value. The token is never printed or persisted.")

    report_parser = subparsers.add_parser("report", help="Generate monitoring artifacts from local state.")
    add_state_argument(report_parser)
    report_parser.add_argument("--out", required=True, help="Directory for status.json and report.md artifacts.")
    report_parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Also generate dashboard/index.html under the output directory.",
    )

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
        elif args.command == "sync":
            token = _resolve_sync_token(args, parser)
            client = github_readonly_client_from_token(token)
            sync_summary = sync_github_readonly(
                client=client,
                owner=args.owner,
                repo=args.repo,
                store=LocalStateIngestAdapter(store),
            )
            result = _persist_sync_summary(store, sync_summary, owner=args.owner, repo=args.repo)
        elif args.command == "report":
            result = write_monitoring_artifacts(store, args.out, include_dashboard=args.dashboard)
        elif args.command == "snapshot":
            result = store.deterministic_snapshot()
        else:
            parser.error(f"unknown command: {args.command}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _resolve_sync_token(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    if args.token_env:
        token = os.environ.get(args.token_env)
        if not token:
            parser.error(f"sync requires environment variable {args.token_env} to be set")
        return token
    if args.token:
        return args.token
    parser.error("sync requires --token-env NAME or --token TOKEN")
    raise AssertionError("parser.error exits")


def _persist_sync_summary(
    store: LocalStateStore, sync_summary: dict[str, int | str], *, owner: str, repo: str
) -> dict[str, object]:
    stored_summary = {
        "mode": "live_github_readonly_sync",
        "source": "github_readonly_rest",
        "owner": owner,
        "repo": repo,
        "read_only": True,
        "external_write_performed": False,
        **sync_summary,
        "object_counts": store.object_counts(),
    }
    store.upsert_summary("github_readonly_sync", stored_summary)
    store.upsert_summary(
        "repo_manager_status",
        {
            "mode": "live_github_readonly_sync",
            "source": "local_state",
            "repository_external_key": sync_summary["repository_external_key"],
            "read_only": True,
            "external_write_performed": False,
            "github_write_count": sync_summary["github_write_count"],
            "live_llm_call_count": sync_summary["live_llm_call_count"],
            "object_counts": store.object_counts(),
        },
    )
    return {
        "sync_complete": True,
        "source": "github_readonly_rest",
        "read_only": True,
        "external_write_performed": False,
        **sync_summary,
        "object_counts": store.object_counts(),
    }


if __name__ == "__main__":
    raise SystemExit(main())
