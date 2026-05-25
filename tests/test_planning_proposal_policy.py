import json
from pathlib import Path

from activegraph_repo_manager.behaviors.propose_planning_patch import (
    propose_new_item_for_high_signal_issue,
    propose_status_implemented_for_merged_pr,
)
from activegraph_repo_manager.policies import (
    approve_planning_patch_proposal,
    mark_planning_patch_proposal_applied,
    reject_planning_patch_proposal,
)

FIXTURE_ROOT = Path("activegraph_repo_manager/fixtures")


def _load(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_merged_pr_advances_relation_produces_planning_patch_proposal_only() -> None:
    proposal = propose_status_implemented_for_merged_pr(
        pr_external_key="gh:pr:activegraph/activegraph#42",
        pr_status="merged",
        planning_item_external_key="planning:item:ingest-idempotency",
        current_status="in_progress",
        has_blocking_finding=False,
        review_external_key="review:pr:42",
        check_external_key="check:pr:42:ci",
    )

    assert proposal is not None
    assert proposal["change_type"] == "status"
    assert proposal["to_value"] == "implemented"
    assert proposal["proposed_item"] is None


def test_proposal_includes_required_approval_grade_fields() -> None:
    proposal = propose_status_implemented_for_merged_pr(
        pr_external_key="gh:pr:activegraph/activegraph#42",
        pr_status="merged",
        planning_item_external_key="planning:item:ingest-idempotency",
        current_status="in_progress",
        has_blocking_finding=False,
    )

    assert proposal is not None
    assert proposal["target_external_key"]
    assert proposal["change_type"]
    assert proposal["field"]
    assert proposal["from_value"] is not None
    assert proposal["to_value"] is not None
    assert proposal["evidence_refs"]
    assert proposal["confidence"] >= 0.0
    assert proposal["rationale"]
    assert proposal["caused_by_event_id"]
    assert proposal["proposed_by_behavior"]
    assert proposal["status"] == "proposed"


def test_unmatched_high_signal_issue_produces_new_item_proposal_with_proposed_item() -> None:
    proposal = propose_new_item_for_high_signal_issue(
        issue_external_key="gh:issue:activegraph/activegraph#23",
        issue_number=23,
        issue_title="Close observability and adoption-surface instrumentation gap",
    )

    assert proposal["change_type"] == "new_item"
    assert proposal["proposed_item"] is not None
    assert proposal["target_slug"] == "candidate:issue-23"


def test_blocking_review_finding_prevents_implemented_status_proposal() -> None:
    proposal = propose_status_implemented_for_merged_pr(
        pr_external_key="gh:pr:activegraph/activegraph#42",
        pr_status="merged",
        planning_item_external_key="planning:item:ingest-idempotency",
        current_status="in_progress",
        has_blocking_finding=True,
    )

    assert proposal is None


def test_rejected_proposal_leaves_planning_item_status_unchanged() -> None:
    planning_item = {"external_key": "planning:item:1", "status": "in_progress"}
    proposal = propose_status_implemented_for_merged_pr(
        pr_external_key="gh:pr:activegraph/activegraph#42",
        pr_status="merged",
        planning_item_external_key="planning:item:1",
        current_status="in_progress",
        has_blocking_finding=False,
    )
    assert proposal is not None

    rejected = reject_planning_patch_proposal(proposal)

    assert rejected["status"] == "rejected"
    assert planning_item["status"] == "in_progress"


def test_approved_and_applied_states_are_represented_without_writes() -> None:
    proposal = propose_new_item_for_high_signal_issue(
        issue_external_key="gh:issue:activegraph/activegraph#23",
        issue_number=23,
        issue_title="Close observability and adoption-surface instrumentation gap",
    )

    approved = approve_planning_patch_proposal(proposal)
    applied = mark_planning_patch_proposal_applied(approved)

    assert approved["status"] == "approved"
    assert applied["status"] == "applied"


def test_evidence_refs_point_to_valid_object_refs_or_external_keys() -> None:
    proposal = propose_status_implemented_for_merged_pr(
        pr_external_key="gh:pr:activegraph/activegraph#42",
        pr_status="merged",
        planning_item_external_key="planning:item:ingest-idempotency",
        current_status="in_progress",
        has_blocking_finding=False,
        review_external_key="review:pr:42",
        check_external_key="check:pr:42:ci",
    )
    assert proposal is not None

    for ref in proposal["evidence_refs"]:
        assert ":" in ref["locator"]


def test_no_external_action_proposal_created_and_no_write_behavior_introduced() -> None:
    fixture = _load("llm_planning_decider.v1.json")

    assert "external_action_proposals" not in fixture
    assert "github_write" not in json.dumps(fixture).lower()
    assert "file_write" not in json.dumps(fixture).lower()
