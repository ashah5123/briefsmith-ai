"""Placeholder tests for Briefsmith."""


from briefsmith import __version__


def test_version() -> None:
    """Package has a version."""
    assert __version__ == "0.1.0"


def test_health_endpoint() -> None:
    """Health endpoint returns status ok."""
    from fastapi.testclient import TestClient

    from briefsmith.api import app

    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
