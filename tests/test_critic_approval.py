"""Tests for critic approval logic with soft/hard issues."""

from briefsmith.agents import CriticDecision
from briefsmith.schemas import (
    BriefInput,
    BriefOutput,
    BriefSections,
    ObjectionResponse,
    ResearchFindings,
    SourceItem,
    WorkflowState,
    validate_completeness,
)
from briefsmith.agents.critic import critic_agent


class FakeLLMCritic:
    """Fake LLM that returns CriticDecision based on call count."""

    def __init__(self, decisions: list[CriticDecision]) -> None:
        self._decisions = decisions
        self._call_count = 0

    def generate(self, prompt: str, system: str | None = None) -> str:
        return "OK"

    def generate_json(
        self,
        prompt: str,
        schema_json: str,
        system: str | None = None,
    ) -> str:
        if "status" in schema_json:
            decision = self._decisions[self._call_count]
            self._call_count += 1
            return decision.model_dump_json()
        return "{}"


def test_approve_with_zero_hard_and_two_soft_issues() -> None:
    """Critic should approve when 0 hard issues and <= 2 soft issues."""
    # Create a brief with 2 soft issues (seo_keywords < 8, content_ideas < 6)
    # Add citations to meet citation requirement (>= 5)
    cite = " (Source #1)"
    brief = BriefSections(
        positioning_statement="Test positioning statement" + cite,
        key_messages=["M1" + cite, "M2" + cite, "M3" + cite, "M4" + cite, "M5" + cite],
        objections_and_responses=[
            ObjectionResponse(objection="O1", response="R1" + cite),
            ObjectionResponse(objection="O2", response="R2" + cite),
            ObjectionResponse(objection="O3", response="R3" + cite),
        ],
        launch_plan=["L1" + cite, "L2", "L3", "L4", "L5", "L6", "L7"],
        seo_keywords=["k1", "k2", "k3", "k4", "k5", "k6", "k7"],  # 7 < 8 (soft)
        content_ideas=["c1", "c2", "c3", "c4", "c5"],  # 5 < 6 (soft)
    )

    findings = ResearchFindings(
        market_summary="x" * 80,
        competitor_notes=[],
        positioning_angles=[],
        proof_points=[],
        risks=[],
    )

    sources = [
        SourceItem(url="https://a.com", title="A", snippet="Snippet A"),
        SourceItem(url="https://b.com", title="B", snippet="Snippet B"),
        SourceItem(url="https://c.com", title="C", snippet="Snippet C"),
    ]

    state = WorkflowState(
        input=BriefInput(
            product_name="Test",
            product_description="Test description with at least 20 characters",
            target_audience="Test audience",
        ),
        plan=None,
        sources=sources,
        findings=findings,
        brief=brief,
        approval_status="pending",
        revision_notes=None,
        metadata={"revision_count": 0},
    )

    # Critic returns approved decision
    llm = FakeLLMCritic([
        CriticDecision(status="approved", notes="Looks good", issues=[]),
    ])

    result = critic_agent(state, llm)

    assert result.approval_status == "approved"
    assert result.revision_notes is not None
    assert "Improvement suggestions" in result.revision_notes
    assert result.metadata.get("revision_count") == 0


def test_revise_with_hard_issues() -> None:
    """Critic should revise when hard issues exist."""
    # Create a brief with hard issue (missing positioning_statement)
    brief = BriefSections(
        positioning_statement="",  # Hard issue
        key_messages=["M1", "M2", "M3", "M4", "M5"],
        objections_and_responses=[
            ObjectionResponse(objection="O1", response="R1"),
            ObjectionResponse(objection="O2", response="R2"),
            ObjectionResponse(objection="O3", response="R3"),
        ],
        launch_plan=["L1", "L2", "L3", "L4", "L5", "L6", "L7"],
        seo_keywords=["k1"] * 12,
        content_ideas=["c1"] * 8,
    )

    findings = ResearchFindings(
        market_summary="x" * 80,
        competitor_notes=[],
        positioning_angles=[],
        proof_points=[],
        risks=[],
    )

    sources = [
        SourceItem(url="https://a.com", title="A", snippet="Snippet A"),
        SourceItem(url="https://b.com", title="B", snippet="Snippet B"),
        SourceItem(url="https://c.com", title="C", snippet="Snippet C"),
    ]

    state = WorkflowState(
        input=BriefInput(
            product_name="Test",
            product_description="Test description with at least 20 characters",
            target_audience="Test audience",
        ),
        plan=None,
        sources=sources,
        findings=findings,
        brief=brief,
        approval_status="pending",
        revision_notes=None,
        metadata={"revision_count": 0},
    )

    llm = FakeLLMCritic([
        CriticDecision(status="revise", notes="Fix issues", issues=[]),
    ])

    result = critic_agent(state, llm)

    assert result.approval_status == "revise"
    assert result.revision_notes is not None
    assert "Fix checklist" in result.revision_notes
    assert "Fix 1:" in result.revision_notes
    assert result.metadata.get("revision_count") == 1


def test_revise_with_more_than_two_soft_issues() -> None:
    """Critic should revise when > 2 soft issues."""
    # Create a brief with 3 soft issues
    brief = BriefSections(
        positioning_statement="Test positioning statement",
        key_messages=["M1", "M2", "M3", "M4", "M5"],
        objections_and_responses=[
            ObjectionResponse(objection="O1", response="R1"),
            ObjectionResponse(objection="O2", response="R2"),
        ],  # 2 < 3 (soft)
        launch_plan=["L1", "L2", "L3", "L4"],  # 4 < 5 (soft)
        seo_keywords=["k1", "k2", "k3", "k4", "k5", "k6", "k7"],  # 7 < 8 (soft)
        content_ideas=["c1", "c2", "c3", "c4", "c5"],  # 5 < 6 (soft)
    )

    findings = ResearchFindings(
        market_summary="x" * 80,
        competitor_notes=[],
        positioning_angles=[],
        proof_points=[],
        risks=[],
    )

    sources = [
        SourceItem(url="https://a.com", title="A", snippet="Snippet A"),
        SourceItem(url="https://b.com", title="B", snippet="Snippet B"),
        SourceItem(url="https://c.com", title="C", snippet="Snippet C"),
    ]

    state = WorkflowState(
        input=BriefInput(
            product_name="Test",
            product_description="Test description with at least 20 characters",
            target_audience="Test audience",
        ),
        plan=None,
        sources=sources,
        findings=findings,
        brief=brief,
        approval_status="pending",
        revision_notes=None,
        metadata={"revision_count": 0},
    )

    llm = FakeLLMCritic([
        CriticDecision(status="revise", notes="Need more content", issues=[]),
    ])

    result = critic_agent(state, llm)

    assert result.approval_status == "revise"
    assert result.metadata.get("revision_count") == 1


def test_validate_completeness_returns_structured_issues() -> None:
    """validate_completeness should return list of dicts with severity and message."""
    brief = BriefSections(
        positioning_statement="",  # Hard issue
        key_messages=["M1", "M2"],
        objections_and_responses=[
            ObjectionResponse(objection="O1", response="R1"),
        ],  # Soft issue: < 3
        launch_plan=["L1", "L2"],  # Soft issue: < 5
        seo_keywords=["k1", "k2"],  # Soft issue: < 8
        content_ideas=["c1"],  # Soft issue: < 6
    )

    findings = ResearchFindings(
        market_summary="x" * 50,  # Hard issue: < 80
        competitor_notes=[],
        positioning_angles=[],
        proof_points=[],
        risks=[],
    )

    sources = [
        SourceItem(url="https://a.com", title="A", snippet="Snippet A"),
    ]  # Hard issue: < 3

    output = BriefOutput(
        input=BriefInput(
            product_name="Test",
            product_description="Test description with at least 20 characters",
            target_audience="Test audience",
        ),
        findings=findings,
        brief=brief,
        sources=sources,
        metadata={},
    )

    issues = validate_completeness(output)

    assert len(issues) > 0
    for issue in issues:
        assert "severity" in issue
        assert "message" in issue
        assert issue["severity"] in ("hard", "soft")

    hard_issues = [i for i in issues if i["severity"] == "hard"]
    soft_issues = [i for i in issues if i["severity"] == "soft"]

    assert len(hard_issues) >= 3  # positioning, sources, market_summary
    assert len(soft_issues) >= 4  # objections, launch_plan, seo_keywords, content_ideas
