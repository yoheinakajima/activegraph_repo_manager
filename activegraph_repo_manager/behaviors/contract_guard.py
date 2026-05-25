"""Mechanical contract-guard checks over deterministic PR diff analysis."""

from __future__ import annotations

from typing import Any

from activegraph_repo_manager.behaviors.analyze_pr_diff import analyze_pr_diff


def run_contract_guard(pr_diff: dict[str, Any]) -> dict[str, Any]:
    analysis = analyze_pr_diff(pr_diff)
    return {
        "pr_external_key": analysis["pr_external_key"],
        "triggered": analysis["is_contract_sensitive"],
        "reasons": list(analysis["semantic_reasons"]),
        "sensitive_paths": list(analysis["sensitive_paths"]),
        "evidence_refs": list(analysis["evidence_refs"]),
    }


behaviors = ()
