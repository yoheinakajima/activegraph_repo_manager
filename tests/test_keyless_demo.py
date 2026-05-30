import os
import socket

import pytest

from activegraph_repo_manager.tools.demo import run_keyless_demo


class FakeGitHubReadOnlyClient:
    def __init__(self) -> None:
        self.read_calls: list[str] = []
        self.write_calls: list[str] = []

    def get_repository(self, owner: str, repo: str) -> dict:
        self.read_calls.append("get_repository")
        return {
            "owner": {"login": owner},
            "name": repo,
            "default_branch": "main",
            "private": False,
        }

    def list_open_issues(self, owner: str, repo: str) -> list[dict]:
        self.read_calls.append("list_open_issues")
        return [
            {
                "number": 23,
                "title": "Add OpenTelemetry spans for ingest pipeline",
                "state": "open",
                "labels": [{"name": "telemetry"}, {"name": "enhancement"}],
            }
        ]

    def get_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        self.read_calls.append("get_issue")
        return {
            "number": issue_number,
            "title": "Add OpenTelemetry spans for ingest pipeline",
            "state": "open",
            "labels": [{"name": "telemetry"}, {"name": "enhancement"}],
        }

    def list_open_pull_requests(self, owner: str, repo: str) -> list[dict]:
        self.read_calls.append("list_open_pull_requests")
        return [self.get_pull_request(owner, repo, 24)]

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        self.read_calls.append("get_pull_request")
        return {
            "number": pr_number,
            "title": "Persist FalkorDB event store checkpoints",
            "state": "open",
            "base": {"ref": "main"},
            "head": {
                "ref": "feat/falkordb-eventstore",
                "sha": "a1b2c3d4e5f60123456789abcdef0123456789ab",
            },
        }

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        self.read_calls.append("get_pull_request_files")
        return [
            {
                "filename": "activegraph/store/event_store.py",
                "status": "modified",
                "additions": 42,
                "deletions": 7,
            }
        ]

    def get_pull_request_checks(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        self.read_calls.append("get_pull_request_checks")
        return [
            {
                "name": "ci/audit",
                "status": "completed",
                "conclusion": "success",
                "app": {"slug": "github-actions"},
            }
        ]

    def post_comment(self, *args: object, **kwargs: object) -> None:
        self.write_calls.append("post_comment")
        raise AssertionError("write method must not be called")

    def apply_label(self, *args: object, **kwargs: object) -> None:
        self.write_calls.append("apply_label")
        raise AssertionError("write method must not be called")

    def request_changes(self, *args: object, **kwargs: object) -> None:
        self.write_calls.append("request_changes")
        raise AssertionError("write method must not be called")

    def approve_pr(self, *args: object, **kwargs: object) -> None:
        self.write_calls.append("approve_pr")
        raise AssertionError("write method must not be called")

    def open_issue(self, *args: object, **kwargs: object) -> None:
        self.write_calls.append("open_issue")
        raise AssertionError("write method must not be called")

    def open_pull_request(self, *args: object, **kwargs: object) -> None:
        self.write_calls.append("open_pull_request")
        raise AssertionError("write method must not be called")


def test_demo_runs_without_github_credentials_or_live_llm_calls() -> None:
    summary = run_keyless_demo()
    assert summary["repository_external_key"] == "gh:repo:yoheinakajima/activegraph"
    assert summary["read_only_guarantees"]["live_llm_call_count"] == 0


def test_demo_output_is_deterministic_across_repeated_runs() -> None:
    first = run_keyless_demo()
    second = run_keyless_demo()
    assert first == second


def test_default_demo_output_is_fixture_only_without_github_readonly_sync() -> None:
    client = FakeGitHubReadOnlyClient()
    summary = run_keyless_demo(github_client=client)
    assert "github_readonly_sync" not in summary
    assert client.read_calls == []
    assert client.write_calls == []


def test_issue_fixture_appears_as_observability_adoption_surface_gap() -> None:
    summary = run_keyless_demo()
    issue_summary = summary["issue_classification_summary"]
    assert issue_summary["work_type"] == "observability"
    assert "operator_surface" in issue_summary["affected_areas"]


def test_pr_fixture_appears_as_store_backend_high_risk() -> None:
    summary = run_keyless_demo()
    pr_summary = summary["pr_classification_summary"]
    assert pr_summary["work_type"] == "store_backend"
    assert pr_summary["risk"] == "high"


def test_repo_grasp_summary_includes_files_symbols_and_test_surfaces() -> None:
    summary = run_keyless_demo()
    assert summary["repo_file_count"] > 0
    assert summary["symbol_count"] > 0
    assert summary["test_surface_count"] > 0


def test_contract_guard_triggered_for_contract_sensitive_diff_fixture() -> None:
    summary = run_keyless_demo()
    assert summary["contract_guard_triggered"] is True


def test_structured_review_findings_present() -> None:
    summary = run_keyless_demo()
    assert summary["review_findings_count"] >= 1


def test_planning_patch_proposal_present_for_fixture_scenario() -> None:
    summary = run_keyless_demo()
    assert summary["planning_proposals_count"] >= 1


def test_read_only_guarantee_counters_are_zero() -> None:
    summary = run_keyless_demo()
    guarantees = summary["read_only_guarantees"]
    assert guarantees["external_action_proposals_count"] == 0
    assert guarantees["planning_item_mutations_count"] == 0
    assert guarantees["github_write_count"] == 0
    assert guarantees["live_llm_call_count"] == 0
    assert guarantees["external_write_performed"] is False


def test_github_readonly_sync_requires_injected_fake_client() -> None:
    with pytest.raises(ValueError, match="requires an injected GitHub read client"):
        run_keyless_demo(include_github_readonly_sync=True)


def test_github_readonly_sync_summary_appears_only_when_enabled() -> None:
    default_summary = run_keyless_demo()
    assert "github_readonly_sync" not in default_summary

    sync_summary = run_keyless_demo(
        include_github_readonly_sync=True,
        github_client=FakeGitHubReadOnlyClient(),
    )
    assert "github_readonly_sync" in sync_summary


def test_github_readonly_sync_summary_counts_existing_repo_issue_pr_diff_and_check() -> None:
    client = FakeGitHubReadOnlyClient()
    summary = run_keyless_demo(include_github_readonly_sync=True, github_client=client)
    sync_summary = summary["github_readonly_sync"]

    assert sync_summary["repository_external_key"] == "gh:repo:yoheinakajima/activegraph"
    assert sync_summary["issues_seen"] == 1
    assert sync_summary["issues_created"] == 0
    assert sync_summary["issues_updated_or_patched"] == 1
    assert sync_summary["pull_requests_seen"] == 1
    assert sync_summary["pull_requests_created"] == 0
    assert sync_summary["pull_requests_updated_or_patched"] == 1
    assert sync_summary["pr_diffs_seen"] == 1
    assert sync_summary["pr_diffs_created"] == 0
    assert sync_summary["checks_seen"] == 1
    assert sync_summary["checks_created"] == 1
    assert sync_summary["checks_updated_or_patched"] == 0


def test_github_readonly_sync_keeps_write_and_live_counters_zero() -> None:
    client = FakeGitHubReadOnlyClient()
    summary = run_keyless_demo(include_github_readonly_sync=True, github_client=client)
    guarantees = summary["read_only_guarantees"]
    sync_summary = summary["github_readonly_sync"]

    assert guarantees["external_action_proposals_count"] == 0
    assert guarantees["planning_item_mutations_count"] == 0
    assert guarantees["github_write_count"] == 0
    assert guarantees["external_write_performed"] is False
    assert guarantees["live_llm_call_count"] == 0
    assert sync_summary["write_actions_attempted"] == 0
    assert sync_summary["github_write_count"] == 0
    assert sync_summary["live_llm_call_count"] == 0
    assert client.write_calls == []


def test_github_readonly_sync_reads_no_credentials_and_makes_no_network_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingEnviron(dict):
        def get(self, key: object, default: object | None = None) -> object | None:
            raise AssertionError(f"credential environment variable read attempted: {key}")

        def __getitem__(self, key: object) -> object:
            raise AssertionError(f"credential environment variable read attempted: {key}")

    def fail_getenv(name: str, default: object | None = None) -> object | None:
        raise AssertionError(f"credential environment variable read attempted: {name}")

    def fail_create_connection(*args: object, **kwargs: object) -> object:
        raise AssertionError("network call attempted")

    monkeypatch.setattr(os, "environ", FailingEnviron())
    monkeypatch.setattr(os, "getenv", fail_getenv)
    monkeypatch.setattr(socket, "create_connection", fail_create_connection)

    client = FakeGitHubReadOnlyClient()
    summary = run_keyless_demo(include_github_readonly_sync=True, github_client=client)

    assert summary["github_readonly_sync"]["github_write_count"] == 0
    assert client.write_calls == []


def test_optional_external_action_proposal_counters_are_available_without_writes() -> None:
    summary = run_keyless_demo(include_external_action_proposals=True)
    assert summary["external_action_proposals_count"] == 0
    assert summary["dry_run_external_actions_count"] == 0
    guarantees = summary["read_only_guarantees"]
    assert guarantees["github_write_count"] == 0
    assert guarantees["external_write_performed"] is False
    assert guarantees["live_llm_call_count"] == 0
