from activegraph_repo_manager.tools.demo import run_keyless_demo


def test_demo_runs_without_github_credentials_or_live_llm_calls() -> None:
    summary = run_keyless_demo()
    assert summary["repository_external_key"] == "gh:repo:yoheinakajima/activegraph"
    assert summary["read_only_guarantees"]["live_llm_call_count"] == 0


def test_demo_output_is_deterministic_across_repeated_runs() -> None:
    first = run_keyless_demo()
    second = run_keyless_demo()
    assert first == second


def test_issue_fixture_appears_as_observability_adoption_surface_gap() -> None:
    summary = run_keyless_demo()
    issue_summary = summary["issue_classification_summary"]
    assert issue_summary["work_type"] == "observability"
    assert "operator_surface" in issue_summary["affected_areas"]


def test_pr_fixture_appears_as_store_backend_high_risk() -> None:
    summary = run_keyless_demo()
    pr_summary = summary["pr_classification_summary"]
    assert pr_summary["work_type"] == "store_backend"
    assert pr_summary["risk"] == "high"


def test_repo_grasp_summary_includes_files_symbols_and_test_surfaces() -> None:
    summary = run_keyless_demo()
    assert summary["repo_file_count"] > 0
    assert summary["symbol_count"] > 0
    assert summary["test_surface_count"] > 0


def test_contract_guard_triggered_for_contract_sensitive_diff_fixture() -> None:
    summary = run_keyless_demo()
    assert summary["contract_guard_triggered"] is True


def test_structured_review_findings_present() -> None:
    summary = run_keyless_demo()
    assert summary["review_findings_count"] >= 1


def test_planning_patch_proposal_present_for_fixture_scenario() -> None:
    summary = run_keyless_demo()
    assert summary["planning_proposals_count"] >= 1


def test_read_only_guarantee_counters_are_zero() -> None:
    summary = run_keyless_demo()
    guarantees = summary["read_only_guarantees"]
    assert guarantees["external_action_proposals_count"] == 0
    assert guarantees["planning_item_mutations_count"] == 0
    assert guarantees["github_write_count"] == 0
    assert guarantees["live_llm_call_count"] == 0
    assert guarantees["external_write_performed"] is False



def test_optional_external_action_proposal_counters_are_available_without_writes() -> None:
    summary = run_keyless_demo(include_external_action_proposals=True)
    assert summary["external_action_proposals_count"] == 0
    assert summary["dry_run_external_actions_count"] == 0
    guarantees = summary["read_only_guarantees"]
    assert guarantees["github_write_count"] == 0
    assert guarantees["external_write_performed"] is False
    assert guarantees["live_llm_call_count"] == 0
