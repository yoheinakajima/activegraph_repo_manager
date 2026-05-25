"""Deterministic issue classification replay using recorded fixture output."""

from __future__ import annotations

import hashlib
import json
from typing import Any

REQUIRED_FIELDS = {
    "work_type",
    "scope",
    "risk",
    "planning_priority",
    "triage_urgency",
    "lifecycle_status",
    "affected_areas",
    "needs_maintainer_input",
    "classification_confidence",
    "classification_prompt_version",
    "classification_input_hash",
}

ALLOWED_WORK_TYPE = {"observability", "store_backend", "bugfix", "feature", "docs", "refactor", "infra"}
ALLOWED_SCOPE = {"S", "M", "L", "repository", "module", "file", "line"}
ALLOWED_RISK = {"low", "medium", "high"}
ALLOWED_PRIORITY = {"low", "medium", "high", "critical", "should_have"}
ALLOWED_TRIAGE_URGENCY = {"low", "normal", "urgent"}
ALLOWED_LIFECYCLE_STATUS = {"open", "in_progress", "blocked", "closed"}


def classification_input_hash(issue_payload: dict[str, Any]) -> str:
    metadata = issue_payload.get("external_metadata", {})
    canonical = {
        "title": issue_payload.get("title", ""),
        "body": metadata.get("body", ""),
        "labels": sorted(metadata.get("labels", [])),
        "state": issue_payload.get("status", ""),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def classify_issue_from_recorded_output(issue_payload: dict[str, Any], recorded_output: dict[str, Any]) -> dict[str, Any]:
    payload = dict(recorded_output)
    payload["classification_input_hash"] = classification_input_hash(issue_payload)
    missing = REQUIRED_FIELDS - set(payload)
    if missing:
        raise ValueError(f"Missing required classification fields: {sorted(missing)}")
    if not isinstance(payload["affected_areas"], list):
        raise ValueError("affected_areas must be a list")
    if payload["work_type"] not in ALLOWED_WORK_TYPE:
        raise ValueError("work_type is not in allowed enum values")
    if payload["scope"] not in ALLOWED_SCOPE:
        raise ValueError("scope is not in allowed enum values")
    if payload["risk"] not in ALLOWED_RISK:
        raise ValueError("risk is not in allowed enum values")
    if payload["planning_priority"] not in ALLOWED_PRIORITY:
        raise ValueError("planning_priority is not in allowed enum values")
    if payload["triage_urgency"] not in ALLOWED_TRIAGE_URGENCY:
        raise ValueError("triage_urgency is not in allowed enum values")
    if payload["lifecycle_status"] not in ALLOWED_LIFECYCLE_STATUS:
        raise ValueError("lifecycle_status is not in allowed enum values")
    if not isinstance(payload["classification_confidence"], (int, float)) or not (
        0.0 <= float(payload["classification_confidence"]) <= 1.0
    ):
        raise ValueError("classification_confidence must be in [0.0, 1.0]")
    return payload


behaviors = ()
