"""Deterministic helpers for approval-gated external action proposals."""

from __future__ import annotations

from typing import Any

ALLOWED_EXTERNAL_ACTION_TYPES = {
    "github_comment",
    "github_label",
    "github_request_changes",
    "github_approve_pr",
    "github_open_issue",
    "open_roadmap_update_pr",
    "open_contract_update_pr",
}


def _format_evidence_refs(evidence_refs: list[dict[str, Any]]) -> str:
    return "\n".join(f"- {ref.get('source')}::{ref.get('locator')}" for ref in evidence_refs)


def proposal_from_review_finding(finding: dict[str, Any]) -> dict[str, Any] | None:
    action_hint = finding.get("requires_external_action")
    pr_external_key = finding.get("pr_external_key")
    if not pr_external_key:
        return None

    if action_hint == "comment":
        action_type = "github_comment"
    elif action_hint == "request_changes" and bool(finding.get("blocking")):
        action_type = "github_request_changes"
    else:
        return None

    evidence_refs = list(finding.get("evidence_refs", []))
    body = (
        f"Finding {finding.get('finding_id', 'unknown')}: {finding.get('summary', '')}\n"
        f"Severity: {finding.get('severity')}\n"
        f"Category: {finding.get('category')}\n"
        "Evidence:\n"
        f"{_format_evidence_refs(evidence_refs)}"
    )

    return {
        "proposal_id": f"external-action:{finding.get('finding_id', 'unknown')}:{action_type}",
        "status": "proposed",
        "action_type": action_type,
        "target_external_key": pr_external_key,
        "payload": {"body": body},
        "evidence_refs": evidence_refs,
        "rationale": f"Review finding requires external action: {action_hint}",
        "confidence": float(finding.get("confidence", 0.0)),
    }


def proposal_from_planning_patch(planning_patch_proposal: dict[str, Any]) -> dict[str, Any] | None:
    target = planning_patch_proposal.get("target_external_key")
    field = planning_patch_proposal.get("field")
    to_value = str(planning_patch_proposal.get("to_value", ""))
    if field != "docs" and "contract" not in to_value.lower():
        return None

    action_type = "open_contract_update_pr"
    return {
        "proposal_id": f"external-action:{planning_patch_proposal.get('proposal_id')}:{action_type}",
        "status": "proposed",
        "action_type": action_type,
        "target_external_key": target or planning_patch_proposal.get("target_slug", "planning:unknown"),
        "payload": {
            "title": "Contract/docs follow-up required",
            "context": planning_patch_proposal.get("rationale", ""),
        },
        "evidence_refs": list(planning_patch_proposal.get("evidence_refs", [])),
        "rationale": "Planning patch indicates a contract/docs follow-up action.",
        "confidence": float(planning_patch_proposal.get("confidence", 0.0)),
    }


behaviors = ()
