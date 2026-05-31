"""Combined coverage for the local state store, query layer, and CLI contract."""

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from activegraph_repo_manager.cli import main as cli_main
from activegraph_repo_manager.demo_state import seed_keyless_demo_state
from activegraph_repo_manager.query import answer_question
from activegraph_repo_manager.state import LocalStateStore

ROOT = Path(__file__).resolve().parents[1]


def _offline_subprocess_env() -> dict[str, str]:
    return {
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _run_cli(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        check=True,
        text=True,
        capture_output=True,
        cwd=cwd or ROOT,
        env=_offline_subprocess_env(),
    )


def test_local_state_upserts_objects_relations_summaries_and_snapshots_deterministically() -> None:
    store = LocalStateStore.in_memory()
    try:
        store.upsert_object(
            "issue",
            {
                "external_key": "gh:issue:owner/repo#23",
                "source": "test",
                "number": 23,
                "title": "Original",
                "status": "open",
            },
        )
        store.upsert_object(
            "issue",
            {
                "external_key": "gh:issue:owner/repo#23",
                "source": "test",
                "number": 23,
                "title": "Patched",
                "status": "open",
            },
        )
        store.upsert_relation("relates_to", {"from": "a", "to": "b", "relation": "relates_to"})
        store.upsert_summary("sync:demo", {"issues_seen": 1, "live_llm_call_count": 0})

        assert store.count_objects_by_type("issue") == 1
        assert store.get_object("issue", "gh:issue:owner/repo#23")["title"] == "Patched"
        assert store.list_relations("relates_to") == [
            {"from": "a", "relation": "relates_to", "to": "b"}
        ]
        assert store.get_summary("sync:demo") == {"issues_seen": 1, "live_llm_call_count": 0}
        assert store.deterministic_snapshot() == store.deterministic_snapshot()
    finally:
        store.close()


def test_seed_keyless_demo_state_populates_supported_local_objects() -> None:
    store = LocalStateStore.in_memory()
    try:
        summary = seed_keyless_demo_state(store)

        assert summary["state_seeded"] is True
        assert summary["external_write_performed"] is False
        assert summary["live_llm_call_count"] == 0
        assert store.count_objects_by_type("repository") == 1
        assert store.count_objects_by_type("issue") == 1
        assert store.count_objects_by_type("pull_request") == 1
        assert store.count_objects_by_type("repo_file") > 0
        assert store.count_objects_by_type("symbol") > 0
        assert store.count_objects_by_type("test_surface") > 0
        assert store.count_objects_by_type("review_finding") == 1
        assert store.count_objects_by_type("planning_patch_proposal") == 1
        assert store.get_summary("repo_manager_status")["read_only"] is True
    finally:
        store.close()


def test_query_layer_answers_required_question_families_from_local_state() -> None:
    store = LocalStateStore.in_memory()
    try:
        seed_keyless_demo_state(store)

        questions = {
            "what issues are open?": "Open issues",
            "what PRs are open?": "Open pull requests",
            "what PRs need review?": "need review attention",
            "what is blocking planning?": "approval gates",
            "what planning proposals exist?": "Planning patch proposals",
            "what external actions are proposed or dry-run only?": "dry-run/proposal",
            "summarize issue 23": "Issue 23",
            "summarize PR 24": "Pull Request 24",
            "what is the current repo manager status?": "offline, read-only",
            "what is safe to run?": "safe offline/keyless",
        }
        for question, expected in questions.items():
            answer = answer_question(question, store)
            assert answer["source"] == "local_state"
            assert answer["live_llm_call_count"] == 0
            assert expected in answer["answer"]
    finally:
        store.close()


def test_query_layer_returns_clear_deterministic_response_for_unsupported_questions() -> None:
    store = LocalStateStore.in_memory()
    try:
        answer = answer_question("can you deploy this repo?", store)
        assert answer == {
            "question": "can you deploy this repo?",
            "answer": "I can answer from local state about open issues, open PRs, PRs needing review, planning blockers, planning proposals, external action proposals, issue/PR summaries, repo-manager status, and safe commands.",
            "items": [],
            "source": "local_state",
            "live_llm_call_count": 0,
        }
    finally:
        store.close()


def test_cli_keyless_demo_alias_via_cli_module_writes_only_requested_state_path(tmp_path) -> None:
    state_path = tmp_path / ".repo-manager" / "state.sqlite"

    demo = _run_cli(
        ["-m", "activegraph_repo_manager.cli", "keyless-demo", "--state", str(state_path)]
    )
    demo_payload = json.loads(demo.stdout)

    assert demo_payload["state_seeded"] is True
    assert demo_payload["external_write_performed"] is False
    assert demo_payload["live_llm_call_count"] == 0
    assert state_path.exists()
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == {
        Path(".repo-manager"),
        Path(".repo-manager/state.sqlite"),
    }


def test_cli_keyless_demo_alias_via_package_entrypoint_then_status_and_ask(tmp_path) -> None:
    state_path = tmp_path / ".repo-manager" / "state.sqlite"

    package_demo = _run_cli(
        ["-m", "activegraph_repo_manager", "keyless-demo", "--state", str(state_path)]
    )
    assert json.loads(package_demo.stdout)["state_seeded"] is True

    status = _run_cli(
        ["-m", "activegraph_repo_manager.cli", "status", "--state", str(state_path)]
    )
    status_payload = json.loads(status.stdout)
    assert status_payload["source"] == "local_state"
    assert status_payload["live_llm_call_count"] == 0
    assert status_payload["items"][0]["github_write_count"] == 0
    assert status_payload["items"][0]["external_write_performed"] is False

    ask = _run_cli(
        [
            "-m",
            "activegraph_repo_manager.cli",
            "ask",
            "--state",
            str(state_path),
            "what PRs need review?",
        ]
    )
    ask_payload = json.loads(ask.stdout)
    assert ask_payload["source"] == "local_state"
    assert ask_payload["live_llm_call_count"] == 0
    assert "need review attention" in ask_payload["answer"]
    assert ask_payload["items"][0]["number"] == 24


def test_cli_demo_command_remains_available_for_backwards_compatibility(tmp_path) -> None:
    state_path = tmp_path / "repo-manager.sqlite3"

    demo = _run_cli(
        ["-m", "activegraph_repo_manager", "--state", str(state_path), "demo"]
    )
    demo_payload = json.loads(demo.stdout)
    assert demo_payload["state_seeded"] is True
    assert demo_payload["external_write_performed"] is False

    ask = _run_cli(
        [
            "-m",
            "activegraph_repo_manager",
            "--state",
            str(state_path),
            "ask",
            "summarize PR 24",
        ]
    )
    ask_payload = json.loads(ask.stdout)
    assert ask_payload["source"] == "local_state"
    assert ask_payload["live_llm_call_count"] == 0
    assert "Pull Request 24" in ask_payload["answer"]
    assert ask_payload["items"][0]["review_findings"]


def test_cli_unsupported_commands_fail_clearly(tmp_path) -> None:
    state_path = tmp_path / "state.sqlite"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "activegraph_repo_manager.cli",
            "unsupported-command",
            "--state",
            str(state_path),
        ],
        check=False,
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=_offline_subprocess_env(),
    )

    assert result.returncode != 0
    assert "invalid choice" in result.stderr
    assert "unsupported-command" in result.stderr


def test_cli_requires_no_credentials_network_or_live_llm_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    credential_names = {
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "API_KEY",
        "TOKEN",
    }

    class FailingEnviron(dict):
        def get(self, key: object, default: object | None = None) -> object | None:
            if str(key) in credential_names:
                raise AssertionError(f"credential environment variable read attempted: {key}")
            return default

        def __getitem__(self, key: object) -> object:
            if str(key) in credential_names:
                raise AssertionError(f"credential environment variable read attempted: {key}")
            raise KeyError(key)

    def fail_getenv(name: str, default: object | None = None) -> object | None:
        if name in credential_names:
            raise AssertionError(f"credential environment variable read attempted: {name}")
        return default

    def fail_network(*args: Any, **kwargs: Any) -> object:
        raise AssertionError("network call attempted")

    monkeypatch.setattr(os, "environ", FailingEnviron())
    monkeypatch.setattr(os, "getenv", fail_getenv)
    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket, "socket", fail_network)

    state_path = tmp_path / "state.sqlite"
    assert cli_main(["keyless-demo", "--state", str(state_path)]) == 0
    demo_payload = json.loads(capsys.readouterr().out)
    assert demo_payload["live_llm_call_count"] == 0
    assert demo_payload["external_write_performed"] is False

    assert cli_main(["ask", "--state", str(state_path), "what is the current repo manager status?"]) == 0
    ask_payload = json.loads(capsys.readouterr().out)
    assert ask_payload["source"] == "local_state"
    assert ask_payload["live_llm_call_count"] == 0
    assert ask_payload["items"][0]["github_write_count"] == 0
