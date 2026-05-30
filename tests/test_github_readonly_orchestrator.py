import os
import socket
from collections.abc import Iterator
from typing import Any

import pytest

from activegraph_repo_manager.behaviors.ingest_github import InMemoryExternalStore
from activegraph_repo_manager.tools.github import sync_github_readonly


OWNER = "yoheinakajima"
REPO = "activegraph"


class FakeGitHubClient:
    def __init__(self) -> None:
        self.head_sha = "abc123"
        self.read_calls: list[tuple[str, str, str, int | None]] = []
        self.write_calls: list[str] = []

    def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        self.read_calls.append(("get_repository", owner, repo, None))
        return {
            "owner": {"login": owner},
            "name": repo,
            "default_branch": "main",
            "private": False,
            "html_url": f"https://github.com/{owner}/{repo}",
        }

    def list_open_issues(self, owner: str, repo: str) -> list[dict[str, Any]]:
        self.read_calls.append(("list_open_issues", owner, repo, None))
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
        self.read_calls.append(("get_issue", owner, repo, issue_number))
        return {
            "number": issue_number,
            "title": "Add OpenTelemetry spans",
            "state": "open",
            "labels": [{"name": "observability"}],
        }

    def list_open_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]:
        self.read_calls.append(("list_open_pull_requests", owner, repo, None))
        return [self.get_pull_request(owner, repo, 24)]

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        self.read_calls.append(("get_pull_request", owner, repo, pr_number))
        return {
            "number": pr_number,
            "title": "Add FalkorDB event store",
            "state": "open",
            "base": {"ref": "main"},
            "head": {"ref": "feature/falkordb-eventstore", "sha": self.head_sha},
            "html_url": f"https://github.com/{owner}/{repo}/pull/{pr_number}",
        }

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        self.read_calls.append(("get_pull_request_files", owner, repo, pr_number))
        return [
            {
                "filename": "activegraph/stores/falkordb.py",
                "status": "added",
                "additions": 42,
                "deletions": 0,
            }
        ]

    def get_pull_request_checks(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        self.read_calls.append(("get_pull_request_checks", owner, repo, pr_number))
        return [
            {
                "name": "ci/test",
                "status": "completed",
                "conclusion": "success",
                "app": {"slug": "github-actions"},
            }
        ]

    def post_comment(self, *_args: Any, **_kwargs: Any) -> None:
        self.write_calls.append("post_comment")
        raise AssertionError("write method must not be called")

    def apply_label(self, *_args: Any, **_kwargs: Any) -> None:
        self.write_calls.append("apply_label")
        raise AssertionError("write method must not be called")

    def request_changes(self, *_args: Any, **_kwargs: Any) -> None:
        self.write_calls.append("request_changes")
        raise AssertionError("write method must not be called")

    def approve_pr(self, *_args: Any, **_kwargs: Any) -> None:
        self.write_calls.append("approve_pr")
        raise AssertionError("write method must not be called")

    def open_issue(self, *_args: Any, **_kwargs: Any) -> None:
        self.write_calls.append("open_issue")
        raise AssertionError("write method must not be called")

    def open_pull_request(self, *_args: Any, **_kwargs: Any) -> None:
        self.write_calls.append("open_pull_request")
        raise AssertionError("write method must not be called")


class NoCredentialEnvironment(dict[str, str]):
    def __getitem__(self, key: str) -> str:
        raise AssertionError(f"credential/environment read attempted for {key}")

    def get(self, key: str, default: str | None = None) -> str | None:
        raise AssertionError(f"credential/environment read attempted for {key}")

    def __contains__(self, key: object) -> bool:
        raise AssertionError(f"credential/environment read attempted for {key}")

    def items(self) -> Iterator[tuple[str, str]]:
        raise AssertionError("credential/environment read attempted")


@pytest.fixture
def no_credentials_or_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_network(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("network call attempted")

    monkeypatch.setattr(os, "getenv", lambda *_args, **_kwargs: forbidden_network())
    monkeypatch.setattr(os, "environ", NoCredentialEnvironment())
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket, "socket", forbidden_network)


def keys_with_prefix(store: InMemoryExternalStore, prefix: str) -> list[str]:
    return sorted(key for key in store.records if key.startswith(prefix))


def test_sync_uses_injected_client_and_fetches_expected_readonly_resources(
    no_credentials_or_network: None,
) -> None:
    client = FakeGitHubClient()
    store = InMemoryExternalStore()

    summary = sync_github_readonly(client=client, owner=OWNER, repo=REPO, store=store)

    assert client.read_calls == [
        ("get_repository", OWNER, REPO, None),
        ("list_open_issues", OWNER, REPO, None),
        ("list_open_pull_requests", OWNER, REPO, None),
        ("get_pull_request", OWNER, REPO, 24),
        ("get_pull_request_files", OWNER, REPO, 24),
        ("get_pull_request_checks", OWNER, REPO, 24),
    ]
    assert client.write_calls == []
    assert summary["repository_external_key"] == "gh:repo:yoheinakajima/activegraph"
    assert summary["issues_seen"] == 1
    assert summary["pull_requests_seen"] == 1
    assert summary["pr_diffs_seen"] == 1
    assert summary["checks_seen"] == 1
    assert summary["write_actions_attempted"] == 0
    assert summary["github_write_count"] == 0
    assert summary["live_llm_call_count"] == 0


def test_sync_normalizes_external_keys_and_never_calls_write_methods(
    no_credentials_or_network: None,
) -> None:
    client = FakeGitHubClient()
    store = InMemoryExternalStore()

    sync_github_readonly(client=client, owner=OWNER, repo=REPO, store=store)

    assert store.records["gh:repo:yoheinakajima/activegraph"]["name"] == "activegraph"
    assert store.records["gh:issue:yoheinakajima/activegraph#23"]["number"] == 23
    assert store.records["gh:pr:yoheinakajima/activegraph#24"]["number"] == 24
    assert store.records[
        "gh:check:yoheinakajima/activegraph#24:github-actions:ci/test:abc123"
    ]["conclusion"] == "success"
    assert client.write_calls == []


def test_repeated_sync_is_idempotent_for_github_objects(no_credentials_or_network: None) -> None:
    client = FakeGitHubClient()
    store = InMemoryExternalStore()

    first_summary = sync_github_readonly(client=client, owner=OWNER, repo=REPO, store=store)
    first_keys = sorted(store.records)
    second_summary = sync_github_readonly(client=client, owner=OWNER, repo=REPO, store=store)

    assert sorted(store.records) == first_keys
    assert len(keys_with_prefix(store, "gh:issue:")) == 1
    assert len(keys_with_prefix(store, "gh:pr:")) == 1
    assert len(keys_with_prefix(store, "gh:prdiff:")) == 1
    assert len(keys_with_prefix(store, "gh:check:")) == 1
    assert first_summary["issues_created"] == 1
    assert first_summary["pull_requests_created"] == 1
    assert first_summary["pr_diffs_created"] == 1
    assert first_summary["checks_created"] == 1
    assert second_summary["issues_created"] == 0
    assert second_summary["issues_updated_or_patched"] == 1
    assert second_summary["pull_requests_created"] == 0
    assert second_summary["pull_requests_updated_or_patched"] == 1
    assert second_summary["pr_diffs_created"] == 0
    assert second_summary["checks_created"] == 0
    assert second_summary["checks_updated_or_patched"] == 1
    assert client.write_calls == []


def test_changed_pr_head_sha_creates_new_diff_but_not_new_pull_request(
    no_credentials_or_network: None,
) -> None:
    client = FakeGitHubClient()
    store = InMemoryExternalStore()

    sync_github_readonly(client=client, owner=OWNER, repo=REPO, store=store)
    client.head_sha = "def456"
    changed_summary = sync_github_readonly(client=client, owner=OWNER, repo=REPO, store=store)

    assert keys_with_prefix(store, "gh:pr:") == ["gh:pr:yoheinakajima/activegraph#24"]
    assert keys_with_prefix(store, "gh:prdiff:") == [
        "gh:prdiff:yoheinakajima/activegraph#24:abc123",
        "gh:prdiff:yoheinakajima/activegraph#24:def456",
    ]
    assert keys_with_prefix(store, "gh:check:") == [
        "gh:check:yoheinakajima/activegraph#24:github-actions:ci/test:abc123",
        "gh:check:yoheinakajima/activegraph#24:github-actions:ci/test:def456",
    ]
    assert changed_summary["pull_requests_created"] == 0
    assert changed_summary["pull_requests_updated_or_patched"] == 1
    assert changed_summary["pr_diffs_created"] == 1
    assert changed_summary["checks_created"] == 1
    assert changed_summary["write_actions_attempted"] == 0
    assert changed_summary["github_write_count"] == 0
    assert client.write_calls == []
