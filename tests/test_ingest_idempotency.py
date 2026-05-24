import json
from copy import deepcopy
from pathlib import Path

from activegraph_repo_manager.behaviors.ingest_github import (
    InMemoryExternalStore,
    ingest_check_run,
    ingest_issue,
    ingest_pr_diff,
    ingest_pull_request,
    ingest_repository,
)

FIXTURE_ROOT = Path("activegraph_repo_manager/fixtures")


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_ingest_same_issue_twice_patches_existing_object() -> None:
    store = InMemoryExternalStore()
    issue_payload = _load_fixture("issue_23_open_telemetry.json")["issue"]

    first = ingest_issue(store, issue_payload)
    second = ingest_issue(store, issue_payload)

    assert first.action == "created"
    assert second.action == "patched"
    assert len([k for k in store.records if k.startswith("gh:issue:")]) == 1


def test_ingest_edited_issue_patches_same_object() -> None:
    store = InMemoryExternalStore()
    base_issue = _load_fixture("issue_23_open_telemetry.json")["issue"]
    edited_issue = deepcopy(base_issue)
    edited_issue["title"] = "Add OTEL spans for ingest + replay pipeline"
    edited_issue["external_metadata"]["labels"] = ["telemetry", "infra"]

    ingest_issue(store, base_issue)
    result = ingest_issue(store, edited_issue)

    assert result.action == "patched"
    assert len([k for k in store.records if k.startswith("gh:issue:")]) == 1
    assert store.records[base_issue["external_key"]]["title"] == edited_issue["title"]


def test_webhook_redelivery_does_not_create_duplicate_pr() -> None:
    store = InMemoryExternalStore()
    pr_payload = _load_fixture("pr_24_falkordb_eventstore.json")["pull_request"]

    first = ingest_pull_request(store, pr_payload)
    second = ingest_pull_request(store, pr_payload)

    assert first.action == "created"
    assert second.action == "patched"
    assert len([k for k in store.records if k.startswith("gh:pr:")]) == 1


def test_changed_pr_sha_creates_new_prdiff_not_new_pr() -> None:
    store = InMemoryExternalStore()
    repo_payload = _load_fixture("repo_snapshot_minimal.json")["repository"]
    pr_payload = _load_fixture("pr_24_falkordb_eventstore.json")["pull_request"]
    diff_payload = _load_fixture("pr_diff_contract_sensitive.json")["pr_diff"]

    ingest_repository(store, repo_payload)
    ingest_pull_request(store, pr_payload)
    ingest_pr_diff(store, diff_payload)

    updated_pr = deepcopy(pr_payload)
    new_sha = "bbbbc3d4e5f60123456789abcdef0123456789cd"
    updated_pr["external_metadata"]["head_sha"] = new_sha
    ingest_pull_request(store, updated_pr)

    updated_diff = deepcopy(diff_payload)
    updated_diff["external_key"] = f"gh:prdiff:yoheinakajima/activegraph#24:{new_sha}"
    updated_diff["external_metadata"]["commit_external_key"] = (
        f"gh:commit:yoheinakajima/activegraph@{new_sha}"
    )
    ingest_pr_diff(store, updated_diff)

    assert len([k for k in store.records if k.startswith("gh:pr:")]) == 1
    assert len([k for k in store.records if k.startswith("gh:prdiff:")]) == 2


def test_reingest_same_check_run_patches_existing_check_run() -> None:
    store = InMemoryExternalStore()
    check_payload = _load_fixture("pr_24_falkordb_eventstore.json")["check_run"]

    ingest_check_run(store, check_payload)
    patched = deepcopy(check_payload)
    patched["conclusion"] = "neutral"
    result = ingest_check_run(store, patched)

    assert result.action == "patched"
    assert len([k for k in store.records if k.startswith("gh:check:")]) == 1
    assert store.records[check_payload["external_key"]]["conclusion"] == "neutral"


def test_fixture_files_are_valid_and_include_external_keys() -> None:
    repo = _load_fixture("repo_snapshot_minimal.json")["repository"]
    issue = _load_fixture("issue_23_open_telemetry.json")["issue"]
    pr_fixture = _load_fixture("pr_24_falkordb_eventstore.json")
    pr = pr_fixture["pull_request"]
    check_run = pr_fixture["check_run"]
    pr_diff = _load_fixture("pr_diff_contract_sensitive.json")["pr_diff"]

    assert repo["external_key"] == "gh:repo:yoheinakajima/activegraph"
    assert issue["external_key"] == "gh:issue:yoheinakajima/activegraph#23"
    assert pr["external_key"] == "gh:pr:yoheinakajima/activegraph#24"
    assert pr_diff["external_metadata"]["commit_external_key"].startswith(
        "gh:commit:yoheinakajima/activegraph@"
    )
    assert check_run["external_key"].startswith(
        "gh:check:yoheinakajima/activegraph#24:"
    )
