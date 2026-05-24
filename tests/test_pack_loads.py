import importlib
import json
from pathlib import Path


def test_package_imports() -> None:
    module = importlib.import_module("activegraph_repo_manager")
    assert module is not None


def test_behavior_and_tool_modules_expose_empty_tuples() -> None:
    behavior_modules = [
        "ingest_github",
        "index_repo",
        "load_planning_docs",
        "classify_issue",
        "classify_pr",
        "link_issue_to_planning",
        "analyze_pr_diff",
        "contract_guard",
        "review_pr",
        "propose_planning_patch",
        "apply_approved_actions",
        "digest",
    ]
    for name in behavior_modules:
        mod = importlib.import_module(f"activegraph_repo_manager.behaviors.{name}")
        assert getattr(mod, "behaviors") == ()

    tool_modules = ["github", "git", "repo_index", "test_runner"]
    for name in tool_modules:
        mod = importlib.import_module(f"activegraph_repo_manager.tools.{name}")
        assert getattr(mod, "tools") == ()


def test_prompt_placeholders_exist() -> None:
    prompt_files = [
        "classify_issue.v1.md",
        "classify_pr.v1.md",
        "summarize_file.v1.md",
        "review_pr.v1.md",
        "contract_guard.v1.md",
        "planning_decider.v1.md",
        "maintainer_digest.v1.md",
    ]
    root = Path("activegraph_repo_manager/prompts")
    for name in prompt_files:
        assert (root / name).is_file()


def test_fixture_placeholders_are_valid_json() -> None:
    fixture_files = [
        "issue_23_open_telemetry.json",
        "pr_24_falkordb_eventstore.json",
        "repo_snapshot_minimal.json",
        "pr_diff_contract_sensitive.json",
        "llm_issue_classification.v1.json",
        "llm_pr_review.v1.json",
        "llm_planning_decider.v1.json",
    ]
    root = Path("activegraph_repo_manager/fixtures")
    for name in fixture_files:
        payload = json.loads((root / name).read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
