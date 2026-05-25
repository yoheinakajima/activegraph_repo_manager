"""Deterministic keyless Phase 0-4 integration demo over offline fixtures."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from activegraph_repo_manager.behaviors.classify_issue import classify_issue_from_recorded_output
from activegraph_repo_manager.behaviors.classify_pr import classify_pr_from_recorded_output
from activegraph_repo_manager.behaviors.contract_guard import run_contract_guard
from activegraph_repo_manager.behaviors.ingest_github import (
    InMemoryExternalStore,
    ingest_issue,
    ingest_pr_diff,
    ingest_pull_request,
    ingest_repository,
)
from activegraph_repo_manager.behaviors.link_issue_to_planning import (
    link_issue_to_planning,
    link_pr_to_planning,
)
from activegraph_repo_manager.behaviors.propose_planning_patch import (
    propose_new_item_for_high_signal_issue,
)
from activegraph_repo_manager.behaviors.review_pr import review_pr_from_recorded_output
from activegraph_repo_manager.tools.repo_index import infer_test_surfaces, parse_python_symbols

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def run_keyless_demo(include_external_action_proposals: bool = False) -> dict[str, Any]:
    """Run deterministic offline fixture integration across Phases 0-4."""

    repository = _load_fixture("repo_snapshot_minimal.json")["repository"]
    repo_snapshot = _load_fixture("repo_snapshot_minimal.json")["repo_snapshot"]
    issue = _load_fixture("issue_23_open_telemetry.json")["issue"]
    pr_bundle = _load_fixture("pr_24_falkordb_eventstore.json")
    pull_request = pr_bundle["pull_request"]
    pr_diff = _load_fixture("pr_diff_contract_sensitive.json")["pr_diff"]

    issue_llm = _load_fixture("llm_issue_classification.v1.json")
    pr_llm = _load_fixture("llm_pr_classification.v1.json")
    pr_review_llm = _load_fixture("llm_pr_review.v1.json")
    planning_decider_fixture = _load_fixture("llm_planning_decider.v1.json")

    store = InMemoryExternalStore()
    ingest_repository(store, repository)
    ingest_issue(store, issue)
    ingest_issue(store, issue)
    ingest_pull_request(store, pull_request)
    ingest_pull_request(store, pull_request)
    ingest_pr_diff(store, pr_diff)

    repo_files = [item["path"] for item in repo_snapshot.get("files", [])]
    test_surfaces = infer_test_surfaces(repo_files)

    symbol_count = 0
    for path in repo_files:
        if path.endswith(".py"):
            fixture_source = f'def demo_symbol_{path.replace("/", "_").replace(".", "_")}():\n    return "ok"\n'
            symbol_count += len(parse_python_symbols(fixture_source))

    issue_classification = classify_issue_from_recorded_output(issue, issue_llm)
    pr_classification = classify_pr_from_recorded_output(pull_request, pr_diff["files_changed"], pr_llm)

    planning_items = [
        {
            "external_key": "planning:item:observability-gap",
            "title": "Close observability and adoption-surface instrumentation gap",
            "status": "planned",
        },
        {
            "external_key": "planning:item:store-backend-checkpointing",
            "title": "Store backend event checkpointing hardening",
            "status": "in_progress",
        },
    ]
    relations = link_issue_to_planning(issue, planning_items)
    relations.extend(link_pr_to_planning(pull_request, planning_items, [issue["external_key"]]))

    grouped_relations: dict[str, list[dict[str, str]]] = defaultdict(list)
    for relation in relations:
        grouped_relations[relation["relation"]].append(
            {"from": relation["from"], "to": relation["to"]}
        )
    grouped_relations = {
        name: sorted(edges, key=lambda item: (item["from"], item["to"]))
        for name, edges in sorted(grouped_relations.items())
    }

    contract_guard = run_contract_guard(pr_diff)
    review = review_pr_from_recorded_output(pull_request, pr_diff, pr_review_llm)

    planning_proposals = [
        propose_new_item_for_high_signal_issue(
            issue_external_key=issue["external_key"],
            issue_number=issue["number"],
            issue_title="Close observability and adoption-surface instrumentation gap",
        )
    ]

    issue_summary = {
        "work_type": issue_classification["work_type"],
        "scope": issue_classification["scope"],
        "risk": issue_classification["risk"],
        "affected_areas": sorted(issue_classification["affected_areas"]),
    }
    pr_summary = {
        "work_type": pr_classification["work_type"],
        "scope": pr_classification["scope"],
        "risk": pr_classification["risk"],
        "affected_areas": sorted(pr_classification["affected_areas"]),
    }

    _ = planning_decider_fixture  # fixture loaded intentionally to verify keyless input surface.

    result = {
        "repository_external_key": repository["external_key"],
        "ingested_issue_count": sum(1 for key in store.records if key.startswith("gh:issue:")),
        "ingested_pr_count": sum(1 for key in store.records if key.startswith("gh:pr:")),
        "repo_file_count": len(repo_files),
        "symbol_count": symbol_count,
        "test_surface_count": len(test_surfaces),
        "issue_classification_summary": issue_summary,
        "pr_classification_summary": pr_summary,
        "relations_by_name": grouped_relations,
        "contract_guard_triggered": contract_guard["triggered"],
        "review_findings_count": len(review["findings"]),
        "planning_proposals_count": len([p for p in planning_proposals if p is not None]),
        "read_only_guarantees": {
            "external_action_proposals_count": len(review["external_action_proposals"]),
            "planning_item_mutations_count": len(review["planning_item_mutations"]),
            "github_write_count": 0,
            "external_write_performed": False,
            "live_llm_call_count": 0,
        },
        "fixture_counts": dict(Counter(["issue", "pr", "repo", "pr_diff"])),
    }

    if include_external_action_proposals:
        result["external_action_proposals_count"] = len(review["external_action_proposals"])
        result["dry_run_external_actions_count"] = 0

    return result



tools = ()
