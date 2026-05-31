"""Deterministic local-state question router for the repo-governance pack."""

from __future__ import annotations

from typing import Any

from activegraph_repo_manager.state import LocalStateStore

SAFE_TO_RUN_COMMANDS = (
    "python -m activegraph_repo_manager demo",
    "python -m activegraph_repo_manager ask 'what issues are open?'",
    "pytest tests/test_keyless_demo.py",
    "pytest tests/test_github_readonly_sync.py",
    "pytest tests/test_external_action_policy.py",
    "pytest tests/test_live_write_boundary.py",
    "pytest tests/test_pack_integration_audit.py",
)


def answer_question(question: str, store: LocalStateStore) -> dict[str, Any]:
    """Answer a supported question family using only deterministic local state."""

    normalized = _normalize(question)
    if _asks_open_issues(normalized):
        return _answer_with_items(question, "Open issues in local state.", _open_items(store, "issue"))
    if _asks_open_prs(normalized):
        return _answer_with_items(question, "Open pull requests in local state.", _open_items(store, "pull_request"))
    if "pr" in normalized and "need" in normalized and "review" in normalized:
        return _answer_prs_need_review(question, store)
    if "blocking" in normalized and "planning" in normalized:
        return _answer_blocking_planning(question, store)
    if "planning" in normalized and "proposal" in normalized:
        return _answer_with_items(
            question,
            "Planning patch proposals tracked in local state.",
            store.list_objects("planning_patch_proposal"),
        )
    if "external action" in normalized or ("dry run" in normalized and "action" in normalized):
        return _answer_external_actions(question, store)
    if "summarize issue" in normalized or "summary issue" in normalized:
        return _answer_numbered_object(question, store, "issue")
    if "summarize pr" in normalized or "summary pr" in normalized or "summarize pull request" in normalized:
        return _answer_numbered_object(question, store, "pull_request")
    if "current repo manager status" in normalized or "repo manager status" in normalized or normalized == "status":
        return _answer_status(question, store)
    if "safe to run" in normalized:
        return _answer_safe_to_run(question)
    return _base_answer(
        question,
        "I can answer from local state about open issues, open PRs, PRs needing review, planning blockers, planning proposals, external action proposals, issue/PR summaries, repo-manager status, and safe commands.",
        [],
    )


def _base_answer(question: str, answer: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "question": question,
        "answer": answer,
        "items": items,
        "source": "local_state",
        "live_llm_call_count": 0,
    }


def _answer_with_items(question: str, prefix: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(items)
    suffix = f" Found {count} item" + ("." if count == 1 else "s.")
    return _base_answer(question, prefix + suffix, items)


def _normalize(question: str) -> str:
    return " ".join(question.lower().replace("'", "").replace("?", " ").split())


def _asks_open_issues(normalized: str) -> bool:
    return "issue" in normalized and "open" in normalized and "summarize" not in normalized


def _asks_open_prs(normalized: str) -> bool:
    mentions_pr = "prs" in normalized or "pr " in f"{normalized} " or "pull request" in normalized
    return mentions_pr and "open" in normalized and "review" not in normalized and "summarize" not in normalized


def _open_items(store: LocalStateStore, object_type: str) -> list[dict[str, Any]]:
    return [item for item in store.list_objects(object_type) if str(item.get("status", "")).lower() == "open"]


def _answer_prs_need_review(question: str, store: LocalStateStore) -> dict[str, Any]:
    open_prs = _open_items(store, "pull_request")
    findings_by_pr: dict[str, list[dict[str, Any]]] = {}
    for finding in store.list_objects("review_finding"):
        pr_key = str(finding.get("pr_external_key") or "")
        if pr_key:
            findings_by_pr.setdefault(pr_key, []).append(finding)

    items = []
    for pr in open_prs:
        pr_key = str(pr["external_key"])
        findings = findings_by_pr.get(pr_key, [])
        blocking_findings = [finding for finding in findings if bool(finding.get("blocking"))]
        if findings or not _has_successful_check(store, pr_key):
            items.append(
                {
                    **pr,
                    "review_findings_count": len(findings),
                    "blocking_findings_count": len(blocking_findings),
                    "successful_check_present": _has_successful_check(store, pr_key),
                }
            )
    return _answer_with_items(question, "Open PRs that need review attention.", items)


def _has_successful_check(store: LocalStateStore, pr_external_key: str) -> bool:
    for check_run in store.list_objects("check_run"):
        metadata = check_run.get("external_metadata", {})
        if not isinstance(metadata, dict):
            continue
        if metadata.get("pull_request_external_key") == pr_external_key:
            return check_run.get("conclusion") == "success"
    return False


def _answer_blocking_planning(question: str, store: LocalStateStore) -> dict[str, Any]:
    blockers = []
    for proposal in store.list_objects("planning_patch_proposal"):
        if proposal.get("status") == "proposed":
            blockers.append({**proposal, "blocking_reason": "awaiting approval gate"})
    for action in store.list_objects("external_action_proposal"):
        if action.get("status") == "proposed":
            blockers.append({**action, "blocking_reason": "external action remains dry-run/proposed"})
    return _answer_with_items(question, "Planning is blocked only by proposal approval gates in local state.", blockers)


def _answer_external_actions(question: str, store: LocalStateStore) -> dict[str, Any]:
    actions = store.list_objects("external_action_proposal")
    answer = "External action proposals are tracked as dry-run/proposal objects only; no external writes are performed."
    return _answer_with_items(question, answer, actions)


def _answer_numbered_object(question: str, store: LocalStateStore, object_type: str) -> dict[str, Any]:
    number = _extract_last_int(question)
    if number is None:
        return _base_answer(question, f"No {object_type.replace('_', ' ')} number was found in the question.", [])
    matches = [item for item in store.list_objects(object_type) if item.get("number") == number]
    if not matches:
        return _base_answer(question, f"No {object_type.replace('_', ' ')} {number} is tracked in local state.", [])
    item = matches[0]
    answer = f"{object_type.replace('_', ' ').title()} {number}: {item.get('title')} ({item.get('status')})."
    if object_type == "pull_request":
        findings = [
            finding
            for finding in store.list_objects("review_finding")
            if finding.get("pr_external_key") == item.get("external_key")
        ]
        item = {**item, "review_findings": findings}
    return _base_answer(question, answer, [item])


def _extract_last_int(value: str) -> int | None:
    current = ""
    found: list[int] = []
    for char in value:
        if char.isdigit():
            current += char
        elif current:
            found.append(int(current))
            current = ""
    if current:
        found.append(int(current))
    return found[-1] if found else None


def _answer_status(question: str, store: LocalStateStore) -> dict[str, Any]:
    summary = store.get_summary("repo_manager_status") or {}
    counts = store.object_counts()
    item = {
        "mode": summary.get("mode", "local_state"),
        "read_only": summary.get("read_only", True),
        "external_write_performed": summary.get("external_write_performed", False),
        "github_write_count": summary.get("github_write_count", 0),
        "live_llm_call_count": summary.get("live_llm_call_count", 0),
        "object_counts": counts,
    }
    return _base_answer(
        question,
        "Repo manager is operating from local state only: offline, read-only, and with zero live LLM calls.",
        [item],
    )


def _answer_safe_to_run(question: str) -> dict[str, Any]:
    items = [{"command": command, "network_required": False, "external_write": False} for command in SAFE_TO_RUN_COMMANDS]
    return _base_answer(
        question,
        "These commands are safe offline/keyless paths and do not perform external writes.",
        items,
    )
