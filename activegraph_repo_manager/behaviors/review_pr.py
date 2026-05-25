"""Deterministic, replay-only PR review findings from offline fixtures."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from activegraph_repo_manager.behaviors.analyze_pr_diff import analyze_pr_diff
from activegraph_repo_manager.behaviors.contract_guard import run_contract_guard

REQUIRED_FIELDS = {
    "pr_external_key",
    "severity",
    "category",
    "blocking",
    "title",
    "detail",
    "suggested_fix",
    "evidence_refs",
    "confidence",
    "requires_external_action",
}
ALLOWED_SEVERITY = {"info", "warning", "error"}
ALLOWED_CATEGORY = {
    "correctness",
    "determinism",
    "event_log",
    "replay",
    "api",
    "docs",
    "tests",
    "security",
    "ops",
    "migration",
    "store",
    "observability",
}


def review_input_hash(pr_payload: dict[str, Any], pr_diff: dict[str, Any]) -> str:
    canonical = {
        "pr_external_key": pr_payload.get("external_key", ""),
        "pr_title": pr_payload.get("title", ""),
        "changed_files": sorted([str(path) for path in pr_diff.get("files_changed", [])]),
        "additions": int(pr_diff.get("additions", 0)),
        "deletions": int(pr_diff.get("deletions", 0)),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def assemble_review_context(pr_payload: dict[str, Any], pr_diff: dict[str, Any]) -> dict[str, Any]:
    analysis = analyze_pr_diff(pr_diff)
    guard = run_contract_guard(pr_diff)
    return {
        "pr_external_key": pr_payload.get("external_key", ""),
        "changed_files": analysis["changed_files"],
        "semantic_reasons": analysis["semantic_reasons"],
        "touched_paths": analysis["sensitive_paths"],
        "evidence_refs": analysis["evidence_refs"],
        "contract_guard_triggered": guard["triggered"],
        "review_input_hash": review_input_hash(pr_payload, pr_diff),
    }


def _validate_finding(finding: dict[str, Any]) -> dict[str, Any]:
    missing = REQUIRED_FIELDS - set(finding)
    if missing:
        raise ValueError(f"Missing required review finding fields: {sorted(missing)}")
    if finding["severity"] not in ALLOWED_SEVERITY:
        raise ValueError("severity is not in allowed enum values")
    if finding["category"] not in ALLOWED_CATEGORY:
        raise ValueError("category is not in allowed enum values")
    if not isinstance(finding["blocking"], bool):
        raise ValueError("blocking must be a bool")
    if not isinstance(finding["requires_external_action"], bool):
        raise ValueError("requires_external_action must be a bool")
    if not isinstance(finding["evidence_refs"], list) or not finding["evidence_refs"]:
        raise ValueError("evidence_refs must be a non-empty list")
    if not isinstance(finding["confidence"], (int, float)) or not (0.0 <= float(finding["confidence"]) <= 1.0):
        raise ValueError("confidence must be in [0.0, 1.0]")
    return finding


def review_pr_from_recorded_output(
    pr_payload: dict[str, Any],
    pr_diff: dict[str, Any],
    recorded_output: dict[str, Any],
) -> dict[str, Any]:
    context = assemble_review_context(pr_payload, pr_diff)
    findings = []
    for candidate in recorded_output.get("findings", []):
        finding = dict(candidate)
        finding["pr_external_key"] = context["pr_external_key"]
        if not finding.get("evidence_refs"):
            finding["evidence_refs"] = list(context["evidence_refs"])
        findings.append(_validate_finding(finding))

    return {
        "pr_external_key": context["pr_external_key"],
        "review_prompt_version": recorded_output.get("review_prompt_version", "review_pr.v1"),
        "review_input_hash": context["review_input_hash"],
        "contract_guard": run_contract_guard(pr_diff),
        "context": context,
        "findings": findings,
        "external_action_proposals": [],
        "planning_patch_proposals": [],
        "planning_item_mutations": [],
    }


behaviors = ()
