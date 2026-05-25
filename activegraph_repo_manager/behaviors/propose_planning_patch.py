"""Deterministic helpers for approval-gated planning patch proposals."""

from __future__ import annotations

PROPOSAL_STATUS_ALLOWED = {"proposed", "approved", "rejected", "applied"}
PLANNING_CHANGE_TYPE_ALLOWED = {
    "new_item",
    "status",
    "priority",
    "scope",
    "risk",
    "split",
    "merge",
    "defer",
    "close",
    "acceptance_criteria",
}


def proposal_id_from_event(caused_by_event_id: str, change_type: str) -> str:
    normalized = caused_by_event_id.replace(":", "_").replace("/", "_")
    return f"planning_patch::{change_type}::{normalized}"


def propose_status_implemented_for_merged_pr(*, pr_external_key: str, pr_status: str, planning_item_external_key: str, current_status: str, has_blocking_finding: bool, review_external_key: str | None = None, check_external_key: str | None = None) -> dict | None:
    if pr_status != "merged":
        return None
    if has_blocking_finding:
        return None
    if current_status not in {"planned", "in_progress"}:
        return None

    evidence_refs = [
        {"source": "pr", "locator": pr_external_key},
        {"source": "planning_item", "locator": planning_item_external_key},
    ]
    if review_external_key:
        evidence_refs.append({"source": "review", "locator": review_external_key})
    if check_external_key:
        evidence_refs.append({"source": "check", "locator": check_external_key})

    event_id = f"event:pr-merged:{pr_external_key}"
    return {
        "proposal_id": proposal_id_from_event(event_id, "status"),
        "status": "proposed",
        "change_type": "status",
        "field": "status",
        "target_external_key": planning_item_external_key,
        "target_slug": None,
        "from_value": current_status,
        "to_value": "implemented",
        "proposed_item": None,
        "evidence_refs": evidence_refs,
        "confidence": 0.95,
        "rationale": "Merged PR advances planning item with no blocking findings.",
        "caused_by_event_id": event_id,
        "proposed_by_behavior": "propose_planning_patch",
    }


def propose_new_item_for_high_signal_issue(*, issue_external_key: str, issue_number: int, issue_title: str) -> dict:
    target_slug = f"candidate:issue-{issue_number}"
    event_id = f"event:issue-triage:{issue_external_key}"
    return {
        "proposal_id": proposal_id_from_event(event_id, "new_item"),
        "status": "proposed",
        "change_type": "new_item",
        "field": "planning_item",
        "target_external_key": None,
        "target_slug": target_slug,
        "from_value": None,
        "to_value": "proposed_new_item",
        "proposed_item": {
            "external_key": f"planning:auto:issue:{issue_number}",
            "title": issue_title,
            "priority": "high",
            "status": "planned",
            "work_type": "observability",
        },
        "evidence_refs": [{"source": "issue", "locator": issue_external_key}],
        "confidence": 0.9,
        "rationale": "High-signal unmatched issue indicates a planning gap.",
        "caused_by_event_id": event_id,
        "proposed_by_behavior": "propose_planning_patch",
    }


behaviors = ()
