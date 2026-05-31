import json
import subprocess
import sys
from pathlib import Path

from activegraph_repo_manager.demo_state import seed_keyless_demo_state
from activegraph_repo_manager.monitoring import build_report_markdown, build_status, write_monitoring_artifacts
from activegraph_repo_manager.state import LocalStateStore

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "repo-manager.yml"


def test_monitoring_status_and_report_are_deterministic_and_read_only() -> None:
    store = LocalStateStore.in_memory()
    try:
        seed_keyless_demo_state(store)

        first = build_status(store)
        second = build_status(store)
        report = build_report_markdown(first)

        assert first == second
        assert first["source"] == "local_sqlite_state"
        assert first["counts"]["issues"] == 1
        assert first["counts"]["pull_requests"] == 1
        assert first["counts"]["prs_needing_review"] == 1
        assert first["counts"]["planning_proposals"] == 1
        assert first["counts"]["external_action_proposals"] == 0
        assert first["live_write_counters"] == {"github_write_count": 0, "write_actions_attempted": 0}
        assert first["live_llm_counters"] == {"live_llm_call_count": 0}
        assert first["safety_status"] == {
            "read_only_sync": True,
            "no_github_writes": True,
            "no_live_llm": True,
            "token_not_persisted": True,
        }
        assert first["safe"] is True
        assert "# ActiveGraph repo manager monitoring" in report
        assert "No GitHub writes: `pass`" in report
        assert "No live LLM: `pass`" in report
        assert "Token not persisted: `pass`" in report
    finally:
        store.close()


def test_report_status_and_dashboard_redact_token_like_values(tmp_path: Path) -> None:
    secret = "github_pat_exampleSecretToken1234567890"
    store = LocalStateStore.in_memory()
    try:
        seed_keyless_demo_state(store)
        status_summary = store.get_summary("repo_manager_status") or {}
        status_summary["token"] = secret
        store.upsert_summary("repo_manager_status", status_summary)
        repository_key = status_summary["repository_external_key"]
        repository = store.get_object("repository", repository_key) or {}
        repository["external_metadata"] = {"authorization": f"Bearer {secret}"}
        store.upsert_object("repository", repository)

        result = write_monitoring_artifacts(store, tmp_path / "report", include_dashboard=True)
        status_path = Path(result["artifacts"]["status_json"])
        report_path = Path(result["artifacts"]["report_md"])
        dashboard_path = Path(result["artifacts"]["dashboard_html"])

        combined_output = "\n".join(
            [status_path.read_text(), report_path.read_text(), dashboard_path.read_text()]
        )
        assert secret not in combined_output
        assert f"Bearer {secret}" not in combined_output
        assert json.loads(status_path.read_text())["safe"] is False
        assert json.loads(status_path.read_text())["safety_status"]["token_not_persisted"] is False
    finally:
        store.close()


def test_write_monitoring_artifacts_creates_status_report_and_dashboard(tmp_path: Path) -> None:
    store = LocalStateStore.in_memory()
    try:
        seed_keyless_demo_state(store)
        result = write_monitoring_artifacts(store, tmp_path / "report", include_dashboard=True)

        status_path = Path(result["artifacts"]["status_json"])
        report_path = Path(result["artifacts"]["report_md"])
        dashboard_path = Path(result["artifacts"]["dashboard_html"])

        assert status_path == tmp_path / "report" / "status.json"
        assert report_path == tmp_path / "report" / "report.md"
        assert dashboard_path == tmp_path / "report" / "dashboard" / "index.html"
        assert json.loads(status_path.read_text())["safe"] is True
        assert "## Safety status" in report_path.read_text()
        assert "ActiveGraph repo manager monitoring" in dashboard_path.read_text()
    finally:
        store.close()


def test_cli_report_generates_monitoring_artifacts_without_credentials(tmp_path: Path) -> None:
    state_path = tmp_path / ".repo-manager" / "state.sqlite"
    report_dir = tmp_path / ".repo-manager" / "report"

    demo = subprocess.run(
        [sys.executable, "-m", "activegraph_repo_manager", "keyless-demo", "--state", str(state_path)],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    assert json.loads(demo.stdout)["external_write_performed"] is False

    paths_before_report = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    report = subprocess.run(
        [
            sys.executable,
            "-m",
            "activegraph_repo_manager",
            "report",
            "--state",
            str(state_path),
            "--out",
            str(report_dir),
            "--dashboard",
        ],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    payload = json.loads(report.stdout)

    assert payload["status"]["safe"] is True
    assert (report_dir / "status.json").exists()
    assert (report_dir / "report.md").exists()
    assert (report_dir / "dashboard" / "index.html").exists()

    paths_after_report = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    created_by_report = paths_after_report - paths_before_report
    assert created_by_report == {
        Path(".repo-manager/report"),
        Path(".repo-manager/report/status.json"),
        Path(".repo-manager/report/report.md"),
        Path(".repo-manager/report/dashboard"),
        Path(".repo-manager/report/dashboard/index.html"),
    }


def test_github_actions_workflow_is_read_only_and_generates_monitoring_artifacts() -> None:
    assert WORKFLOW_PATH.exists()
    workflow = WORKFLOW_PATH.read_text()

    assert "workflow_dispatch:" in workflow
    assert "schedule:" in workflow
    assert 'cron: "*/30 * * * *"' in workflow
    assert "contents: read" in workflow
    assert "issues: read" in workflow
    assert "pull-requests: read" in workflow
    assert "checks: read" in workflow
    assert "contents: write" not in workflow
    assert "issues: write" not in workflow
    assert "pull-requests: write" not in workflow
    assert "write-all" not in workflow
    assert "POST" not in workflow
    assert "PATCH" not in workflow
    assert "PUT" not in workflow
    assert "DELETE" not in workflow
    assert "REPO_MANAGER_GITHUB_TOKEN: ${{ secrets.REPO_MANAGER_GITHUB_TOKEN }}" in workflow
    assert "persist-credentials: false" in workflow
    assert "--token-env REPO_MANAGER_GITHUB_TOKEN" in workflow
    assert "python -m activegraph_repo_manager report" in workflow
    assert "cat .repo-manager/report/report.md >> \"${GITHUB_STEP_SUMMARY}\"" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "repo-manager-monitoring" in workflow
    assert ".repo-manager/state.sqlite" in workflow
    assert ".repo-manager/report/status.json" in workflow
    assert ".repo-manager/report/report.md" in workflow
    assert ".repo-manager/report/dashboard/index.html" in workflow
    assert "peaceiris/actions-gh-pages" not in workflow
    assert "actions/deploy-pages" not in workflow
