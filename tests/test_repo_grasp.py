import json
from pathlib import Path

from activegraph_repo_manager.behaviors.ingest_github import (
    InMemoryExternalStore,
    patch_or_create_external,
)
from activegraph_repo_manager.tools.repo_index import (
    build_repo_snapshot_from_fixture,
    derive_repo_file_external_key,
    derive_repo_snapshot_external_key,
    derive_symbol_external_key,
    derive_test_surface_external_key,
    detect_file_role,
    infer_test_surfaces,
    parse_python_symbols,
)

FIXTURE_ROOT = Path("activegraph_repo_manager/fixtures")


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_repo_snapshot_fixture_derives_stable_snapshot_data() -> None:
    fixture = _load_fixture("repo_snapshot_minimal.json")["repo_snapshot"]
    snapshot = build_repo_snapshot_from_fixture(fixture)

    expected_key = derive_repo_snapshot_external_key(
        fixture["repository_external_key"], fixture["snapshot_id"]
    )
    assert snapshot["external_key"] == expected_key
    assert snapshot["commit_sha"] == fixture["commit_sha"]
    assert snapshot["external_metadata"]["snapshot_id"] == "fixture-main-001"


def test_repo_file_external_keys_are_stable_and_usable_for_patch_or_create() -> None:
    fixture = _load_fixture("repo_snapshot_minimal.json")["repo_snapshot"]
    repository_key = fixture["repository_external_key"]
    path = fixture["files"][0]["path"]
    external_key = derive_repo_file_external_key(repository_key, path)

    store = InMemoryExternalStore()
    first = patch_or_create_external(
        store,
        external_key=external_key,
        payload={"external_key": external_key, "path": path, "source": "repo_fixture"},
        object_type="RepoFile",
    )
    second = patch_or_create_external(
        store,
        external_key=external_key,
        payload={"external_key": external_key, "path": path, "source": "repo_fixture"},
        object_type="RepoFile",
    )

    assert first.action == "created"
    assert second.action == "patched"
    assert len(store.records) == 1


def test_file_role_detector_classifies_docs_tests_runtime_and_config() -> None:
    assert detect_file_role("docs/codex/project_brief.md") == "docs"
    assert detect_file_role("tests/test_repo_grasp.py") == "tests"
    assert detect_file_role("activegraph_repo_manager/tools/repo_index.py") == "runtime"
    assert detect_file_role("pyproject.toml") == "config"


def test_python_ast_parser_extracts_class_function_and_method_symbols() -> None:
    source = '''"""module doc"""

CONSTANT = 5

def helper():
    """helper doc"""
    return CONSTANT

class Service:
    """service doc"""

    def run(self):
        """run doc"""
        return helper()
'''
    symbols = parse_python_symbols(source)
    by_kind = {(item.kind, item.qualified_name): item for item in symbols}

    assert ("module", "<module>") in by_kind
    assert ("function", "helper") in by_kind
    assert ("class", "Service") in by_kind
    assert ("method", "Service.run") in by_kind
    assert ("constant", "CONSTANT") in by_kind
    assert by_kind[("method", "Service.run")].line_start is not None


def test_public_api_heuristic_is_conservative_and_deterministic() -> None:
    source = '''def public_fn():
    return 1

def _private_fn():
    return 0

class PublicClass:
    def api(self):
        return 1

    def _internal(self):
        return 0

class _HiddenClass:
    def visible_name(self):
        return 1
'''
    symbols = parse_python_symbols(source)
    flags = {item.qualified_name: item.public_api for item in symbols}

    assert flags["public_fn"] is True
    assert flags["_private_fn"] is False
    assert flags["PublicClass"] is True
    assert flags["PublicClass.api"] is True
    assert flags["PublicClass._internal"] is False
    assert flags["_HiddenClass"] is False
    assert flags["_HiddenClass.visible_name"] is False


def test_testsurface_inference_links_test_file_to_likely_target() -> None:
    files = [
        "activegraph_repo_manager/tools/repo_index.py",
        "tests/test_repo_grasp.py",
        "tests/test_ingest_idempotency.py",
    ]
    surfaces = infer_test_surfaces(files)

    assert len(surfaces) >= 1
    assert any(item["likely_target"] == "repo_grasp.py" for item in surfaces)
    ts_external_key = derive_test_surface_external_key(
        "gh:repo:yoheinakajima/activegraph",
        "tests/test_repo_grasp.py",
        "repo_grasp.py",
    )
    symbol_key = derive_symbol_external_key(
        "gh:repo:yoheinakajima/activegraph",
        "activegraph_repo_manager/tools/repo_index.py",
        "function",
        "parse_python_symbols",
    )
    assert ts_external_key.startswith("gh:repo:yoheinakajima/activegraph:testsurface:")
    assert symbol_key.endswith(":function:parse_python_symbols")
