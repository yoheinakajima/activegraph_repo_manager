from pathlib import Path

from activegraph_repo_manager.behaviors.apply_approved_actions import execute_external_action_proposal_dry_run
from activegraph_repo_manager.policies import evaluate_external_action_execution_guard
from activegraph_repo_manager.tools import github as github_tools


def _approved_proposal() -> dict:
    return {
        "action_type": "github_comment",
        "target_external_key": "gh:pr:activegraph/activegraph#77",
        "payload": {"body": "Looks good"},
        "evidence_refs": [{"source": "pr_diff", "locator": "README.md"}],
        "status": "approved",
    }


def test_default_settings_disable_live_write_execution() -> None:
    proposal = _approved_proposal()
    guard = evaluate_external_action_execution_guard(
        proposal,
        enable_external_writes=False,
        require_approval_for_external_actions=True,
        dry_run_external_actions=False,
    )
    assert guard["allowed"] is False
    assert guard["reason"] == "external_writes_disabled"


def test_github_write_stubs_are_deterministic_and_disabled() -> None:
    result = github_tools.github_post_comment("gh:pr:1", {"body": "x"})
    assert result["executed"] is False
    assert result["reason"] == "live_write_disabled"
    assert result["no_external_write"] is True


def test_missing_approval_prevents_execution() -> None:
    proposal = _approved_proposal()
    proposal.pop("status")
    result = execute_external_action_proposal_dry_run(proposal)
    assert result["executed"] is False
    assert result["reason"] == "proposal_not_approved"


def test_rejected_proposal_prevents_execution() -> None:
    proposal = _approved_proposal()
    proposal["status"] = "rejected"
    result = execute_external_action_proposal_dry_run(proposal)
    assert result["executed"] is False
    assert result["reason"] == "proposal_not_approved"


def test_proposed_but_not_approved_prevents_execution() -> None:
    proposal = _approved_proposal()
    proposal["status"] = "proposed"
    result = execute_external_action_proposal_dry_run(proposal)
    assert result["executed"] is False
    assert result["reason"] == "proposal_not_approved"


def test_approved_proposal_still_dry_runs_by_default() -> None:
    result = execute_external_action_proposal_dry_run(_approved_proposal())
    assert result["executed"] is True
    assert result["dry_run"] is True
    assert result["no_external_write"] is True


def test_enabled_external_writes_with_dry_run_true_does_not_live_execute() -> None:
    result = execute_external_action_proposal_dry_run(
        _approved_proposal(), enable_external_writes=True, dry_run_external_actions=True
    )
    assert result["executed"] is True
    assert result["dry_run"] is True
    assert result["no_external_write"] is True


def test_dry_run_disabled_returns_not_implemented_boundary() -> None:
    result = execute_external_action_proposal_dry_run(
        _approved_proposal(), enable_external_writes=True, dry_run_external_actions=False
    )
    assert result["executed"] is False
    assert result["result_status"] == "live_write_not_implemented"
    assert result["no_external_write"] is True


def test_no_credentials_read_no_github_client_and_no_filesystem_write_paths() -> None:
    source = Path("activegraph_repo_manager/tools/github.py").read_text(encoding="utf-8").lower()
    forbidden_tokens = [
        "os.environ",
        "github.client",
        "github(" ,
        "requests.",
        "httpx.",
        "write_text(",
        "open(",
        "subprocess",
    ]
    for token in forbidden_tokens:
        assert token not in source
