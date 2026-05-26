from activegraph_repo_manager.behaviors.ingest_github import (
    InMemoryExternalStore,
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
from activegraph_repo_manager.tools import github as github_tools


class FakeGitHubClient:
    def __init__(self) -> None:
        self.write_calls: list[str] = []

    def get_repository(self, owner: str, repo: str) -> dict:
        return {"owner": {"login": owner}, "name": repo, "default_branch": "main", "private": False}

    def list_open_issues(self, owner: str, repo: str) -> list[dict]:
        return [self.get_issue(owner, repo, 23)]

    def get_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        return {"number": issue_number, "title": "Issue title", "state": "open", "labels": [{"name": "bug"}]}

    def list_open_pull_requests(self, owner: str, repo: str) -> list[dict]:
        return [self.get_pull_request(owner, repo, 24)]

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        return {
            "number": pr_number,
            "title": "PR title",
            "state": "open",
            "base": {"ref": "main"},
            "head": {"ref": "feature", "sha": "abc123"},
        }

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        return [{"filename": "a.py", "status": "modified", "additions": 2, "deletions": 1}]

    def get_pull_request_checks(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        return [{"name": "ci/test", "status": "completed", "conclusion": "success", "app": {"slug": "github-actions"}}]


def test_injected_fake_client_readonly_functions_work() -> None:
    client = FakeGitHubClient()
    owner, repo = "yoheinakajima", "activegraph"
    assert github_tools.github_get_repository(client=client, owner=owner, repo=repo)["name"] == repo
    assert github_tools.github_list_open_issues(client=client, owner=owner, repo=repo)[0]["number"] == 23
    assert github_tools.github_get_issue(client=client, owner=owner, repo=repo, issue_number=23)["state"] == "open"
    assert github_tools.github_list_open_pull_requests(client=client, owner=owner, repo=repo)[0]["number"] == 24
    assert github_tools.github_get_pull_request(client=client, owner=owner, repo=repo, pr_number=24)["head"]["sha"] == "abc123"
    assert len(github_tools.github_get_pull_request_files(client=client, owner=owner, repo=repo, pr_number=24)) == 1
    assert len(github_tools.github_get_pull_request_checks(client=client, owner=owner, repo=repo, pr_number=24)) == 1


def test_normalization_external_keys_and_determinism() -> None:
    owner, repo = "yoheinakajima", "activegraph"
    repo_payload = normalize_github_repository({"owner": {"login": owner}, "name": repo, "default_branch": "main"})
    issue_payload = normalize_github_issue({"number": 23, "title": "x", "state": "open", "labels": []}, owner=owner, repo=repo)
    pr_payload = normalize_github_pull_request({"number": 24, "title": "y", "state": "open", "base": {"ref": "main"}, "head": {"ref": "f", "sha": "abc123"}}, owner=owner, repo=repo)
    files_payload = normalize_github_pr_files([{"filename": "f.py", "status": "modified", "additions": 1, "deletions": 0}], owner=owner, repo=repo, pr_number=24, head_sha="abc123")
    check_payload = normalize_github_check_run({"name": "ci/test", "status": "completed", "app": {"slug": "github-actions"}}, owner=owner, repo=repo, pr_number=24, head_sha="abc123")

    assert repo_payload["external_key"] == "gh:repo:yoheinakajima/activegraph"
    assert issue_payload["external_key"] == "gh:issue:yoheinakajima/activegraph#23"
    assert pr_payload["external_key"] == "gh:pr:yoheinakajima/activegraph#24"
    assert files_payload["external_key"] == "gh:prdiff:yoheinakajima/activegraph#24:abc123"
    assert check_payload["external_key"] == "gh:check:yoheinakajima/activegraph#24:github-actions:ci/test:abc123"


def test_normalized_payloads_reuse_idempotent_ingest_helpers() -> None:
    owner, repo = "yoheinakajima", "activegraph"
    store = InMemoryExternalStore()
    repo_payload = normalize_github_repository({"owner": {"login": owner}, "name": repo, "default_branch": "main"})
    issue_payload = normalize_github_issue({"number": 23, "title": "x", "state": "open", "labels": []}, owner=owner, repo=repo)
    pr_payload = normalize_github_pull_request({"number": 24, "title": "y", "state": "open", "base": {"ref": "main"}, "head": {"ref": "f", "sha": "abc123"}}, owner=owner, repo=repo)
    diff_payload = normalize_github_pr_files([], owner=owner, repo=repo, pr_number=24, head_sha="abc123")
    check_payload = normalize_github_check_run({"name": "ci/test", "status": "completed", "app": {"slug": "github-actions"}}, owner=owner, repo=repo, pr_number=24, head_sha="abc123")

    assert ingest_repository(store, repo_payload).action == "created"
    assert ingest_repository(store, repo_payload).action == "patched"
    assert ingest_issue(store, issue_payload).action == "created"
    assert ingest_issue(store, issue_payload).action == "patched"
    assert ingest_pull_request(store, pr_payload).action == "created"
    assert ingest_pull_request(store, pr_payload).action == "patched"
    assert ingest_pr_diff(store, diff_payload).action == "created"
    assert ingest_pr_diff(store, diff_payload).action == "patched"
    assert ingest_check_run(store, check_payload).action == "created"
    assert ingest_check_run(store, check_payload).action == "patched"


def test_readonly_functions_do_not_call_write_methods_and_write_stubs_disabled() -> None:
    client = FakeGitHubClient()
    _ = github_tools.github_get_repository(client=client, owner="yoheinakajima", repo="activegraph")
    assert client.write_calls == []

    result = github_tools.github_post_comment("gh:pr:1", {"body": "x"})
    assert result["executed"] is False
    assert result["reason"] == "live_write_disabled"
