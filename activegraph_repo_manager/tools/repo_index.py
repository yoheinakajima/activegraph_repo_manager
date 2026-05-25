"""Deterministic offline repo indexing helpers for Phase 1 repo grasp."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import PurePosixPath


def derive_repo_snapshot_external_key(repository_external_key: str, snapshot_id: str) -> str:
    """Build stable RepoSnapshot external key from repository key + snapshot id."""

    return f"{repository_external_key}:snapshot:{snapshot_id}"


def derive_repo_file_external_key(repository_external_key: str, file_path: str) -> str:
    """Build stable RepoFile external key from repository key + normalized file path."""

    normalized = str(PurePosixPath(file_path))
    return f"{repository_external_key}:file:{normalized}"


def derive_symbol_external_key(
    repository_external_key: str,
    file_path: str,
    symbol_kind: str,
    qualified_name: str,
) -> str:
    """Build stable Symbol external key from path/kind/qualified name."""

    normalized = str(PurePosixPath(file_path))
    return f"{repository_external_key}:symbol:{normalized}:{symbol_kind}:{qualified_name}"


def derive_test_surface_external_key(
    repository_external_key: str,
    test_file_path: str,
    target_hint: str,
) -> str:
    """Build stable TestSurface external key from test path + target hint."""

    normalized = str(PurePosixPath(test_file_path))
    return f"{repository_external_key}:testsurface:{normalized}:{target_hint}"


def detect_file_role(path: str) -> str:
    """Classify repository file role using deterministic path heuristics."""

    normalized = str(PurePosixPath(path)).lower()
    p = PurePosixPath(normalized)
    parts = p.parts
    name = p.name

    if "tests" in parts or name.startswith("test_"):
        return "tests"
    if normalized.startswith("docs/") or name.endswith(".md") or "doc" in parts:
        return "docs"
    if "examples" in parts:
        return "examples"
    if normalized.startswith(".github/workflows/"):
        return "ci"
    if name in {"pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "ruff.toml"}:
        return "config"
    if name in {"pack.py", "settings.py", "relations.py", "policies.py"}:
        return "pack"
    if "store" in parts:
        return "store"
    if name.endswith(".py"):
        return "runtime"
    return "unknown"


@dataclass(frozen=True)
class ParsedSymbol:
    name: str
    kind: str
    qualified_name: str
    line_start: int | None
    line_end: int | None
    docstring: str | None
    public_api: bool


class _ModuleVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbols: list[ParsedSymbol] = []
        self.module_docstring: str | None = None

    def visit_Module(self, node: ast.Module) -> None:  # noqa: N802
        self.module_docstring = ast.get_docstring(node)
        self.symbols.append(
            ParsedSymbol(
                name="<module>",
                kind="module",
                qualified_name="<module>",
                line_start=getattr(node, "lineno", None),
                line_end=getattr(node, "end_lineno", None),
                docstring=self.module_docstring,
                public_api=True,
            )
        )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        class_public = not node.name.startswith("_")
        self.symbols.append(
            ParsedSymbol(
                name=node.name,
                kind="class",
                qualified_name=node.name,
                line_start=getattr(node, "lineno", None),
                line_end=getattr(node, "end_lineno", None),
                docstring=ast.get_docstring(node),
                public_api=class_public,
            )
        )
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                method_name = f"{node.name}.{child.name}"
                method_public = class_public and not child.name.startswith("_")
                self.symbols.append(
                    ParsedSymbol(
                        name=child.name,
                        kind="method",
                        qualified_name=method_name,
                        line_start=getattr(child, "lineno", None),
                        line_end=getattr(child, "end_lineno", None),
                        docstring=ast.get_docstring(child),
                        public_api=method_public,
                    )
                )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        if isinstance(getattr(node, "parent", None), ast.ClassDef):
            return
        self.symbols.append(
            ParsedSymbol(
                name=node.name,
                kind="function",
                qualified_name=node.name,
                line_start=getattr(node, "lineno", None),
                line_end=getattr(node, "end_lineno", None),
                docstring=ast.get_docstring(node),
                public_api=not node.name.startswith("_"),
            )
        )

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                self.symbols.append(
                    ParsedSymbol(
                        name=target.id,
                        kind="constant",
                        qualified_name=target.id,
                        line_start=getattr(node, "lineno", None),
                        line_end=getattr(node, "end_lineno", None),
                        docstring=None,
                        public_api=True,
                    )
                )


def _attach_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent  # type: ignore[attr-defined]


def parse_python_symbols(source_text: str) -> list[ParsedSymbol]:
    """Extract module/class/function/method/constant symbols from Python source."""

    tree = ast.parse(source_text)
    _attach_parents(tree)
    visitor = _ModuleVisitor()
    visitor.visit(tree)
    return visitor.symbols


def infer_test_surfaces(repo_files: list[str]) -> list[dict[str, str]]:
    """Infer lightweight test surfaces from test file paths."""

    surfaces: list[dict[str, str]] = []
    for path in repo_files:
        role = detect_file_role(path)
        if role != "tests":
            continue
        normalized = str(PurePosixPath(path))
        target_hint = "unknown"
        p = PurePosixPath(normalized)
        if p.name.startswith("test_") and p.suffix == ".py":
            mod_name = p.stem.removeprefix("test_")
            target_hint = f"{mod_name}.py"
        surfaces.append(
            {
                "test_file_path": normalized,
                "likely_target": target_hint,
                "test_kind": "unknown",
            }
        )
    return surfaces


def build_repo_snapshot_from_fixture(payload: dict) -> dict:
    """Construct stable RepoSnapshot payload from deterministic fixture data."""

    repository_external_key = payload["repository_external_key"]
    return {
        "external_key": derive_repo_snapshot_external_key(
            repository_external_key, payload["snapshot_id"]
        ),
        "source": "repo_fixture",
        "repository_external_key": repository_external_key,
        "commit_sha": payload["commit_sha"],
        "files": list(payload.get("files", [])),
        "symbols": list(payload.get("symbols", [])),
        "tests": list(payload.get("tests", [])),
        "external_metadata": {"snapshot_id": payload["snapshot_id"]},
    }


tools = ()
