import json
from copy import deepcopy
from pathlib import Path

from activegraph_repo_manager.behaviors.classify_issue import (
    classification_input_hash as issue_hash,
    classify_issue_from_recorded_output,
)
from activegraph_repo_manager.behaviors.classify_pr import (
    classification_input_hash as pr_hash,
    classify_pr_from_recorded_output,
)
from activegraph_repo_manager.behaviors.link_issue_to_planning import (
    link_issue_to_planning,
    link_pr_to_planning,
)

FIXTURE_ROOT = Path("activegraph_repo_manager/fixtures")


def _load(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_issue_23_classifies_as_observability_gap() -> None:
    issue = _load("issue_23_open_telemetry.json")["issue"]
    recorded = _load("llm_issue_classification.v1.json")
    result = classify_issue_from_recorded_output(issue, recorded)

    assert result["work_type"] == "observability"
    assert result["scope"] == "M"
    assert result["risk"] == "medium"
    assert result["planning_priority"] == "should_have"
    assert result["triage_urgency"] == "normal"
    assert {"observability", "metrics", "operator_surface"}.issubset(result["affected_areas"])
    assert result["needs_maintainer_input"] is True


def test_pr_24_classifies_as_store_backend_high_risk() -> None:
    pr = _load("pr_24_falkordb_eventstore.json")["pull_request"]
    recorded = _load("llm_pr_classification.v1.json")
    changed_files = ["activegraph_repo_manager/tools/repo_index.py", "activegraph_repo_manager/tools/github.py"]
    result = classify_pr_from_recorded_output(pr, changed_files, recorded)

    assert result["work_type"] == "store_backend"
    assert result["scope"] == "L"
    assert result["risk"] == "high"
    assert {"store", "event_log", "operator_surface"}.issubset(result["affected_areas"])


def test_classification_input_hash_stability_and_meaningful_change() -> None:
    issue = _load("issue_23_open_telemetry.json")["issue"]
    first = issue_hash(issue)
    second = issue_hash(deepcopy(issue))
    assert first == second

    metadata_only = deepcopy(issue)
    metadata_only["external_metadata"]["html_url"] = "https://example.com/changed"
    assert issue_hash(metadata_only) == first

    meaningful = deepcopy(issue)
    meaningful["title"] = "Different classification signal"
    assert issue_hash(meaningful) != first


def test_issue_reclassifies_only_when_meaningful_hash_changes() -> None:
    issue = _load("issue_23_open_telemetry.json")["issue"]
    recorded = _load("llm_issue_classification.v1.json")

    classifications = 0
    last_hash = ""
    for payload in (
        issue,
        deepcopy(issue),
        {**deepcopy(issue), "external_metadata": {**issue["external_metadata"], "html_url": "https://example.invalid"}},
        {**deepcopy(issue), "title": "Add OTEL spans for ingest pipeline and replay"},
    ):
        current_hash = issue_hash(payload)
        if current_hash != last_hash:
            classify_issue_from_recorded_output(payload, recorded)
            classifications += 1
            last_hash = current_hash

    assert classifications == 2


def test_pr_hash_stability_for_meaningful_inputs() -> None:
    pr = _load("pr_24_falkordb_eventstore.json")["pull_request"]
    files = ["b.py", "a.py"]
    assert pr_hash(pr, files) == pr_hash(deepcopy(pr), ["a.py", "b.py"])


def test_recorded_classification_outputs_validate_required_enum_like_fields() -> None:
    issue = _load("issue_23_open_telemetry.json")["issue"]
    pr = _load("pr_24_falkordb_eventstore.json")["pull_request"]
    issue_recorded = _load("llm_issue_classification.v1.json")
    pr_recorded = _load("llm_pr_classification.v1.json")

    issue_result = classify_issue_from_recorded_output(issue, issue_recorded)
    pr_result = classify_pr_from_recorded_output(pr, ["a.py"], pr_recorded)

    assert issue_result["classification_prompt_version"] == "classify_issue.v1"
    assert isinstance(issue_result["classification_input_hash"], str)
    assert pr_result["classification_prompt_version"] == "classify_pr.v1"
    assert isinstance(pr_result["classification_input_hash"], str)


def test_deterministic_linking_issue_and_pr_without_mutation() -> None:
    issue = _load("issue_23_open_telemetry.json")["issue"]
    pr = _load("pr_24_falkordb_eventstore.json")["pull_request"]
    pr["external_metadata"]["body"] = "Implements store checkpointing and closes #23"
    planning_items = [
        {"external_key": "plan:obs:1", "title": "Improve observability and telemetry metrics", "status": "open"},
        {"external_key": "plan:store:1", "title": "Store backend event checkpointing", "status": "open"},
    ]
    baseline = deepcopy(planning_items)

    issue_rel = link_issue_to_planning(issue, planning_items)
    pr_rel = link_pr_to_planning(pr, planning_items, [issue["external_key"]])

    assert any(r["relation"] == "tracks" for r in issue_rel)
    assert any(r["relation"] == "advances" for r in pr_rel)
    assert any(r["relation"] == "addresses" for r in pr_rel)
    assert planning_items == baseline
