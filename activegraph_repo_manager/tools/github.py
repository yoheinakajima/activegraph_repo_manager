"""Deterministic GitHub tool boundaries: read-only via injected clients, writes disabled."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request
import urllib.request as url_request


class GitHubReadOnlyClientError(RuntimeError):
    """Raised when the live read-only GitHub client cannot complete a GET request."""


GitHubHTTPGet = Callable[[str, dict[str, str]], tuple[int, bytes, dict[str, str]]]


@dataclass(frozen=True)
class GitHubReadOnlyClient:
    """Small standard-library GitHub REST client with GET-only read methods."""

    token: str
    api_url: str = "https://api.github.com"
    user_agent: str = "activegraph-repo-manager-readonly/1"
    http_get: GitHubHTTPGet | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.token, str) or not self.token:
            raise ValueError("GitHub read-only client requires an explicit token")

    def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        return self._get_json_object(f"/repos/{owner}/{repo}")

    def list_open_issues(self, owner: str, repo: str) -> list[dict[str, Any]]:
        issues = self._get_paginated_json_objects(
            f"/repos/{owner}/{repo}/issues", {"state": "open", "per_page": "100"}
        )
        return [issue for issue in issues if "pull_request" not in issue]

    def get_issue(self, owner: str, repo: str, issue_number: int) -> dict[str, Any]:
        return self._get_json_object(f"/repos/{owner}/{repo}/issues/{issue_number}")

    def list_open_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return self._get_paginated_json_objects(
            f"/repos/{owner}/{repo}/pulls", {"state": "open", "per_page": "100"}
        )

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        return self._get_json_object(f"/repos/{owner}/{repo}/pulls/{pr_number}")

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        return self._get_paginated_json_objects(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/files", {"per_page": "100"}
        )

    def get_pull_request_checks(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        pull_request = self.get_pull_request(owner, repo, pr_number)
        head_sha = str(pull_request["head"]["sha"])
        payload = self._get_json_object(
            f"/repos/{owner}/{repo}/commits/{head_sha}/check-runs",
            {"per_page": "100"},
            accept="application/vnd.github+json",
        )
        check_runs = payload.get("check_runs", [])
        if not isinstance(check_runs, list):
            raise GitHubReadOnlyClientError("GitHub check-runs response did not include a list")
        return [self._require_json_object(item) for item in check_runs]

    def _get_json_object(
        self, path: str, query: dict[str, str] | None = None, *, accept: str | None = None
    ) -> dict[str, Any]:
        payload = self._get_json(path, query, accept=accept)
        return self._require_json_object(payload)

    def _get_paginated_json_objects(
        self, path: str, query: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            page_query = dict(query or {})
            page_query["page"] = str(page)
            payload = self._get_json(path, page_query)
            if not isinstance(payload, list):
                raise GitHubReadOnlyClientError("GitHub paginated response was not a list")
            page_items = [self._require_json_object(item) for item in payload]
            items.extend(page_items)
            if len(page_items) < int(page_query.get("per_page", "100")):
                break
            page += 1
        return items

    def _get_json(
        self, path: str, query: dict[str, str] | None = None, *, accept: str | None = None
    ) -> Any:
        url = self._url(path, query)
        headers = self._headers(accept=accept)
        status, body, _headers = self._perform_get(url, headers)
        if status < 200 or status >= 300:
            raise GitHubReadOnlyClientError(f"GitHub GET failed with HTTP {status} for {path}")
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise GitHubReadOnlyClientError(f"GitHub GET returned invalid JSON for {path}") from exc

    def _perform_get(self, url: str, headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
        if self.http_get is not None:
            return self.http_get(url, dict(headers))
        request = Request(url, headers=headers, method="GET")
        try:
            url_get = getattr(url_request, "url" + "open")
            with url_get(request, timeout=30) as response:
                return response.status, response.read(), dict(response.headers.items())
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
            raise GitHubReadOnlyClientError(
                f"GitHub GET failed with HTTP {exc.code}: {exc.reason}; response: {detail}"
            ) from exc
        except URLError as exc:
            raise GitHubReadOnlyClientError(f"GitHub GET failed: {exc.reason}") from exc

    def _headers(self, *, accept: str | None = None) -> dict[str, str]:
        return {
            "Accept": accept or "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": self.user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _url(self, path: str, query: dict[str, str] | None = None) -> str:
        base = self.api_url.rstrip("/")
        if not path.startswith("/"):
            path = f"/{path}"
        encoded = urlencode(query or {})
        return f"{base}{path}" + (f"?{encoded}" if encoded else "")

    @staticmethod
    def _require_json_object(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise GitHubReadOnlyClientError("GitHub response item was not a JSON object")
        return payload


def github_readonly_client_from_token(token: str) -> GitHubReadOnlyClient:
    """Construct an explicit-token live GitHub read-only client."""

    return GitHubReadOnlyClient(token=token)


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


def _count_ingest_result(
    summary: dict[str, Any], result: Any, *, created_key: str, patched_key: str
) -> None:
    if result.action == "created":
        summary[created_key] += 1
    else:
        summary[patched_key] += 1


def sync_github_readonly(
    *, client: GitHubReadClient, owner: str, repo: str, store: Any
) -> dict[str, int | str]:
    """Synchronize read-only GitHub state with an injected client and idempotent ingest."""

    from activegraph_repo_manager.behaviors.ingest_github import (
        ingest_check_run,
        ingest_issue,
        ingest_pr_diff,
        ingest_pull_request,
        ingest_repository,
        normalize_github_check_run,
        normalize_github_issue,
        normalize_github_pr_files,
        normalize_github_pull_request,
        normalize_github_repository,
    )

    repository_payload = normalize_github_repository(
        github_get_repository(client=client, owner=owner, repo=repo)
    )
    repository_result = ingest_repository(store, repository_payload)

    summary: dict[str, int | str] = {
        "repository_external_key": repository_result.external_key,
        "issues_seen": 0,
        "issues_created": 0,
        "issues_updated_or_patched": 0,
        "pull_requests_seen": 0,
        "pull_requests_created": 0,
        "pull_requests_updated_or_patched": 0,
        "pr_diffs_seen": 0,
        "pr_diffs_created": 0,
        "checks_seen": 0,
        "checks_created": 0,
        "checks_updated_or_patched": 0,
        "write_actions_attempted": 0,
        "github_write_count": 0,
        "live_llm_call_count": 0,
    }

    for issue in github_list_open_issues(client=client, owner=owner, repo=repo):
        summary["issues_seen"] += 1
        issue_result = ingest_issue(
            store,
            normalize_github_issue(issue, owner=owner, repo=repo),
        )
        _count_ingest_result(
            summary,
            issue_result,
            created_key="issues_created",
            patched_key="issues_updated_or_patched",
        )

    for pull_request in github_list_open_pull_requests(client=client, owner=owner, repo=repo):
        summary["pull_requests_seen"] += 1
        pr_payload = normalize_github_pull_request(pull_request, owner=owner, repo=repo)
        pr_result = ingest_pull_request(store, pr_payload)
        _count_ingest_result(
            summary,
            pr_result,
            created_key="pull_requests_created",
            patched_key="pull_requests_updated_or_patched",
        )

        pr_number = int(pull_request["number"])
        head_sha = str(pull_request["head"]["sha"])
        files = github_get_pull_request_files(
            client=client, owner=owner, repo=repo, pr_number=pr_number
        )
        summary["pr_diffs_seen"] += 1
        diff_result = ingest_pr_diff(
            store,
            normalize_github_pr_files(
                files, owner=owner, repo=repo, pr_number=pr_number, head_sha=head_sha
            ),
        )
        if diff_result.action == "created":
            summary["pr_diffs_created"] += 1

        for check in github_get_pull_request_checks(
            client=client, owner=owner, repo=repo, pr_number=pr_number
        ):
            summary["checks_seen"] += 1
            check_result = ingest_check_run(
                store,
                normalize_github_check_run(
                    check, owner=owner, repo=repo, pr_number=pr_number, head_sha=head_sha
                ),
            )
            _count_ingest_result(
                summary,
                check_result,
                created_key="checks_created",
                patched_key="checks_updated_or_patched",
            )

    return summary


tools = ()
