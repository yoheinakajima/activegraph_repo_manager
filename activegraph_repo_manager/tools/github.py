"""Deterministic GitHub tool boundaries: read-only via injected clients, writes disabled."""

from __future__ import annotations

from typing import Any, Protocol


class GitHubReadClient(Protocol):
    def get_repository(self, owner: str, repo: str) -> dict[str, Any]: ...

    def list_open_issues(self, owner: str, repo: str) -> list[dict[str, Any]]: ...

    def get_issue(self, owner: str, repo: str, issue_number: int) -> dict[str, Any]: ...

    def list_open_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]: ...

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]: ...

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]: ...

    def get_pull_request_checks(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]: ...


def github_get_repository(*, client: GitHubReadClient, owner: str, repo: str) -> dict[str, Any]:
    return client.get_repository(owner, repo)


def github_list_open_issues(*, client: GitHubReadClient, owner: str, repo: str) -> list[dict[str, Any]]:
    return client.list_open_issues(owner, repo)


def github_get_issue(*, client: GitHubReadClient, owner: str, repo: str, issue_number: int) -> dict[str, Any]:
    return client.get_issue(owner, repo, issue_number)


def github_list_open_pull_requests(
    *, client: GitHubReadClient, owner: str, repo: str
) -> list[dict[str, Any]]:
    return client.list_open_pull_requests(owner, repo)


def github_get_pull_request(*, client: GitHubReadClient, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
    return client.get_pull_request(owner, repo, pr_number)


def github_get_pull_request_files(
    *, client: GitHubReadClient, owner: str, repo: str, pr_number: int
) -> list[dict[str, Any]]:
    return client.get_pull_request_files(owner, repo, pr_number)


def github_get_pull_request_checks(
    *, client: GitHubReadClient, owner: str, repo: str, pr_number: int
) -> list[dict[str, Any]]:
    return client.get_pull_request_checks(owner, repo, pr_number)


def _disabled_result(action_name: str, target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "executed": False,
        "result_status": "disabled",
        "reason": "live_write_disabled",
        "action": action_name,
        "target_external_key": target_external_key,
        "payload_keys": sorted(payload.keys()),
        "no_external_write": True,
    }


def github_post_comment(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("github_post_comment", target_external_key, payload)


def github_apply_label(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("github_apply_label", target_external_key, payload)


def github_request_changes(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("github_request_changes", target_external_key, payload)


def github_approve_pr(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("github_approve_pr", target_external_key, payload)


def github_open_issue(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("github_open_issue", target_external_key, payload)


def open_roadmap_update_pr(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("open_roadmap_update_pr", target_external_key, payload)


def open_contract_update_pr(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("open_contract_update_pr", target_external_key, payload)


tools = ()
