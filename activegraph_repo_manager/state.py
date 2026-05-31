"""SQLite-backed local state for the repo-governance pack command surface."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

SUPPORTED_OBJECT_TYPES = (
    "repository",
    "issue",
    "pull_request",
    "repo_file",
    "symbol",
    "test_surface",
    "review_finding",
    "planning_patch_proposal",
    "external_action_proposal",
    "check_run",
    "pr_diff",
    "planning_item",
)

SUPPORTED_OBJECT_TYPE_SET = frozenset(SUPPORTED_OBJECT_TYPES)
DEFAULT_STATE_PATH = Path(".activegraph_repo_manager") / "state.sqlite3"


GITHUB_EXTERNAL_KEY_OBJECT_TYPES = (
    ("gh:prdiff:", "pr_diff"),
    ("gh:check:", "check_run"),
    ("gh:repo:", "repository"),
    ("gh:issue:", "issue"),
    ("gh:pr:", "pull_request"),
)


def github_object_type_from_external_key(external_key: str) -> str:
    for prefix, object_type in GITHUB_EXTERNAL_KEY_OBJECT_TYPES:
        if external_key.startswith(prefix):
            return object_type
    raise ValueError(f"Unsupported GitHub external_key for local state ingest: {external_key}")


class LocalStateIngestAdapter:
    """Adapter that lets idempotent ingest helpers persist into LocalStateStore."""

    def __init__(self, store: "LocalStateStore") -> None:
        self.store = store

    def find_by_external_key(self, external_key: str) -> dict[str, Any] | None:
        return self.store.get_object(github_object_type_from_external_key(external_key), external_key)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        external_key = _external_key_from_payload(payload)
        object_type = github_object_type_from_external_key(external_key)
        return self.store.upsert_object(object_type, dict(payload))

    def patch(self, external_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        object_type = github_object_type_from_external_key(external_key)
        existing = self.store.get_object(object_type, external_key) or {}
        return self.store.upsert_object(object_type, {**existing, **dict(payload)})


def _external_key_from_payload(payload: dict[str, Any]) -> str:
    external_key = payload.get("external_key")
    if not isinstance(external_key, str) or not external_key:
        raise ValueError("payload must include a non-empty external_key")
    return external_key


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _decode_json(payload_json: str) -> dict[str, Any]:
    decoded = json.loads(payload_json)
    if not isinstance(decoded, dict):
        raise ValueError("state payload must decode to a JSON object")
    return decoded


def _require_supported_object_type(object_type: str) -> None:
    if object_type not in SUPPORTED_OBJECT_TYPE_SET:
        raise ValueError(f"Unsupported object type: {object_type}")


class LocalStateStore:
    """Small deterministic SQLite store for local, offline repo-manager state."""

    def __init__(self, path: str | Path = DEFAULT_STATE_PATH) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._initialize_schema()

    @classmethod
    def in_memory(cls) -> "LocalStateStore":
        return cls(":memory:")

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "LocalStateStore":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _initialize_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS objects (
                object_type TEXT NOT NULL,
                external_key TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (object_type, external_key)
            );
            CREATE INDEX IF NOT EXISTS idx_objects_type_key
                ON objects (object_type, external_key);

            CREATE TABLE IF NOT EXISTS relations (
                relation_type TEXT NOT NULL,
                relation_key TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (relation_type, relation_key)
            );
            CREATE INDEX IF NOT EXISTS idx_relations_type_key
                ON relations (relation_type, relation_key);

            CREATE TABLE IF NOT EXISTS summaries (
                summary_key TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            """
        )
        self._connection.commit()

    def upsert_object(self, object_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        _require_supported_object_type(object_type)
        external_key = payload.get("external_key")
        if not isinstance(external_key, str) or not external_key:
            raise ValueError("object payload must include a non-empty external_key")
        stored = dict(payload)
        self._connection.execute(
            """
            INSERT INTO objects (object_type, external_key, payload_json)
            VALUES (?, ?, ?)
            ON CONFLICT(object_type, external_key) DO UPDATE SET
                payload_json = excluded.payload_json
            """,
            (object_type, external_key, _canonical_json(stored)),
        )
        self._connection.commit()
        return stored

    def get_object(self, object_type: str, external_key: str) -> dict[str, Any] | None:
        _require_supported_object_type(object_type)
        row = self._connection.execute(
            """
            SELECT payload_json FROM objects
            WHERE object_type = ? AND external_key = ?
            """,
            (object_type, external_key),
        ).fetchone()
        if row is None:
            return None
        return _decode_json(str(row["payload_json"]))

    def list_objects(self, object_type: str) -> list[dict[str, Any]]:
        _require_supported_object_type(object_type)
        rows = self._connection.execute(
            """
            SELECT payload_json FROM objects
            WHERE object_type = ?
            ORDER BY external_key ASC
            """,
            (object_type,),
        ).fetchall()
        return [_decode_json(str(row["payload_json"])) for row in rows]

    def count_objects_by_type(self, object_type: str) -> int:
        _require_supported_object_type(object_type)
        row = self._connection.execute(
            "SELECT COUNT(*) AS count FROM objects WHERE object_type = ?",
            (object_type,),
        ).fetchone()
        return int(row["count"])

    def object_counts(self) -> dict[str, int]:
        return {object_type: self.count_objects_by_type(object_type) for object_type in SUPPORTED_OBJECT_TYPES}

    def upsert_relation(
        self,
        relation_type: str,
        payload: dict[str, Any],
        relation_key: str | None = None,
    ) -> dict[str, Any]:
        if not relation_type:
            raise ValueError("relation_type must be non-empty")
        stored = dict(payload)
        stable_key = relation_key or stored.get("external_key") or self._derive_relation_key(relation_type, stored)
        if not isinstance(stable_key, str) or not stable_key:
            raise ValueError("relation key must be non-empty")
        self._connection.execute(
            """
            INSERT INTO relations (relation_type, relation_key, payload_json)
            VALUES (?, ?, ?)
            ON CONFLICT(relation_type, relation_key) DO UPDATE SET
                payload_json = excluded.payload_json
            """,
            (relation_type, stable_key, _canonical_json(stored)),
        )
        self._connection.commit()
        return stored

    def list_relations(self, relation_type: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT payload_json FROM relations
            WHERE relation_type = ?
            ORDER BY relation_key ASC
            """,
            (relation_type,),
        ).fetchall()
        return [_decode_json(str(row["payload_json"])) for row in rows]

    def upsert_summary(self, summary_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not summary_key:
            raise ValueError("summary_key must be non-empty")
        stored = dict(payload)
        self._connection.execute(
            """
            INSERT INTO summaries (summary_key, payload_json)
            VALUES (?, ?)
            ON CONFLICT(summary_key) DO UPDATE SET
                payload_json = excluded.payload_json
            """,
            (summary_key, _canonical_json(stored)),
        )
        self._connection.commit()
        return stored

    def get_summary(self, summary_key: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT payload_json FROM summaries WHERE summary_key = ?",
            (summary_key,),
        ).fetchone()
        if row is None:
            return None
        return _decode_json(str(row["payload_json"]))

    def list_summaries(self) -> dict[str, dict[str, Any]]:
        rows = self._connection.execute(
            "SELECT summary_key, payload_json FROM summaries ORDER BY summary_key ASC"
        ).fetchall()
        return {str(row["summary_key"]): _decode_json(str(row["payload_json"])) for row in rows}

    def deterministic_snapshot(self) -> dict[str, Any]:
        return {
            "objects": {
                object_type: self.list_objects(object_type)
                for object_type in SUPPORTED_OBJECT_TYPES
                if self.count_objects_by_type(object_type) > 0
            },
            "relations": self._relation_snapshot(),
            "summaries": self.list_summaries(),
        }

    def _relation_snapshot(self) -> dict[str, list[dict[str, Any]]]:
        rows = self._connection.execute(
            "SELECT DISTINCT relation_type FROM relations ORDER BY relation_type ASC"
        ).fetchall()
        return {str(row["relation_type"]): self.list_relations(str(row["relation_type"])) for row in rows}

    @staticmethod
    def _derive_relation_key(relation_type: str, payload: dict[str, Any]) -> str:
        encoded = _canonical_json(payload)
        digest = hashlib.sha256(f"{relation_type}:{encoded}".encode("utf-8")).hexdigest()
        return f"{relation_type}:{digest}"
