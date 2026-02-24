"""Smoke test: graph runs end-to-end with fake LLM and search clients."""

from briefsmith.agents import CriticDecision, PlanOutput
from briefsmith.schemas import (
    BriefInput,
    BriefSections,
    ObjectionResponse,
    ResearchFindings,
    SourceItem,
    WorkflowState,
)
from briefsmith.workflows import build_graph


class FakeLLMClient:
    """Returns structured JSON for planner, synthesizer, writer, and critic."""

    def generate(self, prompt: str, system: str | None = None) -> str:
        return "OK"

    def generate_json(
        self,
        prompt: str,
        schema_json: str,
        system: str | None = None,
    ) -> str:
        if "positioning_statement" in schema_json:
            cite = " (Source #1) " * 3 + " (Source #2) " * 2
            return BriefSections(
                positioning_statement="Position" + cite,
                key_messages=["M1" + cite, "M2", "M3", "M4", "M5"],
                objections_and_responses=[
                    ObjectionResponse(objection="O1", response="R1"),
                    ObjectionResponse(objection="O2", response="R2"),
                    ObjectionResponse(objection="O3", response="R3"),
                ],
                launch_plan=["L1", "L2", "L3", "L4", "L5", "L6", "L7"],
                seo_keywords=["k1", "k2", "k3", "k4", "k5", "k6", "k7", "k8", "k9", "k10", "k11", "k12"],
                content_ideas=["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"],
            ).model_dump_json()
        if "status" in schema_json:
            return CriticDecision(
                status="approved", notes="", issues=[]
            ).model_dump_json()
        if "market_summary" in schema_json:
            return ResearchFindings(
                market_summary="A" * 80,
                competitor_notes=["Note 1"],
                positioning_angles=["Angle 1"],
                proof_points=["Proof 1"],
                risks=["Risk 1"],
            ).model_dump_json()
        if '"plan"' in schema_json:
            return PlanOutput(
                plan=["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"]
            ).model_dump_json()
        return "{}"


class FakeSearchClient:
    """Returns a fixed list of SourceItems (>=3 for validate_completeness)."""

    def search(self, query: str, max_results: int = 5) -> list[SourceItem]:
        return [
            SourceItem(
                url="https://example.com/1",
                title="Source 1",
                snippet="Snippet 1",
            ),
            SourceItem(
                url="https://example.com/2",
                title="Source 2",
                snippet="Snippet 2",
            ),
            SourceItem(
                url="https://example.com/3",
                title="Source 3",
                snippet="Snippet 3",
            ),
        ][:max_results]


def test_graph_runs_end_to_end_and_returns_findings() -> None:
    """Graph runs full pipeline; final state has findings, brief, approved."""
    llm = FakeLLMClient()
    search = FakeSearchClient()
    graph = build_graph(llm, search)

    brief_input = BriefInput(
        product_name="Test Product",
        product_description=(
            "A product description with at least twenty characters here."
        ),
        target_audience="Test audience",
    )
    initial = WorkflowState(
        input=brief_input,
        plan=None,
        sources=[],
        findings=None,
        brief=None,
        approval_status="pending",
        revision_notes=None,
        metadata={"revision_count": 0},
    )
    state_dict = initial.model_dump(mode="json")

    final = graph.invoke(state_dict)

    assert final is not None
    assert final.get("plan") is not None
    assert len(final["plan"]) >= 5
    assert final.get("sources") is not None
    assert len(final["sources"]) >= 1
    assert final.get("findings") is not None
    findings = final["findings"]
    assert "market_summary" in findings
    assert len(findings["market_summary"]) >= 80
    assert final.get("brief") is not None
    assert final.get("approval_status") == "approved"
