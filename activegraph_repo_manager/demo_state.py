"""Offline fixture seeding for the local repo-manager state store."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from activegraph_repo_manager.behaviors.classify_issue import classify_issue_from_recorded_output
from activegraph_repo_manager.behaviors.classify_pr import classify_pr_from_recorded_output
from activegraph_repo_manager.behaviors.contract_guard import run_contract_guard
from activegraph_repo_manager.behaviors.link_issue_to_planning import (
    link_issue_to_planning,
    link_pr_to_planning,
)
from activegraph_repo_manager.behaviors.propose_planning_patch import (
    propose_new_item_for_high_signal_issue,
)
from activegraph_repo_manager.behaviors.review_pr import review_pr_from_recorded_output
from activegraph_repo_manager.state import LocalStateStore
from activegraph_repo_manager.tools.demo import run_keyless_demo
from activegraph_repo_manager.tools.repo_index import (
    derive_repo_file_external_key,
    derive_symbol_external_key,
    derive_test_surface_external_key,
    infer_test_surfaces,
    parse_python_symbols,
)

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _slug(value: str) -> str:
    lowered = value.lower()
    chars = [char if char.isalnum() else "-" for char in lowered]
    return "-".join(part for part in "".join(chars).split("-") if part)


def seed_keyless_demo_state(store: LocalStateStore) -> dict[str, Any]:
    """Populate local state from deterministic offline fixtures and summaries."""

    repo_fixture = _load_fixture("repo_snapshot_minimal.json")
    repository = repo_fixture["repository"]
    repo_snapshot = repo_fixture["repo_snapshot"]
    issue = _load_fixture("issue_23_open_telemetry.json")["issue"]
    pr_bundle = _load_fixture("pr_24_falkordb_eventstore.json")
    pull_request = pr_bundle["pull_request"]
    check_run = pr_bundle["check_run"]
    pr_diff = _load_fixture("pr_diff_contract_sensitive.json")["pr_diff"]

    issue_llm = _load_fixture("llm_issue_classification.v1.json")
    pr_llm = _load_fixture("llm_pr_classification.v1.json")
    pr_review_llm = _load_fixture("llm_pr_review.v1.json")

    store.upsert_object("repository", repository)
    store.upsert_object("issue", issue)
    store.upsert_object("pull_request", pull_request)
    store.upsert_object("check_run", check_run)
    store.upsert_object("pr_diff", pr_diff)

    repository_external_key = repository["external_key"]
    repo_files = [dict(item) for item in repo_snapshot.get("files", [])]
    for repo_file in repo_files:
        path = str(PurePosixPath(repo_file["path"]))
        payload = {
            "external_key": derive_repo_file_external_key(repository_external_key, path),
            "source": "repo_fixture",
            "repository_external_key": repository_external_key,
            **repo_file,
            "path": path,
        }
        store.upsert_object("repo_file", payload)
        if path.endswith(".py"):
            fixture_source = f'def demo_symbol_{path.replace("/", "_").replace(".", "_")}():\n    return "ok"\n'
            for symbol in parse_python_symbols(fixture_source):
                symbol_payload = {
                    "external_key": derive_symbol_external_key(
                        repository_external_key,
                        path,
                        symbol.kind,
                        symbol.qualified_name,
                    ),
                    "source": "repo_fixture",
                    "repository_external_key": repository_external_key,
                    "file_path": path,
                    "name": symbol.name,
                    "kind": symbol.kind,
                    "qualified_name": symbol.qualified_name,
                    "line_start": symbol.line_start,
                    "line_end": symbol.line_end,
                    "public_api": symbol.public_api,
                }
                store.upsert_object("symbol", symbol_payload)

    for surface in infer_test_surfaces([item["path"] for item in repo_files]):
        external_key = derive_test_surface_external_key(
            repository_external_key,
            surface["test_file_path"],
            surface["likely_target"],
        )
        store.upsert_object(
            "test_surface",
            {
                "external_key": external_key,
                "source": "repo_fixture",
                "repository_external_key": repository_external_key,
                **surface,
            },
        )

    planning_items = [
        {
            "external_key": "planning:item:observability-gap",
            "title": "Close observability and adoption-surface instrumentation gap",
            "status": "planned",
            "priority": "high",
            "work_type": "observability",
        },
        {
            "external_key": "planning:item:store-backend-checkpointing",
            "title": "Store backend event checkpointing hardening",
            "status": "in_progress",
            "priority": "medium",
            "work_type": "store_backend",
        },
    ]
    for planning_item in planning_items:
        store.upsert_object("planning_item", planning_item)

    for relation in link_issue_to_planning(issue, planning_items):
        store.upsert_relation(relation["relation"], relation)
    for relation in link_pr_to_planning(pull_request, planning_items, [issue["external_key"]]):
        store.upsert_relation(relation["relation"], relation)

    issue_classification = classify_issue_from_recorded_output(issue, issue_llm)
    pr_classification = classify_pr_from_recorded_output(pull_request, pr_diff["files_changed"], pr_llm)
    review = review_pr_from_recorded_output(pull_request, pr_diff, pr_review_llm)
    for finding in review["findings"]:
        finding_id = finding.get("finding_id") or _slug(str(finding.get("title", "review-finding")))
        finding_payload = {
            "external_key": f"{pull_request['external_key']}:review_finding:{finding_id}",
            **finding,
        }
        store.upsert_object("review_finding", finding_payload)

    planning_proposal = propose_new_item_for_high_signal_issue(
        issue_external_key=issue["external_key"],
        issue_number=issue["number"],
        issue_title="Close observability and adoption-surface instrumentation gap",
    )
    store.upsert_object(
        "planning_patch_proposal",
        {"external_key": planning_proposal["proposal_id"], **planning_proposal},
    )

    demo_summary = run_keyless_demo()
    store.upsert_summary("keyless_demo", demo_summary)
    store.upsert_summary(
        "repo_manager_status",
        {
            "mode": "offline_keyless_demo",
            "source": "local_state",
            "repository_external_key": repository_external_key,
            "read_only": True,
            "external_write_performed": False,
            "github_write_count": 0,
            "live_llm_call_count": 0,
            "issue_classification_summary": issue_classification,
            "pr_classification_summary": pr_classification,
            "contract_guard_triggered": run_contract_guard(pr_diff)["triggered"],
            "object_counts": store.object_counts(),
        },
    )
    return {
        "state_seeded": True,
        "source": "offline_fixtures",
        "object_counts": store.object_counts(),
        "summary_keys": sorted(store.list_summaries()),
        "live_llm_call_count": 0,
        "external_write_performed": False,
    }
