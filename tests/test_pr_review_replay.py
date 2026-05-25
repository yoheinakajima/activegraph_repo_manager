import json
from copy import deepcopy
from pathlib import Path

from activegraph_repo_manager.behaviors.analyze_pr_diff import analyze_pr_diff
from activegraph_repo_manager.behaviors.contract_guard import run_contract_guard
from activegraph_repo_manager.behaviors.review_pr import (
    ALLOWED_CATEGORY,
    ALLOWED_SEVERITY,
    REQUIRED_FIELDS,
    review_pr_from_recorded_output,
)

FIXTURE_ROOT = Path("activegraph_repo_manager/fixtures")


def _load(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_contract_sensitive_fixture_detected_as_semantic_change() -> None:
    pr_diff = _load("pr_diff_contract_sensitive.json")["pr_diff"]
    analysis = analyze_pr_diff(pr_diff)

    assert analysis["is_contract_sensitive"] is True
    assert "activegraph/store/event_store.py" in analysis["sensitive_paths"]
    assert analysis["evidence_refs"]


def test_non_sensitive_fixture_does_not_trigger_contract_guard() -> None:
    pr_diff = {
        "pull_request_external_key": "gh:pr:example/repo#1",
        "files_changed": ["README.md", "tests/test_smoke.py"],
    }
    guard = run_contract_guard(pr_diff)

    assert guard["triggered"] is False
    assert guard["reasons"] == []
    assert guard["evidence_refs"] == []


def test_pr24_style_fixture_emits_structured_review_finding() -> None:
    pr_payload = _load("pr_24_falkordb_eventstore.json")["pull_request"]
    pr_diff = _load("pr_diff_contract_sensitive.json")["pr_diff"]
    recorded = _load("llm_pr_review.v1.json")

    result = review_pr_from_recorded_output(pr_payload, pr_diff, recorded)

    assert result["findings"]
    assert result["findings"][0]["category"] in {"store", "event_log", "replay", "docs", "tests"}


def test_review_findings_validate_required_fields_and_allowed_values() -> None:
    pr_payload = _load("pr_24_falkordb_eventstore.json")["pull_request"]
    pr_diff = _load("pr_diff_contract_sensitive.json")["pr_diff"]
    recorded = _load("llm_pr_review.v1.json")

    finding = review_pr_from_recorded_output(pr_payload, pr_diff, recorded)["findings"][0]

    assert REQUIRED_FIELDS.issubset(finding.keys())
    assert finding["severity"] in ALLOWED_SEVERITY
    assert finding["category"] in ALLOWED_CATEGORY


def test_review_finding_includes_evidence_refs() -> None:
    pr_payload = _load("pr_24_falkordb_eventstore.json")["pull_request"]
    pr_diff = _load("pr_diff_contract_sensitive.json")["pr_diff"]
    recorded = _load("llm_pr_review.v1.json")

    finding = review_pr_from_recorded_output(pr_payload, pr_diff, recorded)["findings"][0]
    assert isinstance(finding["evidence_refs"], list)
    assert finding["evidence_refs"]


def test_recorded_pr_review_is_deterministic_and_replay_stable() -> None:
    pr_payload = _load("pr_24_falkordb_eventstore.json")["pull_request"]
    pr_diff = _load("pr_diff_contract_sensitive.json")["pr_diff"]
    recorded = _load("llm_pr_review.v1.json")

    first = review_pr_from_recorded_output(pr_payload, pr_diff, recorded)
    second = review_pr_from_recorded_output(deepcopy(pr_payload), deepcopy(pr_diff), deepcopy(recorded))
    assert first == second


def test_pr_review_does_not_create_external_or_planning_proposals_or_mutations() -> None:
    pr_payload = _load("pr_24_falkordb_eventstore.json")["pull_request"]
    pr_diff = _load("pr_diff_contract_sensitive.json")["pr_diff"]
    recorded = _load("llm_pr_review.v1.json")

    result = review_pr_from_recorded_output(pr_payload, pr_diff, recorded)

    assert result["external_action_proposals"] == []
    assert result["planning_patch_proposals"] == []
    assert result["planning_item_mutations"] == []
