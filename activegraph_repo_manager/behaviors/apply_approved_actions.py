"""Deterministic, dry-run-only external action execution helpers."""

from __future__ import annotations

from typing import Any


def _summarize_payload(payload: dict[str, Any]) -> str:
    keys = sorted(payload.keys())
    return ", ".join(keys)


def execute_external_action_proposal_dry_run(proposal: dict[str, Any]) -> dict[str, Any]:
    """Execute an approved external-action proposal in dry-run mode only.

    This helper is deterministic and never performs network, filesystem, or
    planning mutations. Non-approved proposals are rejected.
    """

    status = proposal.get("status")
    if status != "approved":
        return {
            "executed": False,
            "dry_run": True,
            "reason": "proposal_not_approved",
            "proposal_status": status,
            "no_external_write": True,
        }

    payload = dict(proposal.get("payload", {}))
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


behaviors = ()
