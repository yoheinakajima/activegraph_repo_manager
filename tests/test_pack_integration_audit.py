import ast
import importlib
import json
import pkgutil
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "activegraph_repo_manager"
BEHAVIOR_ROOT = PACKAGE_ROOT / "behaviors"
TOOL_ROOT = PACKAGE_ROOT / "tools"
PROMPT_ROOT = PACKAGE_ROOT / "prompts"
FIXTURE_ROOT = PACKAGE_ROOT / "fixtures"

BEHAVIOR_FORBIDDEN_TOKENS = (
    "datetime.now",
    "date.today",
    "random",
    "uuid.uuid4",
    "subprocess",
    "requests",
    "httpx",
    "urllib",
    "socket",
    "open(",
    "Path.read_text",
    "Path.write_text",
    "write_text(",
    "read_text(",
    "os.environ",
    "getenv(",
    "OpenAI(",
)

TOOL_IMPORT_SIDE_EFFECT_TOKENS = (
    "requests.",
    "httpx.",
    "urllib.request",
    "socket.",
    "subprocess.",
    "os.environ",
    "getenv(",
    "Path.write_text",
    "write_text(",
    "open(",
    "OpenAI(",
)

SECRET_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "secret",
    "password",
    "private_key",
    "authorization",
}

PROMPT_EXTERNAL_WRITE_PATTERNS = (
    re.compile(r"\bpost\s+(?:a\s+)?(?:github\s+)?comment\b"),
    re.compile(r"\bapply\s+(?:github\s+)?labels?\b"),
    re.compile(r"\brequest\s+changes\b"),
    re.compile(r"\bapprove\s+(?:the\s+)?(?:github\s+)?pr\b"),
    re.compile(r"\bopen\s+(?:a\s+)?(?:github\s+)?issues?\b"),
    re.compile(r"\bopen\s+(?:a\s+)?(?:github\s+)?pull\s+requests?\b"),
    re.compile(r"\bcreate\s+(?:a\s+)?(?:github\s+)?issues?\b"),
    re.compile(r"\bcreate\s+(?:a\s+)?(?:github\s+)?pull\s+requests?\b"),
    re.compile(r"\bwrite\s+(?:to\s+)?(?:github|files?|the\s+filesystem)\b"),
)




def _class_names_from_source(path: Path, *, exclude: set[str] | None = None) -> set[str]:
    exclude = exclude or set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name not in exclude
    }


def _enum_values_from_source(path: Path, enum_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == enum_name:
            values: set[str] = set()
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
                    if isinstance(stmt.value.value, str):
                        values.add(stmt.value.value)
            return values
    raise AssertionError(f"Enum {enum_name} not found")


def _class_field_defaults_from_source(path: Path, class_name: str) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            defaults: dict[str, Any] = {}
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    if stmt.value is None:
                        continue
                    try:
                        defaults[stmt.target.id] = ast.literal_eval(stmt.value)
                    except (ValueError, SyntaxError):
                        if isinstance(stmt.value, ast.Attribute):
                            defaults[stmt.target.id] = stmt.value.attr
                        elif isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name):
                            defaults[stmt.target.id] = stmt.value.func.id
            return defaults
    raise AssertionError(f"Class {class_name} not found")

def _module_names(root: Path, package: str) -> list[str]:
    return sorted(
        f"{package}.{module.name}"
        for module in pkgutil.iter_modules([str(root)])
        if not module.ispkg
    )


def _resolve_dotted(dotted_path: str) -> Any:
    module_name, attr_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def _walk_json(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    findings: list[tuple[tuple[str, ...], Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = (*path, str(key))
            if str(key).lower() in SECRET_KEYS:
                findings.append((child_path, child))
            findings.extend(_walk_json(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_walk_json(child, (*path, str(index))))
    return findings


def _is_negated_prompt_line(line: str) -> bool:
    stripped = line.strip().lower().lstrip("- ")
    return stripped.startswith(("do not ", "never ", "must not ", "don't "))


def test_package_and_pack_import_cleanly() -> None:
    assert importlib.import_module("activegraph_repo_manager") is not None
    pack_module = importlib.import_module("activegraph_repo_manager.pack")
    assert getattr(pack_module, "pack") is not None


def test_every_behavior_module_imports_and_exposes_behaviors_convention() -> None:
    modules = _module_names(BEHAVIOR_ROOT, "activegraph_repo_manager.behaviors")
    registry = importlib.import_module("activegraph_repo_manager.behaviors").behaviors
    assert set(modules) == set(registry)

    for module_name in modules:
        module = importlib.import_module(module_name)
        assert hasattr(module, "behaviors"), module_name
        assert isinstance(module.behaviors, tuple), module_name


def test_every_tool_module_imports_and_exposes_tools_convention() -> None:
    modules = _module_names(TOOL_ROOT, "activegraph_repo_manager.tools")
    registry = importlib.import_module("activegraph_repo_manager.tools").tools
    assert set(modules) == set(registry)

    for module_name in modules:
        module = importlib.import_module(module_name)
        assert hasattr(module, "tools"), module_name
        assert isinstance(module.tools, tuple), module_name


def test_behavior_modules_do_not_contain_forbidden_io_or_nondeterminism_tokens() -> None:
    for path in sorted(BEHAVIOR_ROOT.glob("*.py")):
        if path.name == "__init__.py":
            continue
        content = path.read_text(encoding="utf-8")
        for token in BEHAVIOR_FORBIDDEN_TOKENS:
            assert token not in content, f"Forbidden token {token!r} in {path}"


def test_tool_modules_avoid_import_time_credential_network_and_file_write_patterns() -> None:
    for path in sorted(TOOL_ROOT.glob("*.py")):
        if path.name == "__init__.py":
            continue
        content = path.read_text(encoding="utf-8")
        module_ast = ast.parse(content)
        module_body_nodes = [
            node
            for node in module_ast.body
            if not isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom,
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
        ]
        module_body = "\n".join(ast.get_source_segment(content, node) or "" for node in module_body_nodes)
        for token in TOOL_IMPORT_SIDE_EFFECT_TOKENS:
            assert token not in module_body, f"Import-time side-effect token {token!r} in {path}"


def test_prompt_files_exist_are_versioned_and_do_not_instruct_external_writes() -> None:
    pack = importlib.import_module("activegraph_repo_manager.pack").pack
    prompt_files = sorted(PROMPT_ROOT.glob("*.v1.md"))
    assert prompt_files
    assert tuple(path.name for path in prompt_files) == tuple(sorted(pack.prompt_files))

    for path in prompt_files:
        assert path.name.endswith(".v1.md"), path
        text = path.read_text(encoding="utf-8").lower()
        for line in text.splitlines():
            if _is_negated_prompt_line(line):
                continue
            for pattern in PROMPT_EXTERNAL_WRITE_PATTERNS:
                assert not pattern.search(line), f"External-write instruction in {path}: {line}"


def test_fixture_json_files_parse_and_contain_no_obvious_secret_keys() -> None:
    fixture_files = sorted(FIXTURE_ROOT.glob("*.json"))
    assert fixture_files
    pack = importlib.import_module("activegraph_repo_manager.pack").pack
    assert tuple(path.name for path in fixture_files) == tuple(sorted(pack.fixture_files))

    for path in fixture_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        secret_key_findings = _walk_json(payload)
        assert secret_key_findings == [], f"Secret-like keys in {path}: {secret_key_findings}"


def test_settings_defaults_keep_external_writes_disabled_and_dry_run_enabled() -> None:
    defaults = _class_field_defaults_from_source(PACKAGE_ROOT / "settings.py", "RepoManagerSettings")
    assert defaults["enable_external_writes"] is False
    assert defaults["enable_github_write_tools"] is False
    assert defaults["enable_file_write_tools"] is False
    assert defaults["require_approval_for_external_actions"] is True
    assert defaults["dry_run_external_actions"] is True
    assert defaults["enable_llm_classification"] is False
    assert defaults["enable_pr_review"] is False


def test_planning_and_external_action_proposals_remain_approval_grade() -> None:
    schema_path = PACKAGE_ROOT / "schemas.py"
    planning_defaults = _class_field_defaults_from_source(schema_path, "PlanningPatchProposal")
    external_defaults = _class_field_defaults_from_source(schema_path, "ExternalActionProposal")
    assert planning_defaults["status"] == "proposed"
    assert external_defaults["status"] == "proposed"

    policy_module = importlib.import_module("activegraph_repo_manager.policies")
    assert policy_module.PLANNING_PATCH_APPROVAL_POLICY.approval_required is True
    assert policy_module.EXTERNAL_ACTION_APPROVAL_POLICY.approval_required is True

    schema_action_values = _enum_values_from_source(schema_path, "ExternalActionType")
    assert policy_module.ALLOWED_EXTERNAL_ACTION_TYPES == frozenset(schema_action_values)


def test_pack_manifest_references_importable_known_schemas_relations_tools_and_behaviors() -> None:
    pack_module = importlib.import_module("activegraph_repo_manager.pack")
    pack = pack_module.pack

    assert pack.name == "activegraph_repo_manager"
    assert pack.settings_schema == "activegraph_repo_manager.settings.RepoManagerSettings"
    assert "RepoManagerSettings" in _class_names_from_source(PACKAGE_ROOT / "settings.py")

    schema_model_names = _class_names_from_source(
        PACKAGE_ROOT / "schemas.py",
        exclude={
            "StrictModel",
            "ExternalObject",
            "PlanningPatchTarget",
            "EvidenceRef",
            "WorkType",
            "Scope",
            "Risk",
            "PlanningPriority",
            "TriageUrgency",
            "LifecycleStatus",
            "ReviewSeverity",
            "ReviewCategory",
            "ProposalStatus",
            "PlanningChangeType",
            "ExternalActionType",
        },
    )
    pack_schema_names = {path.rsplit(".", 1)[1] for path in pack.schema_types}
    assert pack_schema_names == schema_model_names

    relations_module = importlib.import_module("activegraph_repo_manager.relations")
    relation_constants = {
        value
        for name, value in vars(relations_module).items()
        if name.isupper() and name != "RELATIONS" and isinstance(value, str)
    }
    assert set(pack.relations) == relation_constants

    for module_name in pack.behavior_modules:
        assert hasattr(importlib.import_module(module_name), "behaviors")
    for module_name in pack.tool_modules:
        assert hasattr(importlib.import_module(module_name), "tools")
    for dotted_path in pack.policies:
        assert _resolve_dotted(dotted_path).approval_required is True

    prompt_names = {path.name for path in PROMPT_ROOT.glob("*.v1.md")}
    fixture_names = {path.name for path in FIXTURE_ROOT.glob("*.json")}
    assert set(pack.prompt_files) == prompt_names
    assert set(pack.fixture_files) == fixture_names


def test_recorded_fixture_enum_values_match_schemas() -> None:
    schema_path = PACKAGE_ROOT / "schemas.py"
    classification_fixtures = [
        json.loads((FIXTURE_ROOT / "llm_issue_classification.v1.json").read_text(encoding="utf-8")),
        json.loads((FIXTURE_ROOT / "llm_pr_classification.v1.json").read_text(encoding="utf-8")),
    ]
    for payload in classification_fixtures:
        assert payload["work_type"] in _enum_values_from_source(schema_path, "WorkType")
        assert payload["scope"] in _enum_values_from_source(schema_path, "Scope")
        assert payload["risk"] in _enum_values_from_source(schema_path, "Risk")
        assert payload["planning_priority"] in _enum_values_from_source(schema_path, "PlanningPriority")
        assert payload["triage_urgency"] in _enum_values_from_source(schema_path, "TriageUrgency")
        assert payload["lifecycle_status"] in _enum_values_from_source(schema_path, "LifecycleStatus")

    planning_fixture = json.loads(
        (FIXTURE_ROOT / "llm_planning_decider.v1.json").read_text(encoding="utf-8")
    )
    proposal_status_values = _enum_values_from_source(schema_path, "ProposalStatus")
    planning_change_values = _enum_values_from_source(schema_path, "PlanningChangeType")
    for proposal in planning_fixture.values():
        assert proposal["status"] in proposal_status_values
        assert proposal["change_type"] in planning_change_values
        assert proposal["rationale"]
        assert proposal["caused_by_event_id"]
        assert proposal["proposed_by_behavior"]

    repo_fixture = json.loads((FIXTURE_ROOT / "repo_snapshot_minimal.json").read_text(encoding="utf-8"))
    assert repo_fixture["repository"]["external_key"].startswith("gh:repo:")
    for item in repo_fixture["repo_snapshot"]["files"]:
        assert set(item) <= {"path", "language", "size_bytes"}
