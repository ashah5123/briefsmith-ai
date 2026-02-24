"""Tests for the Briefsmith evaluation harness."""

from __future__ import annotations

from pathlib import Path

from briefsmith.eval import build_eval_summary
from briefsmith.eval.runner import EvalRunner
from briefsmith.runs import RunStore
from briefsmith.schemas import (
    BriefInput,
    BriefSections,
    ObjectionResponse,
    ResearchFindings,
    SourceItem,
)
from briefsmith.tools import DuckDuckGoSearchClient, SearchCache


class FakeLLMClient:
    """Fake LLM client that returns structured JSON by schema shape."""

    def generate(self, prompt: str, system: str | None = None) -> str:
        return "OK"

    def generate_json(
        self,
        prompt: str,
        schema_json: str,
        system: str | None = None,
    ) -> str:
        # Planner output
        if '"plan"' in schema_json:
            return '{"plan": ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"]}'

        # Synthesizer: ResearchFindings
        if "market_summary" in schema_json:
            return ResearchFindings(
                market_summary="x" * 80,
                competitor_notes=[],
                positioning_angles=[],
                proof_points=[],
                risks=[],
            ).model_dump_json()

        # Writer: BriefSections
        if "positioning_statement" in schema_json:
            cite = " (Source #1)"
            brief = BriefSections(
                positioning_statement="Positioning" + cite,
                key_messages=[
                    "M1" + cite,
                    "M2" + cite,
                    "M3" + cite,
                    "M4" + cite,
                    "M5" + cite,
                ],
                objections_and_responses=[
                    ObjectionResponse(objection="O1", response="R1" + cite),
                    ObjectionResponse(objection="O2", response="R2" + cite),
                    ObjectionResponse(objection="O3", response="R3" + cite),
                ],
                launch_plan=["L1", "L2", "L3", "L4", "L5", "L6", "L7"],
                seo_keywords=[
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
                content_ideas=["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"],
            )
            return brief.model_dump_json()

        # Critic decision
        if "status" in schema_json:
            return '{"status":"approved","notes":"","issues":[]}'

        return "{}"


class FakeSearchClient:
    """Fake search client that returns stable sources with no network."""

    def search(self, query: str, max_results: int = 5) -> list[SourceItem]:
        return [
            SourceItem(url="https://a.com", title="A", snippet="Snippet A"),
            SourceItem(url="https://b.com", title="B", snippet="Snippet B"),
            SourceItem(url="https://c.com", title="C", snippet="Snippet C"),
        ][:max_results]


class FailingSearchClient:
    """Search client that should never be called when sources_override is used."""

    def search(self, query: str, max_results: int = 5) -> list[SourceItem]:
        raise RuntimeError("Search should not be called when sources_override is set")


def test_eval_runner_and_summary_metrics(tmp_path: Path) -> None:
    """EvalRunner should produce results and a valid summary."""
    run_store = RunStore(base_dir=tmp_path / "runs")
    runner = EvalRunner(llm=FakeLLMClient(), search=FakeSearchClient(), run_store=run_store)

    inp = BriefInput(
        product_name="Test Product",
        product_description="A product description with at least twenty characters.",
        target_audience="Test audience",
        region="US",
    )

    results = runner.run_many(inp, runs=2, offline=False)
    assert len(results) == 2
    assert all(r.get("error") is None for r in results)
    assert all(r.get("approval_status") == "approved" for r in results)

    summary = build_eval_summary(results)
    assert summary["runs_requested"] == 2
    assert summary["runs_completed"] == 2
    assert summary["failures_count"] == 0
    assert summary["approval_rate"] == 1.0

    cs = summary["citation_stats"]
    assert cs["min"] >= 5
    assert cs["max"] >= cs["min"]


def test_offline_mode_enforces_cache_only_on_cache_miss(tmp_path: Path) -> None:
    """Offline mode should fail fast when search cache is missing required queries."""
    cache = SearchCache(cache_dir=tmp_path / "cache")
    ddg = DuckDuckGoSearchClient(cache=cache, base_url="https://example.invalid")

    run_store = RunStore(base_dir=tmp_path / "runs")
    runner = EvalRunner(llm=FakeLLMClient(), search=ddg, run_store=run_store)

    inp = BriefInput(
        product_name="Test Product",
        product_description="A product description with at least twenty characters.",
        target_audience="Test audience",
        region="US",
    )

    result = runner.run_once(inp, offline=True)
    assert result.get("error") is not None
    assert "Offline mode cache miss" in str(result.get("error"))


def test_sources_override_skips_search_and_uses_existing_sources(tmp_path: Path) -> None:
    """When sources_override is provided, EvalRunner must not call search."""
    run_store = RunStore(base_dir=tmp_path / "runs")
    # search client that fails if invoked
    search = FailingSearchClient()

    sources_override = [
        SourceItem(url="https://example.com/1", title="S1", snippet="Snippet 1"),
        SourceItem(url="https://example.com/2", title="S2", snippet="Snippet 2"),
    ]

    runner = EvalRunner(
        llm=FakeLLMClient(),
        search=search,
        run_store=run_store,
        sources_override=sources_override,
    )

    inp = BriefInput(
        product_name="Test Product",
        product_description="A product description with at least twenty characters.",
        target_audience="Test audience",
        region="US",
    )

    result = runner.run_once(inp, offline=True)
    assert result.get("error") is None
    # We only require that search was not called (no error) and a run_id exists.
    assert result.get("run_id") is not None

