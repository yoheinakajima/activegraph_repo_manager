import json
import socket
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from activegraph_repo_manager import cli as cli_module
from activegraph_repo_manager.cli import main as cli_main
from activegraph_repo_manager.state import LocalStateStore
from activegraph_repo_manager.tools.github import GitHubReadOnlyClient, GitHubReadOnlyClientError

OWNER = "yoheinakajima"
REPO = "activegraph"
TOKEN = "test-token-do-not-persist"


class FakeSyncGitHubClient:
    def __init__(self) -> None:
        self.write_calls: list[str] = []

    def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        return {
            "owner": {"login": owner},
            "name": repo,
            "default_branch": "main",
            "private": False,
            "html_url": f"https://github.com/{owner}/{repo}",
        }

    def list_open_issues(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return [
            {
                "number": 23,
                "title": "Add OpenTelemetry spans",
                "state": "open",
                "labels": [{"name": "observability"}],
                "html_url": f"https://github.com/{owner}/{repo}/issues/23",
            }
        ]

    def get_issue(self, owner: str, repo: str, issue_number: int) -> dict[str, Any]:
        return {
            "number": issue_number,
            "title": "Add OpenTelemetry spans",
            "state": "open",
            "labels": [{"name": "observability"}],
        }

    def list_open_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return [self.get_pull_request(owner, repo, 24)]

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        return {
            "number": pr_number,
            "title": "Add FalkorDB event store",
            "state": "open",
            "base": {"ref": "main"},
            "head": {"ref": "feature/falkordb-eventstore", "sha": "abc123"},
            "html_url": f"https://github.com/{owner}/{repo}/pull/{pr_number}",
        }

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        return [
            {
                "filename": "activegraph/stores/falkordb.py",
                "status": "added",
                "additions": 42,
                "deletions": 0,
            }
        ]

    def get_pull_request_checks(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        return [
            {
                "name": "ci/test",
                "status": "completed",
                "conclusion": "success",
                "app": {"slug": "github-actions"},
            }
        ]


def _sync_args(state_path: Path, *token_args: str) -> list[str]:
    return [
        "sync",
        "--state",
        str(state_path),
        "--owner",
        OWNER,
        "--repo",
        REPO,
        *token_args,
    ]


def _install_fake_client_factory(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {"tokens": [], "clients": []}

    def fake_factory(token: str) -> FakeSyncGitHubClient:
        calls["tokens"].append(token)
        client = FakeSyncGitHubClient()
        calls["clients"].append(client)
        return client

    monkeypatch.setattr(cli_module, "github_readonly_client_from_token", fake_factory)
    return calls


def test_sync_fails_clearly_without_token_or_token_env(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_main(_sync_args(tmp_path / "state.sqlite"))

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "sync requires --token-env NAME or --token TOKEN" in captured.err


def test_sync_token_env_reads_only_named_env_var_and_does_not_print_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = tmp_path / ".repo-manager" / "state.sqlite"
    calls = _install_fake_client_factory(monkeypatch)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("REPO_MANAGER_TEST_TOKEN", TOKEN)

    assert cli_main(_sync_args(state_path, "--token-env", "REPO_MANAGER_TEST_TOKEN")) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert calls["tokens"] == [TOKEN]
    assert payload["sync_complete"] is True
    assert TOKEN not in captured.out
    assert TOKEN not in captured.err


def test_sync_token_env_missing_named_variable_fails_without_token_leak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = tmp_path / "state.sqlite"
    monkeypatch.setenv("OTHER_TOKEN", TOKEN)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        cli_main(_sync_args(state_path, "--token-env", "GITHUB_TOKEN"))

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "sync requires environment variable GITHUB_TOKEN to be set" in captured.err
    assert TOKEN not in captured.out
    assert TOKEN not in captured.err


def test_sync_persists_github_state_status_and_ask_answers_without_token_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = tmp_path / ".repo-manager" / "state.sqlite"
    calls = _install_fake_client_factory(monkeypatch)

    assert cli_main(_sync_args(state_path, "--token", TOKEN)) == 0
    captured = capsys.readouterr()
    sync_payload = json.loads(captured.out)

    assert TOKEN not in captured.out
    assert TOKEN not in captured.err
    assert sync_payload["repository_external_key"] == "gh:repo:yoheinakajima/activegraph"
    assert sync_payload["issues_seen"] == 1
    assert sync_payload["pull_requests_seen"] == 1
    assert sync_payload["pr_diffs_seen"] == 1
    assert sync_payload["checks_seen"] == 1
    assert sync_payload["write_actions_attempted"] == 0
    assert sync_payload["github_write_count"] == 0
    assert sync_payload["live_llm_call_count"] == 0
    assert calls["clients"][0].write_calls == []

    with LocalStateStore(state_path) as store:
        assert store.count_objects_by_type("repository") == 1
        assert store.count_objects_by_type("issue") == 1
        assert store.count_objects_by_type("pull_request") == 1
        assert store.count_objects_by_type("pr_diff") == 1
        assert store.count_objects_by_type("check_run") == 1
        assert store.get_summary("github_readonly_sync")["github_write_count"] == 0
        snapshot = json.dumps(store.deterministic_snapshot(), sort_keys=True)
        assert TOKEN not in snapshot

    assert TOKEN.encode() not in state_path.read_bytes()

    assert cli_main(["status", "--state", str(state_path)]) == 0
    status_payload = json.loads(capsys.readouterr().out)
    status_item = status_payload["items"][0]
    assert status_item["github_write_count"] == 0
    assert status_item["live_llm_call_count"] == 0
    assert status_item["object_counts"]["issue"] == 1
    assert status_item["object_counts"]["pull_request"] == 1

    assert cli_main(["ask", "--state", str(state_path), "what issues are open?"]) == 0
    issue_answer = json.loads(capsys.readouterr().out)
    assert issue_answer["source"] == "local_state"
    assert "Open issues" in issue_answer["answer"]
    assert issue_answer["items"][0]["number"] == 23

    assert cli_main(["ask", "--state", str(state_path), "what PRs are open?"]) == 0
    pr_answer = json.loads(capsys.readouterr().out)
    assert pr_answer["source"] == "local_state"
    assert "Open pull requests" in pr_answer["answer"]
    assert pr_answer["items"][0]["number"] == 24


def test_readonly_client_exposes_no_write_methods() -> None:
    client = GitHubReadOnlyClient(token="fake-token", http_get=lambda _url, _headers: (200, b"{}", {}))
    forbidden = {
        "post_comment",
        "apply_label",
        "request_changes",
        "approve_pr",
        "open_issue",
        "open_pull_request",
        "post",
        "patch",
        "put",
        "delete",
    }

    assert forbidden.isdisjoint(set(dir(client)))


def test_readonly_client_uses_get_only_fake_http_and_filters_issue_prs() -> None:
    calls: list[dict[str, Any]] = []

    def fake_http_get(url: str, headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
        calls.append({"method": "GET", "url": url, "headers": headers})
        if "/issues" in url:
            body = [
                {"number": 1, "title": "issue", "state": "open"},
                {"number": 2, "title": "pr issue", "state": "open", "pull_request": {}},
            ]
        elif "/pulls/24/files" in url:
            body = [{"filename": "a.py", "status": "modified", "additions": 1, "deletions": 0}]
        elif "/pulls/24" in url:
            body = {"number": 24, "head": {"sha": "abc123"}}
        elif "/pulls" in url:
            body = [{"number": 24, "head": {"sha": "abc123"}}]
        elif "/check-runs" in url:
            body = {"check_runs": [{"name": "ci/test", "status": "completed"}]}
        else:
            body = {"owner": {"login": OWNER}, "name": REPO, "default_branch": "main"}
        return 200, json.dumps(body).encode("utf-8"), {}

    client = GitHubReadOnlyClient(token=TOKEN, http_get=fake_http_get)

    assert client.get_repository(OWNER, REPO)["name"] == REPO
    assert [issue["number"] for issue in client.list_open_issues(OWNER, REPO)] == [1]
    assert client.list_open_pull_requests(OWNER, REPO)[0]["number"] == 24
    assert client.get_pull_request_files(OWNER, REPO, 24)[0]["filename"] == "a.py"
    assert client.get_pull_request_checks(OWNER, REPO, 24)[0]["name"] == "ci/test"

    assert calls
    assert {call["method"] for call in calls} == {"GET"}
    assert all(call["headers"]["Authorization"] == f"Bearer {TOKEN}" for call in calls)
    assert all(call["headers"]["User-Agent"] == "activegraph-repo-manager-readonly/1" for call in calls)


def test_readonly_client_http_error_is_clear() -> None:
    client = GitHubReadOnlyClient(
        token="fake-token",
        http_get=lambda _url, _headers: (403, b'{"message":"denied"}', {}),
    )

    with pytest.raises(GitHubReadOnlyClientError, match="GitHub GET failed with HTTP 403"):
        client.get_repository(OWNER, REPO)


def test_cli_sync_tests_do_not_need_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_network(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("network call attempted")

    _install_fake_client_factory(monkeypatch)
    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket, "socket", fail_network)

    assert cli_main(_sync_args(tmp_path / "state.sqlite", "--token", TOKEN)) == 0
    assert json.loads(capsys.readouterr().out)["sync_complete"] is True


def test_existing_keyless_demo_behavior_remains_unchanged(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = tmp_path / "keyless.sqlite"

    assert cli_main(["keyless-demo", "--state", str(state_path)]) == 0
    demo_payload = json.loads(capsys.readouterr().out)

    assert demo_payload["state_seeded"] is True
    assert demo_payload["source"] == "offline_fixtures"
    assert demo_payload["external_write_performed"] is False
    assert demo_payload["live_llm_call_count"] == 0
    assert demo_payload["object_counts"]["issue"] == 1


def test_token_is_not_persisted_in_sqlite_after_explicit_token_sync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = tmp_path / "state.sqlite"
    _install_fake_client_factory(monkeypatch)

    assert cli_main(_sync_args(state_path, "--token", TOKEN)) == 0
    _ = capsys.readouterr()

    with sqlite3.connect(state_path) as connection:
        rows = connection.execute(
            "SELECT payload_json FROM objects UNION ALL SELECT payload_json FROM summaries"
        ).fetchall()
    assert rows
    assert all(TOKEN not in str(row[0]) for row in rows)
