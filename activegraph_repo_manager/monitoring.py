"""Deterministic monitoring artifact generation for local repo-manager state."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from activegraph_repo_manager.query import answer_question
from activegraph_repo_manager.state import LocalStateStore


def build_status(store: LocalStateStore) -> dict[str, Any]:
    """Build a deterministic status payload from local SQLite state only."""

    status_summary = store.get_summary("repo_manager_status") or {}
    sync_summary = store.get_summary("github_readonly_sync") or {}
    repository = _redact_sensitive_values(_tracked_repository(store, status_summary, sync_summary))
    last_sync_summary = _redact_sensitive_values(sync_summary or status_summary)
    pr_review_answer = answer_question("what PRs need review?", store)
    object_counts = store.object_counts()
    live_write_counters = _live_write_counters(status_summary, sync_summary)
    live_llm_counters = _live_llm_counters(status_summary, sync_summary)
    token_not_persisted = not _state_contains_token_material(store.deterministic_snapshot())

    safety_status = {
        "read_only_sync": bool(status_summary.get("read_only", True))
        and bool(sync_summary.get("read_only", status_summary.get("read_only", True))),
        "no_github_writes": live_write_counters["github_write_count"] == 0
        and live_write_counters["write_actions_attempted"] == 0
        and not bool(status_summary.get("external_write_performed", False))
        and not bool(sync_summary.get("external_write_performed", False)),
        "no_live_llm": live_llm_counters["live_llm_call_count"] == 0,
        "token_not_persisted": token_not_persisted,
    }

    return {
        "artifact_version": 1,
        "source": "local_sqlite_state",
        "tracked_repository": repository,
        "last_sync_summary": last_sync_summary,
        "counts": {
            "issues": object_counts.get("issue", 0),
            "pull_requests": object_counts.get("pull_request", 0),
            "prs_needing_review": len(pr_review_answer["items"]),
            "planning_proposals": object_counts.get("planning_patch_proposal", 0),
            "external_action_proposals": object_counts.get("external_action_proposal", 0),
        },
        "live_write_counters": live_write_counters,
        "live_llm_counters": live_llm_counters,
        "safety_status": safety_status,
        "safe": all(safety_status.values()),
    }


def build_report_markdown(status: dict[str, Any]) -> str:
    """Render a deterministic GitHub Actions-friendly Markdown report."""

    repository = status["tracked_repository"]
    counts = status["counts"]
    write_counters = status["live_write_counters"]
    llm_counters = status["live_llm_counters"]
    safety = status["safety_status"]
    last_sync = status["last_sync_summary"]

    lines = [
        "# ActiveGraph repo manager monitoring",
        "",
        "## Last sync summary",
        f"- Mode: `{last_sync.get('mode', 'unknown')}`",
        f"- Source: `{last_sync.get('source', status.get('source', 'unknown'))}`",
        f"- Repository external key: `{last_sync.get('repository_external_key', repository.get('external_key', 'unknown'))}`",
        f"- Issues seen: `{last_sync.get('issues_seen', counts['issues'])}`",
        f"- Pull requests seen: `{last_sync.get('pull_requests_seen', counts['pull_requests'])}`",
        f"- Check runs seen: `{last_sync.get('checks_seen', 0)}`",
        "",
        "## Tracked repository",
        f"- Owner/name: `{repository.get('owner', 'unknown')}/{repository.get('name', 'unknown')}`",
        f"- Default branch: `{repository.get('default_branch', 'unknown')}`",
        "",
        "## Counts",
        f"- Issues: `{counts['issues']}`",
        f"- Pull requests: `{counts['pull_requests']}`",
        f"- PRs needing review: `{counts['prs_needing_review']}`",
        f"- Planning proposals: `{counts['planning_proposals']}`",
        f"- External action proposals: `{counts['external_action_proposals']}`",
        "",
        "## Runtime counters",
        f"- GitHub write count: `{write_counters['github_write_count']}`",
        f"- Write actions attempted: `{write_counters['write_actions_attempted']}`",
        f"- Live LLM call count: `{llm_counters['live_llm_call_count']}`",
        "",
        "## Safety status",
        f"- Read-only sync: `{_format_bool(safety['read_only_sync'])}`",
        f"- No GitHub writes: `{_format_bool(safety['no_github_writes'])}`",
        f"- No live LLM: `{_format_bool(safety['no_live_llm'])}`",
        f"- Token not persisted: `{_format_bool(safety['token_not_persisted'])}`",
        "",
        f"Overall safety: `{'pass' if status['safe'] else 'attention_required'}`",
        "",
    ]
    return "\n".join(lines)


def build_dashboard_html(status: dict[str, Any], report_markdown: str) -> str:
    """Render a minimal static HTML dashboard for uploaded artifacts."""

    title = "ActiveGraph repo manager monitoring"
    status_json = json.dumps(status, indent=2, sort_keys=True)
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            f"  <title>{html.escape(title)}</title>",
            "  <style>",
            "    body { font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }",
            "    pre { background: #f6f8fa; padding: 1rem; overflow: auto; }",
            "    .safe { color: #116329; font-weight: 700; }",
            "    .attention { color: #9a6700; font-weight: 700; }",
            "  </style>",
            "</head>",
            "<body>",
            f"  <h1>{html.escape(title)}</h1>",
            f"  <p class=\"{'safe' if status['safe'] else 'attention'}\">Overall safety: {'pass' if status['safe'] else 'attention required'}</p>",
            "  <h2>Report</h2>",
            f"  <pre>{html.escape(report_markdown)}</pre>",
            "  <h2>Status JSON</h2>",
            f"  <pre>{html.escape(status_json)}</pre>",
            "</body>",
            "</html>",
            "",
        ]
    )


def write_monitoring_artifacts(
    store: LocalStateStore, out_dir: str | Path, *, include_dashboard: bool = False
) -> dict[str, Any]:
    """Write status.json, report.md, and optionally dashboard/index.html."""

    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    status = build_status(store)
    report_markdown = build_report_markdown(status)

    status_path = output_dir / "status.json"
    report_path = output_dir / "report.md"
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(report_markdown, encoding="utf-8")

    artifacts: dict[str, Any] = {
        "status": status,
        "artifacts": {
            "status_json": str(status_path),
            "report_md": str(report_path),
        },
    }
    if include_dashboard:
        dashboard_dir = output_dir / "dashboard"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        dashboard_path = dashboard_dir / "index.html"
        dashboard_path.write_text(build_dashboard_html(status, report_markdown), encoding="utf-8")
        artifacts["artifacts"]["dashboard_html"] = str(dashboard_path)
    return artifacts


_TOKEN_VALUE_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"(?:test-)?token-[A-Za-z0-9_-]{8,}"),
)
_SENSITIVE_KEY_PARTS = ("authorization", "token", "secret", "password", "credential")


def _redact_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                redacted[str(key)] = "<redacted>"
            else:
                redacted[str(key)] = _redact_sensitive_values(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive_values(item) for item in value]
    if isinstance(value, str) and _looks_like_token(value):
        return "<redacted>"
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _looks_like_token(value: str) -> bool:
    lowered = value.lower()
    if "bearer " in lowered:
        return True
    return any(pattern.search(value) for pattern in _TOKEN_VALUE_PATTERNS)


def _tracked_repository(
    store: LocalStateStore, status_summary: dict[str, Any], sync_summary: dict[str, Any]
) -> dict[str, Any]:
    repository_key = status_summary.get("repository_external_key") or sync_summary.get("repository_external_key")
    if isinstance(repository_key, str) and repository_key:
        repository = store.get_object("repository", repository_key)
        if repository is not None:
            return repository
    repositories = store.list_objects("repository")
    if repositories:
        return repositories[0]
    return {"external_key": "unknown", "owner": "unknown", "name": "unknown", "default_branch": "unknown"}


def _live_write_counters(status_summary: dict[str, Any], sync_summary: dict[str, Any]) -> dict[str, int]:
    return {
        "github_write_count": _int_value(
            sync_summary.get("github_write_count", status_summary.get("github_write_count", 0))
        ),
        "write_actions_attempted": _int_value(sync_summary.get("write_actions_attempted", 0)),
    }


def _live_llm_counters(status_summary: dict[str, Any], sync_summary: dict[str, Any]) -> dict[str, int]:
    return {
        "live_llm_call_count": _int_value(
            sync_summary.get("live_llm_call_count", status_summary.get("live_llm_call_count", 0))
        )
    }


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _format_bool(value: bool) -> str:
    return "pass" if value else "attention_required"


def _state_contains_token_material(snapshot: dict[str, Any]) -> bool:
    encoded = json.dumps(snapshot, sort_keys=True).lower()
    forbidden_markers = ("authorization", "bearer ", "github_token", "repo_manager_github_token")
    if any(marker in encoded for marker in forbidden_markers):
        return True
    return _contains_token_like_value(snapshot)


def _contains_token_like_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            _is_sensitive_key(str(key)) or _contains_token_like_value(item) for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_token_like_value(item) for item in value)
    return isinstance(value, str) and _looks_like_token(value)
