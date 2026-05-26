"""Phase 0 idempotent ingest helpers for deterministic fixture-sourced GitHub data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

behaviors = ()


@dataclass
class InMemoryExternalStore:
    """Minimal store used by tests to verify idempotent ingest semantics."""

    records: dict[str, dict[str, Any]]

    def __init__(self) -> None:
        self.records = {}

    def find_by_external_key(self, external_key: str) -> dict[str, Any] | None:
        return self.records.get(external_key)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = dict(payload)
        self.records[payload["external_key"]] = record
        return record

    def patch(self, external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.records[external_key]
        current.update(payload)
        return current


@dataclass(frozen=True)
class IngestResult:
    object_type: str
    external_key: str
    action: str


def _require_fields(payload: dict[str, Any], required_fields: tuple[str, ...]) -> None:
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


def patch_or_create_external(
    store: InMemoryExternalStore,
    *,
    external_key: str,
    payload: dict[str, Any],
    object_type: str,
) -> IngestResult:
    """Idempotent find-by-external-key patch-or-create helper."""

    existing = store.find_by_external_key(external_key)
    if existing is None:
        store.create(payload)
        return IngestResult(object_type=object_type, external_key=external_key, action="created")
    store.patch(external_key, payload)
    return IngestResult(object_type=object_type, external_key=external_key, action="patched")


def ingest_repository(store: InMemoryExternalStore, payload: dict[str, Any]) -> IngestResult:
    _require_fields(payload, ("external_key", "source", "owner", "name", "default_branch"))
    return patch_or_create_external(
        store,
        external_key=payload["external_key"],
        payload=dict(payload),
        object_type="Repository",
    )


def ingest_issue(store: InMemoryExternalStore, payload: dict[str, Any]) -> IngestResult:
    _require_fields(payload, ("external_key", "source", "number", "title", "status"))
    return patch_or_create_external(
        store,
        external_key=payload["external_key"],
        payload=dict(payload),
        object_type="Issue",
    )


def ingest_pull_request(store: InMemoryExternalStore, payload: dict[str, Any]) -> IngestResult:
    _require_fields(
        payload,
        ("external_key", "source", "number", "title", "status", "base_branch", "head_branch"),
    )
    return patch_or_create_external(
        store,
        external_key=payload["external_key"],
        payload=dict(payload),
        object_type="PullRequest",
    )


def ingest_pr_diff(store: InMemoryExternalStore, payload: dict[str, Any]) -> IngestResult:
    _require_fields(payload, ("external_key", "source", "pull_request_external_key"))
    return patch_or_create_external(
        store,
        external_key=payload["external_key"],
        payload=dict(payload),
        object_type="PRDiff",
    )


def ingest_check_run(store: InMemoryExternalStore, payload: dict[str, Any]) -> IngestResult:
    _require_fields(payload, ("external_key", "source", "name", "status"))
    return patch_or_create_external(
        store,
        external_key=payload["external_key"],
        payload=dict(payload),
        object_type="CheckRun",
    )


def normalize_github_repository(payload: dict[str, Any]) -> dict[str, Any]:
    owner = payload["owner"]["login"]
    name = payload["name"]
    return {
        "external_key": f"gh:repo:{owner}/{name}",
        "source": "github",
        "owner": owner,
        "name": name,
        "default_branch": payload["default_branch"],
        "external_metadata": {
            "private": bool(payload.get("private", False)),
            "html_url": payload.get("html_url"),
        },
    }


def normalize_github_issue(payload: dict[str, Any], *, owner: str, repo: str) -> dict[str, Any]:
    return {
        "external_key": f"gh:issue:{owner}/{repo}#{payload['number']}",
        "source": "github",
        "number": payload["number"],
        "title": payload["title"],
        "status": payload["state"],
        "external_metadata": {
            "html_url": payload.get("html_url"),
            "labels": [label.get("name") for label in payload.get("labels", [])],
        },
    }


def normalize_github_pull_request(payload: dict[str, Any], *, owner: str, repo: str) -> dict[str, Any]:
    return {
        "external_key": f"gh:pr:{owner}/{repo}#{payload['number']}",
        "source": "github",
        "number": payload["number"],
        "title": payload["title"],
        "status": payload["state"],
        "base_branch": payload["base"]["ref"],
        "head_branch": payload["head"]["ref"],
        "external_metadata": {
            "head_sha": payload["head"]["sha"],
            "html_url": payload.get("html_url"),
        },
    }


def normalize_github_pr_files(
    payload: list[dict[str, Any]], *, owner: str, repo: str, pr_number: int, head_sha: str
) -> dict[str, Any]:
    return {
        "external_key": f"gh:prdiff:{owner}/{repo}#{pr_number}:{head_sha}",
        "source": "github",
        "pull_request_external_key": f"gh:pr:{owner}/{repo}#{pr_number}",
        "external_metadata": {
            "commit_external_key": f"gh:commit:{owner}/{repo}@{head_sha}",
            "files": [
                {
                    "filename": f.get("filename"),
                    "status": f.get("status"),
                    "additions": int(f.get("additions", 0)),
                    "deletions": int(f.get("deletions", 0)),
                }
                for f in payload
            ],
        },
    }


def normalize_github_check_run(
    payload: dict[str, Any], *, owner: str, repo: str, pr_number: int, head_sha: str
) -> dict[str, Any]:
    provider = payload.get("app", {}).get("slug", "unknown")
    name = payload["name"]
    return {
        "external_key": f"gh:check:{owner}/{repo}#{pr_number}:{provider}:{name}:{head_sha}",
        "source": "github",
        "name": name,
        "status": payload["status"],
        "conclusion": payload.get("conclusion"),
        "external_metadata": {
            "provider": provider,
            "head_sha": head_sha,
        },
    }
