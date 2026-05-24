"""Approval policy placeholders for gated actions."""

from pydantic import BaseModel, ConfigDict


class PlanningPatchApprovalPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_required: bool = True
    policy_name: str = "planning_patch_approval"


class ExternalActionApprovalPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_required: bool = True
    policy_name: str = "external_action_approval"


PLANNING_PATCH_APPROVAL_POLICY = PlanningPatchApprovalPolicy()
EXTERNAL_ACTION_APPROVAL_POLICY = ExternalActionApprovalPolicy()
