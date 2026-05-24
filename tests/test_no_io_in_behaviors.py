from pathlib import Path

FORBIDDEN_TOKENS = (
    "datetime.now",
    "date.today",
    "random",
    "uuid.uuid4",
    "subprocess",
    "requests",
    "httpx",
    "urllib",
    "open(",
    "Path.read_text",
)


def test_behavior_modules_do_not_contain_forbidden_io_or_nondeterminism() -> None:
    behavior_dir = Path("activegraph_repo_manager/behaviors")
    for path in behavior_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue
        content = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert token not in content, f"Forbidden token {token!r} in {path}"
