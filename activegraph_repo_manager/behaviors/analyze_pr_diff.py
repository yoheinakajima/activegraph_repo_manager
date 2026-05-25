"""Deterministic PR diff analysis for contract-sensitive surfaces."""

from __future__ import annotations

from typing import Any

CONTRACT_PATH_PREFIXES: tuple[tuple[str, str], ...] = (
    ("activegraph/runtime/", "runtime behavior surface"),
    ("activegraph/store/", "store backend surface"),
    ("activegraph/events/", "event log semantics surface"),
    ("activegraph/packs/", "pack API surface"),
    ("activegraph/tools/", "tooling/operator surface"),
    ("activegraph/llm/", "LLM integration surface"),
    ("activegraph/observability/", "observability/trace surface"),
)

CONTRACT_EXACT_PATHS: tuple[tuple[str, str], ...] = (
    ("activegraph/graph.py", "public graph API surface"),
    ("activegraph/views.py", "public views API surface"),
    ("docs/concepts/events.md", "event semantics contract doc"),
    ("docs/concepts/replay.md", "replay contract doc"),
    ("docs/concepts/forking.md", "forking contract doc"),
    ("docs/concepts/policies.md", "policy lifecycle contract doc"),
    ("docs/concepts/patterns.md", "pattern contract doc"),
    ("docs/guides/authoring-packs.md", "pack authoring contract doc"),
    ("CONTRACT.md", "top-level contract doc"),
    ("CHANGELOG.md", "public change log surface"),
    ("pyproject.toml", "public package/API surface"),
)

SEMANTIC_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("event", "event semantics keyword"),
    ("replay", "replay semantics keyword"),
    ("fork", "fork semantics keyword"),
    ("store", "store backend keyword"),
    ("policy", "policy lifecycle keyword"),
    ("approval", "approval lifecycle keyword"),
    ("trace", "trace format keyword"),
)


def _match_contract_reasons(path: str) -> list[str]:
    reasons: list[str] = []
    for prefix, reason in CONTRACT_PATH_PREFIXES:
        if path.startswith(prefix):
            reasons.append(reason)
    for exact_path, reason in CONTRACT_EXACT_PATHS:
        if path == exact_path:
            reasons.append(reason)
    normalized = path.lower()
    for keyword, reason in SEMANTIC_KEYWORDS:
        if keyword in normalized:
            reasons.append(reason)
    deduped: list[str] = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)
    return deduped


def analyze_pr_diff(pr_diff: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic semantic change analysis and evidence refs."""
    changed_files = [str(path) for path in pr_diff.get("files_changed", [])]
    evidence_refs: list[dict[str, str]] = []
    semantic_reasons: list[str] = []
    sensitive_paths: list[str] = []

    for path in sorted(changed_files):
        reasons = _match_contract_reasons(path)
        if reasons:
            sensitive_paths.append(path)
            for reason in reasons:
                if reason not in semantic_reasons:
                    semantic_reasons.append(reason)
            evidence_refs.append(
                {
                    "source": "pr_diff",
                    "locator": path,
                    "note": "; ".join(reasons),
                }
            )

    return {
        "pr_external_key": pr_diff.get("pull_request_external_key", ""),
        "changed_files": sorted(changed_files),
        "is_contract_sensitive": bool(sensitive_paths),
        "sensitive_paths": sensitive_paths,
        "semantic_reasons": semantic_reasons,
        "evidence_refs": evidence_refs,
    }


behaviors = ()
