"""Approval policy helpers for deterministic, offline proposal lifecycles."""

from dataclasses import dataclass


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
