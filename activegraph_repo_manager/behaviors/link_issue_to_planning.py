"""Deterministic lightweight linking helpers for issues and PRs to planning items."""

from __future__ import annotations

from typing import Any


def link_issue_to_planning(issue_payload: dict[str, Any], planning_items: list[dict[str, Any]]) -> list[dict[str, str]]:
    text = f"{issue_payload.get('title', '')} {issue_payload.get('external_metadata', {}).get('body', '')}".lower()
    relations: list[dict[str, str]] = []
    for item in planning_items:
        item_text = f"{item.get('title', '')}".lower()
        if any(token in text and token in item_text for token in ("observability", "telemetry", "metric")):
            relations.append({"relation": "tracks", "from": issue_payload["external_key"], "to": item["external_key"]})
    return relations


def link_pr_to_planning(
    pr_payload: dict[str, Any],
    planning_items: list[dict[str, Any]],
    issue_external_keys: list[str] | None = None,
) -> list[dict[str, str]]:
    text = f"{pr_payload.get('title', '')} {pr_payload.get('external_metadata', {}).get('body', '')}".lower()
    relations: list[dict[str, str]] = []
    for item in planning_items:
        item_text = item.get("title", "").lower()
        if any(token in text and token in item_text for token in ("store", "event", "checkpoint")):
            relations.append({"relation": "advances", "from": pr_payload["external_key"], "to": item["external_key"]})
    for issue_key in issue_external_keys or []:
        if f"#{issue_key.split('#')[-1]}" in text:
            relations.append({"relation": "addresses", "from": pr_payload["external_key"], "to": issue_key})
    return relations


behaviors = ()
