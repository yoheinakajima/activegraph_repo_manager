from pathlib import Path


README_PATH = Path(__file__).resolve().parents[1] / "activegraph_repo_manager" / "README.md"


def _readme_text() -> str:
    assert README_PATH.exists()
    return README_PATH.read_text(encoding="utf-8")


def test_repo_manager_readme_exists() -> None:
    assert README_PATH.exists()


def test_repo_manager_readme_documents_required_helper_flows() -> None:
    text = _readme_text().lower()

    assert "keyless demo" in text
    assert "read-only sync" in text and "github" in text
    assert "dry-run external actions" in text


def test_repo_manager_readme_documents_live_write_boundary() -> None:
    text = _readme_text().lower()

    assert "live writes are disabled" in text or "live writes are unimplemented" in text


def test_repo_manager_readme_does_not_overclaim_live_capability() -> None:
    text = _readme_text().lower()

    forbidden_claims = (
        "live writes are enabled",
        "live github writes are implemented",
        "github writes are implemented",
        "live llm calls are required",
    )
    for claim in forbidden_claims:
        assert claim not in text
