"""Smoke test: graph runs end-to-end with fake LLM and search clients."""

from briefsmith.agents import PlanOutput
from briefsmith.schemas import (
    BriefInput,
    ResearchFindings,
    SourceItem,
    WorkflowState,
)
from briefsmith.workflows import build_graph


class FakeLLMClient:
    """Returns structured JSON for planner and synthesizer."""

    def generate(self, prompt: str, system: str | None = None) -> str:
        return "OK"

    def generate_json(
        self,
        prompt: str,
        schema_json: str,
        system: str | None = None,
    ) -> str:
        if "plan" in schema_json or "plan" in (prompt + (system or "")):
            plan = PlanOutput(plan=["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"])
            return plan.model_dump_json()
        findings = ResearchFindings(
            market_summary="A" * 80,
            competitor_notes=["Note 1"],
            positioning_angles=["Angle 1"],
            proof_points=["Proof 1"],
            risks=["Risk 1"],
        )
        return findings.model_dump_json()


class FakeSearchClient:
    """Returns a fixed list of SourceItems."""

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
        ][:max_results]


def test_graph_runs_end_to_end_and_returns_findings() -> None:
    """Graph runs planner -> researcher -> synthesizer and final state has findings."""
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
        metadata={},
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
