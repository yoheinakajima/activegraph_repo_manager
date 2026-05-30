"""Approval policy helpers for deterministic, offline proposal lifecycles."""

from dataclasses import dataclass
from typing import Any


ALLOWED_EXTERNAL_ACTION_TYPES = frozenset(
    {
        "github_comment",
        "github_label",
        "github_request_changes",
        "github_approve_pr",
        "github_open_issue",
        "open_roadmap_update_pr",
        "open_contract_update_pr",
    }
)


@dataclass(frozen=True)
class PlanningPatchApprovalPolicy:
    approval_required: bool = True
    policy_name: str = "planning_patch_approval"


@dataclass(frozen=True)
class ExternalActionApprovalPolicy:
    approval_required: bool = True
    policy_name: str = "external_action_approval"


PLANNING_PATCH_APPROVAL_POLICY = PlanningPatchApprovalPolicy()
EXTERNAL_ACTION_APPROVAL_POLICY = ExternalActionApprovalPolicy()


def evaluate_external_action_execution_guard(
    proposal: dict[str, Any],
    *,
    enable_external_writes: bool,
    require_approval_for_external_actions: bool,
    dry_run_external_actions: bool,
) -> dict[str, Any]:
    status = proposal.get("status")
    if require_approval_for_external_actions and status != "approved":
        return {"allowed": False, "reason": "proposal_not_approved", "proposal_status": status}

    if not enable_external_writes:
        return {"allowed": False, "reason": "external_writes_disabled"}

    if dry_run_external_actions:
        return {"allowed": False, "reason": "dry_run_enabled"}

    action_type = proposal.get("action_type")
    if action_type not in ALLOWED_EXTERNAL_ACTION_TYPES:
        return {"allowed": False, "reason": "action_type_not_allowed", "action_type": action_type}

    if not proposal.get("target_external_key"):
        return {"allowed": False, "reason": "missing_target_external_key"}

    payload = proposal.get("payload")
    if not isinstance(payload, dict) or not payload:
        return {"allowed": False, "reason": "missing_payload"}

    return {"allowed": True, "reason": "ready_for_live_write_boundary"}


def approve_planning_patch_proposal(proposal: dict) -> dict:
    updated = dict(proposal)
    updated["status"] = "approved"
    return updated


def reject_planning_patch_proposal(proposal: dict) -> dict:
    updated = dict(proposal)
    updated["status"] = "rejected"
    return updated


def mark_planning_patch_proposal_applied(proposal: dict) -> dict:
    updated = dict(proposal)
    updated["status"] = "applied"
    return updated


def approve_external_action_proposal(proposal: dict) -> dict:
    updated = dict(proposal)
    updated["status"] = "approved"
    return updated


def reject_external_action_proposal(proposal: dict) -> dict:
    updated = dict(proposal)
    updated["status"] = "rejected"
    return updated


def mark_external_action_proposal_applied(proposal: dict) -> dict:
    updated = dict(proposal)
    updated["status"] = "applied"
    return updated
