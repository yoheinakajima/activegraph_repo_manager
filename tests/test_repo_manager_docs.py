from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "activegraph_repo_manager" / "README.md"
STATUS_PATH = ROOT / "activegraph_repo_manager" / "STATUS.md"


def _readme_text() -> str:
    assert README_PATH.exists()
    return README_PATH.read_text(encoding="utf-8")


def _status_text() -> str:
    assert STATUS_PATH.exists()
    return STATUS_PATH.read_text(encoding="utf-8")


def test_repo_manager_readme_exists() -> None:
    assert README_PATH.exists()


def test_repo_manager_readme_documents_required_helper_flows() -> None:
    text = _readme_text().lower()

    assert "keyless demo" in text
    assert "read-only sync" in text and "github" in text
    assert "dry-run external actions" in text


def test_repo_manager_readme_documents_live_write_boundary() -> None:
    text = _readme_text().lower()

    assert (
        "live writes are disabled" in text
        or "live writes are unimplemented" in text
    )


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


def test_repo_manager_status_exists() -> None:
    assert STATUS_PATH.exists()


def test_repo_manager_status_documents_current_boundaries() -> None:
    text = _status_text().lower()

    assert "helper-level" in text
    assert "read-only" in text
    assert "dry-run-only" in text
    assert (
        "live writes are disabled" in text
        or "live writes are unimplemented" in text
    )
    assert "before-live-write gates" in text


def test_repo_manager_readme_points_to_status() -> None:
    text = _readme_text().lower()

    assert "status.md" in text
