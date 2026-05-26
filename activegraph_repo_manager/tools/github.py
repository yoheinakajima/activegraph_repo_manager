"""Deterministic, disabled-by-default GitHub/file external-write stubs."""

from __future__ import annotations

from typing import Any


def _disabled_result(action_name: str, target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "executed": False,
        "result_status": "disabled",
        "reason": "live_write_disabled",
        "action": action_name,
        "target_external_key": target_external_key,
        "payload_keys": sorted(payload.keys()),
        "no_external_write": True,
    }


def github_post_comment(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("github_post_comment", target_external_key, payload)


def github_apply_label(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("github_apply_label", target_external_key, payload)


def github_request_changes(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("github_request_changes", target_external_key, payload)


def github_approve_pr(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("github_approve_pr", target_external_key, payload)


def github_open_issue(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("github_open_issue", target_external_key, payload)


def open_roadmap_update_pr(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("open_roadmap_update_pr", target_external_key, payload)


def open_contract_update_pr(target_external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _disabled_result("open_contract_update_pr", target_external_key, payload)


tools = ()
