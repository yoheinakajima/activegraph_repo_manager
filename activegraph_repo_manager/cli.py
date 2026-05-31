"""Command-line surface for local read-only repo-manager usage."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Callable, Sequence

from activegraph_repo_manager.demo_state import seed_keyless_demo_state
from activegraph_repo_manager.query import answer_question
from activegraph_repo_manager.state import DEFAULT_STATE_PATH, LocalStateIngestAdapter, LocalStateStore
from activegraph_repo_manager.tools.github import github_readonly_client_from_token, sync_github_readonly

MIN_RUN_INTERVAL_SECONDS = 30
DEFAULT_RUN_INTERVAL_SECONDS = 300


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="activegraph-repo-manager",
        description="Local, read-only command surface for the ActiveGraph repo-governance pack.",
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
    _add_github_readonly_arguments(sync_parser, add_state_argument)

    run_parser = subparsers.add_parser("run", help="Periodically sync live GitHub read-only state into local SQLite.")
    _add_github_readonly_arguments(run_parser, add_state_argument)
    run_parser.add_argument(
        "--interval",
        type=_positive_interval_seconds,
        default=DEFAULT_RUN_INTERVAL_SECONDS,
        help=(
            "Seconds to wait between read-only sync iterations. Defaults to 300; "
            "must be at least 30 unless --once is used."
        ),
    )
    run_limit_group = run_parser.add_mutually_exclusive_group()
    run_limit_group.add_argument(
        "--once",
        action="store_true",
        help="Perform exactly one read-only sync iteration and exit without sleeping.",
    )
    run_limit_group.add_argument(
        "--max-iterations",
        type=_positive_iteration_count,
        default=None,
        help="Perform exactly N read-only sync iterations and exit.",
    )

    snapshot_parser = subparsers.add_parser("snapshot", help="Print a deterministic local-state snapshot.")
    add_state_argument(snapshot_parser)
    return parser


def _add_github_readonly_arguments(
    subparser: argparse.ArgumentParser, add_state_argument: Callable[[argparse.ArgumentParser], None]
) -> None:
    add_state_argument(subparser)
    subparser.add_argument("--owner", required=True, help="GitHub repository owner to read.")
    subparser.add_argument("--repo", required=True, help="GitHub repository name to read.")
    token_group = subparser.add_mutually_exclusive_group()
    token_group.add_argument("--token-env", help="Name of the environment variable containing the GitHub token.")
    token_group.add_argument("--token", help="Explicit GitHub token value. The token is never printed or persisted.")


def _positive_interval_seconds(raw_value: str) -> int:
    value = _positive_int(raw_value, argument_name="interval")
    return value


def _positive_iteration_count(raw_value: str) -> int:
    value = _positive_int(raw_value, argument_name="max-iterations")
    return value


def _positive_int(raw_value: str, *, argument_name: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{argument_name} must be a positive integer") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError(f"{argument_name} must be a positive integer")
    return value


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
            result = _sync_once(store=store, client=client, owner=args.owner, repo=args.repo)
        elif args.command == "run":
            _validate_run_interval(args, parser)
            token = _resolve_run_token(args, parser)
            client = github_readonly_client_from_token(token)
            return _run_periodic_sync(
                store=store,
                client=client,
                owner=args.owner,
                repo=args.repo,
                interval_seconds=args.interval,
                max_iterations=_run_iteration_limit(args),
            )
        elif args.command == "snapshot":
            result = store.deterministic_snapshot()
        else:
            parser.error(f"unknown command: {args.command}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _validate_run_interval(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.once:
        return
    if args.interval < MIN_RUN_INTERVAL_SECONDS:
        parser.error(
            f"run requires --interval to be at least {MIN_RUN_INTERVAL_SECONDS} seconds "
            "unless --once is used"
        )


def _run_iteration_limit(args: argparse.Namespace) -> int | None:
    if args.once:
        return 1
    return args.max_iterations


def _resolve_sync_token(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    return _resolve_github_token(args, parser, command_name="sync")


def _resolve_run_token(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    return _resolve_github_token(args, parser, command_name="run")


def _resolve_github_token(args: argparse.Namespace, parser: argparse.ArgumentParser, *, command_name: str) -> str:
    if args.token_env:
        token = os.environ.get(args.token_env)
        if not token:
            parser.error(f"{command_name} requires environment variable {args.token_env} to be set")
        return token
    if args.token:
        return args.token
    parser.error(f"{command_name} requires --token-env NAME or --token TOKEN")
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


def _sync_once(*, store: LocalStateStore, client: object, owner: str, repo: str) -> dict[str, object]:
    sync_summary = sync_github_readonly(
        client=client,
        owner=owner,
        repo=repo,
        store=LocalStateIngestAdapter(store),
    )
    return _persist_sync_summary(store, sync_summary, owner=owner, repo=repo)


def _run_periodic_sync(
    *,
    store: LocalStateStore,
    client: object,
    owner: str,
    repo: str,
    interval_seconds: int,
    max_iterations: int | None = None,
) -> int:
    iteration = 0
    try:
        while True:
            iteration += 1
            sync_result = _sync_once(store=store, client=client, owner=owner, repo=repo)
            run_result = _persist_run_summary(
                store,
                sync_result,
                owner=owner,
                repo=repo,
                interval_seconds=interval_seconds,
                iteration=iteration,
            )
            print(json.dumps(run_result, sort_keys=True), flush=True)
            if max_iterations is not None and iteration >= max_iterations:
                return 0
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        stopped_result = {
            "run_stopped": True,
            "reason": "keyboard_interrupt",
            "source": "github_readonly_rest",
            "read_only": True,
            "external_write_performed": False,
            "github_write_count": 0,
            "live_llm_call_count": 0,
            "iterations_completed": iteration,
        }
        store.upsert_summary("github_readonly_run", stopped_result)
        print(json.dumps(stopped_result, sort_keys=True), flush=True)
        return 0


def _persist_run_summary(
    store: LocalStateStore,
    sync_result: dict[str, object],
    *,
    owner: str,
    repo: str,
    interval_seconds: int,
    iteration: int,
) -> dict[str, object]:
    run_summary = {
        "run_iteration_complete": True,
        "mode": "live_github_readonly_run_loop",
        "source": "github_readonly_rest",
        "owner": owner,
        "repo": repo,
        "interval_seconds": interval_seconds,
        "iteration": iteration,
        "read_only": True,
        "external_write_performed": False,
        "github_write_count": sync_result["github_write_count"],
        "live_llm_call_count": sync_result["live_llm_call_count"],
        "object_counts": store.object_counts(),
        "last_sync": sync_result,
    }
    store.upsert_summary("github_readonly_run", run_summary)
    return run_summary


if __name__ == "__main__":
    raise SystemExit(main())
