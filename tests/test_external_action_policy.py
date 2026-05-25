from pathlib import Path
from activegraph_repo_manager.behaviors.apply_approved_actions import execute_external_action_proposal_dry_run
from activegraph_repo_manager.behaviors.propose_external_action import (
    proposal_from_planning_patch,
    proposal_from_review_finding,
)
from activegraph_repo_manager.policies import approve_external_action_proposal, reject_external_action_proposal


def _finding(action: str, blocking: bool = False) -> dict:
    return {
        "finding_id": "f-1",
        "pr_external_key": "gh:pr:activegraph/activegraph#77",
        "severity": "warning",
        "category": "docs",
        "blocking": blocking,
        "summary": "Need follow-up",
        "evidence_refs": [{"source": "pr_diff", "locator": "file:README.md"}],
        "confidence": 0.8,
        "requires_external_action": action,
    }


def test_review_finding_comment_produces_github_comment_proposal() -> None:
    proposal = proposal_from_review_finding(_finding("comment"))
    assert proposal is not None
    assert proposal["action_type"] == "github_comment"
    assert proposal["target_external_key"] == "gh:pr:activegraph/activegraph#77"
    assert proposal["status"] == "proposed"


def test_blocking_review_finding_request_changes_produces_proposal() -> None:
    proposal = proposal_from_review_finding(_finding("request_changes", blocking=True))
    assert proposal is not None
    assert proposal["action_type"] == "github_request_changes"
    assert proposal["status"] == "proposed"


def test_generated_proposal_has_required_fields() -> None:
    proposal = proposal_from_review_finding(_finding("comment"))
    assert proposal is not None
    for key in ["action_type", "target_external_key", "payload", "evidence_refs", "rationale", "confidence", "status"]:
        assert key in proposal


def test_payload_is_deterministic_across_runs() -> None:
    first = proposal_from_review_finding(_finding("comment"))
    second = proposal_from_review_finding(_finding("comment"))
    assert first == second


def test_rejected_proposal_does_not_execute_even_dry_run() -> None:
    proposal = reject_external_action_proposal(proposal_from_review_finding(_finding("comment")))
    result = execute_external_action_proposal_dry_run(proposal)
    assert result["executed"] is False
    assert result["reason"] == "proposal_not_approved"


def test_approved_proposal_produces_dry_run_only_result() -> None:
    proposal = approve_external_action_proposal(proposal_from_review_finding(_finding("comment")))
    result = execute_external_action_proposal_dry_run(proposal)
    assert result["executed"] is True
    assert result["dry_run"] is True


def test_dry_run_result_has_no_external_write_marker() -> None:
    proposal = approve_external_action_proposal(proposal_from_review_finding(_finding("comment")))
    result = execute_external_action_proposal_dry_run(proposal)
    assert result["no_external_write"] is True


def test_executor_has_no_github_or_filesystem_write_paths() -> None:
    proposal = approve_external_action_proposal(proposal_from_review_finding(_finding("comment")))
    result = execute_external_action_proposal_dry_run(proposal)
    assert result["no_external_write"] is True
    assert "api_call" not in str(result).lower()
    assert "write_file" not in str(result).lower()


def test_no_planning_item_mutation_introduced() -> None:
    planning_item = {"external_key": "planning:item:1", "status": "open"}
    proposal = approve_external_action_proposal(proposal_from_review_finding(_finding("comment")))
    _ = execute_external_action_proposal_dry_run(proposal)
    assert planning_item == {"external_key": "planning:item:1", "status": "open"}


def test_planning_patch_contract_followup_optional_scenario() -> None:
    planning_patch = {
        "proposal_id": "plan-1",
        "field": "docs",
        "to_value": "contract",
        "target_external_key": "planning:item:contract-followup",
        "evidence_refs": [{"source": "planning", "locator": "item:contract-followup"}],
        "rationale": "contract docs follow-up",
        "confidence": 0.7,
    }
    proposal = proposal_from_planning_patch(planning_patch)
    assert proposal is not None
    assert proposal["action_type"] == "open_contract_update_pr"



def test_proposed_but_not_approved_proposal_does_not_execute() -> None:
    proposal = proposal_from_review_finding(_finding("comment"))
    assert proposal is not None
    result = execute_external_action_proposal_dry_run(proposal)
    assert result["executed"] is False
    assert result["reason"] == "proposal_not_approved"
    assert result["proposal_status"] == "proposed"


def test_behavior_bodies_do_not_include_live_write_or_network_calls() -> None:
    apply_src = Path("activegraph_repo_manager/behaviors/apply_approved_actions.py").read_text(encoding="utf-8").lower()
    propose_src = Path("activegraph_repo_manager/behaviors/propose_external_action.py").read_text(encoding="utf-8").lower()
    combined = apply_src + "\n" + propose_src
    forbidden_tokens = [
        "requests.",
        "httpx.",
        "urllib",
        "socket",
        "github.client",
        "write_text(",
        "open(",
        "request_changes(",
        "approve_pr(",
        "create_issue(",
        "create_pr(",
    ]
    for token in forbidden_tokens:
        assert token not in combined
