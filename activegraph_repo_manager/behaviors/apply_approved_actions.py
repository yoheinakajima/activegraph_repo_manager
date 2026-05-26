"""Deterministic, dry-run-first external action execution helpers."""

from __future__ import annotations

from typing import Any

from activegraph_repo_manager.policies import evaluate_external_action_execution_guard


def _summarize_payload(payload: dict[str, Any]) -> str:
    keys = sorted(payload.keys())
    return ", ".join(keys)


def execute_external_action_proposal_dry_run(
    proposal: dict[str, Any],
    *,
    enable_external_writes: bool = False,
    require_approval_for_external_actions: bool = True,
    dry_run_external_actions: bool = True,
) -> dict[str, Any]:
    """Evaluate external-action proposal through policy gates.

    Phase 5b behavior: keep execution deterministic and side-effect free.
    Even if all live-write gates are opened, return a deterministic
    "not implemented" outcome with no external writes.
    """

    status = proposal.get("status")
    if require_approval_for_external_actions and status != "approved":
        return {
            "executed": False,
            "dry_run": True,
            "reason": "proposal_not_approved",
            "proposal_status": status,
            "no_external_write": True,
        }

    payload = dict(proposal.get("payload", {}))

    if dry_run_external_actions:
        return {
            "executed": True,
            "dry_run": True,
            "no_external_write": True,
            "result_status": "dry_run_applied",
            "action_type": proposal.get("action_type"),
            "target_external_key": proposal.get("target_external_key"),
            "payload_summary": _summarize_payload(payload),
            "evidence_refs": list(proposal.get("evidence_refs", [])),
        }

    guard = evaluate_external_action_execution_guard(
        proposal,
        enable_external_writes=enable_external_writes,
        require_approval_for_external_actions=require_approval_for_external_actions,
        dry_run_external_actions=dry_run_external_actions,
    )
    if not guard["allowed"]:
        return {
            "executed": False,
            "dry_run": False,
            "reason": guard["reason"],
            "proposal_status": proposal.get("status"),
            "no_external_write": True,
        }

    return {
        "executed": False,
        "dry_run": False,
        "no_external_write": True,
        "result_status": "live_write_not_implemented",
        "reason": "phase_5b_boundary_only",
        "action_type": proposal.get("action_type"),
        "target_external_key": proposal.get("target_external_key"),
        "payload_summary": _summarize_payload(payload),
        "evidence_refs": list(proposal.get("evidence_refs", [])),
    }


behaviors = ()
