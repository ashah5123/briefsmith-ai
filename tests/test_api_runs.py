"""Tests for run registry FastAPI endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi.testclient import TestClient

import briefsmith.api as api
from briefsmith.runs import RunStore


class _FakeGraph:
    """Simple graph stub that returns a fixed final state."""

    def __init__(self, final_state: Dict[str, Any]) -> None:
        self._final_state = final_state

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return self._final_state


def _make_final_state() -> Dict[str, Any]:
    """Return a minimal but valid final workflow state."""
    findings = {
        "market_summary": "x" * 80,
        "competitor_notes": [],
        "positioning_angles": [],
        "proof_points": [],
        "risks": [],
    }
    brief = {
        "positioning_statement": "Test positioning (Source #1)",
        "key_messages": ["M1 (Source #1)", "M2", "M3", "M4", "M5"],
        "objections_and_responses": [
            {"objection": "O1", "response": "R1 (Source #1)"},
            {"objection": "O2", "response": "R2"},
            {"objection": "O3", "response": "R3"},
        ],
        "launch_plan": ["L1", "L2", "L3", "L4", "L5", "L6", "L7"],
        "seo_keywords": [
            "k1",
            "k2",
            "k3",
            "k4",
            "k5",
            "k6",
            "k7",
            "k8",
            "k9",
            "k10",
            "k11",
            "k12",
        ],
        "content_ideas": ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"],
    }
    sources = [
        {
            "url": "https://example.com/1",
            "title": "Source 1",
            "snippet": "Snippet 1",
        },
        {
            "url": "https://example.com/2",
            "title": "Source 2",
            "snippet": "Snippet 2",
        },
        {
            "url": "https://example.com/3",
            "title": "Source 3",
            "snippet": "Snippet 3",
        },
    ]
    metadata = {
        "revision_count": 0,
        "writer_model": "test-model",
        "durations_ms": {"total": 123},
    }
    return {
        "sources": sources,
        "findings": findings,
        "brief": brief,
        "metadata": metadata,
        "approval_status": "approved",
        "revision_notes": None,
    }


def test_post_run_creates_run_and_artifacts(tmp_path, monkeypatch) -> None:
    """POST /run should register a run and write artifacts."""
    # Use a temporary base directory for runs
    base_dir = tmp_path / "runs"
    api.run_store = RunStore(base_dir=base_dir)

    # Stub out build_graph to avoid real LLM/search work
    final_state = _make_final_state()

    def fake_build_graph(llm: object, search: object) -> _FakeGraph:
        return _FakeGraph(final_state)

    monkeypatch.setattr(api, "build_graph", fake_build_graph)

    # Stub LLM and search client classes to avoid external calls
    class DummyLLM:
        def __init__(self) -> None:
            pass

    class DummySearch:
        def __init__(self, cache: object | None = None) -> None:
            self.cache = cache

    monkeypatch.setattr(api, "OllamaClient", DummyLLM)
    monkeypatch.setattr(api, "DuckDuckGoSearchClient", DummySearch)

    client = TestClient(api.app)

    body = {
        "product_name": "Test Product",
        "product_description": "A product description with at least twenty characters.",
        "target_audience": "Test audience",
    }
    resp = client.post("/run", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    run_id = data["run_id"]
    assert data["approval_status"] == "approved"
    assert data["revision_count"] == 0

    run_dir = base_dir / run_id
    assert run_dir.is_dir()

    # Expected artifacts
    expected_files = {
        "input.json",
        "sources.json",
        "findings.json",
        "brief.json",
        "final_brief.md",
        "run_metadata.json",
    }
    for name in expected_files:
        assert (run_dir / name).is_file()

    # GET /runs should list our run
    list_resp = client.get("/runs", params={"limit": 10})
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(item["run_id"] == run_id for item in items)

    # GET /runs/{run_id} should return metadata
    meta_resp = client.get(f"/runs/{run_id}")
    assert meta_resp.status_code == 200
    meta = meta_resp.json()
    assert meta["run_id"] == run_id
    assert meta["approval_status"] == "approved"

    # GET artifact should return file content
    art_resp = client.get(f"/runs/{run_id}/artifact/final_brief.md")
    assert art_resp.status_code == 200
    assert "text/markdown" in art_resp.headers.get("content-type", "")
    assert "Brief:" in art_resp.text

