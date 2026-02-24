"""Revision loop: writer returns short brief first, critic revises, then approved."""

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


class FakeLLMRevision:
    """Writer: short brief then full; critic: revise then approved."""

    def __init__(self) -> None:
        self._writer_calls = 0
        self._critic_calls = 0

    def generate(self, prompt: str, system: str | None = None) -> str:
        return "OK"

    def generate_json(
        self,
        prompt: str,
        schema_json: str,
        system: str | None = None,
    ) -> str:
        if "positioning_statement" in schema_json:
            self._writer_calls += 1
            if self._writer_calls == 1:
                return BriefSections(
                    positioning_statement="Short (Source #1).",
                    key_messages=["A (Source #1)", "B"],
                    objections_and_responses=[],
                    launch_plan=["L1", "L2"],
                    seo_keywords=["k1", "k2"],
                    content_ideas=["c1", "c2"],
                ).model_dump_json()
            cite = " (Source #1) " * 3 + " (Source #2) " * 2
            return BriefSections(
                    positioning_statement="Full positioning" + cite,
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
            self._critic_calls += 1
            if self._critic_calls == 1:
                return CriticDecision(
                    status="revise",
                    notes="Need more content",
                    issues=["Too few key_messages"],
                ).model_dump_json()
            return CriticDecision(
                status="approved",
                notes="",
                issues=[],
            ).model_dump_json()
        if "market_summary" in schema_json:
            return ResearchFindings(
                market_summary="x" * 80,
                competitor_notes=[],
                positioning_angles=[],
                proof_points=[],
                risks=[],
            ).model_dump_json()
        if '"plan"' in schema_json:
            return PlanOutput(
                plan=["S1", "S2", "S3", "S4", "S5"]
            ).model_dump_json()
        return "{}"


class FakeSearchStable:
    """Returns stable list of sources."""

    def search(self, query: str, max_results: int = 5) -> list[SourceItem]:
        return [
            SourceItem(url="https://a.com", title="A", snippet="Snippet A"),
            SourceItem(url="https://b.com", title="B", snippet="Snippet B"),
            SourceItem(url="https://c.com", title="C", snippet="Snippet C"),
        ][:max_results]


def test_revision_loop_ends_approved_with_revision_count_one() -> None:
    """Short brief -> revise -> full -> approved; revision_count=1."""
    llm = FakeLLMRevision()
    search = FakeSearchStable()
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

    assert final.get("approval_status") == "approved"
    assert final.get("metadata", {}).get("revision_count") == 1
    assert final.get("brief") is not None
