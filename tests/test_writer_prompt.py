"""Tests for writer prompt exact counts."""

from briefsmith.agents.writer import writer_agent
from briefsmith.schemas import (
    BriefInput,
    ObjectionResponse,
    ResearchFindings,
    SourceItem,
    WorkflowState,
)


class SpyLLMClient:
    """Spy LLM client that captures prompts."""

    def __init__(self) -> None:
        self.captured_prompts: list[str] = []
        self.captured_systems: list[str | None] = []

    def generate(self, prompt: str, system: str | None = None) -> str:
        return "OK"

    def generate_json(
        self,
        prompt: str,
        schema_json: str,
        system: str | None = None,
    ) -> str:
        self.captured_prompts.append(prompt)
        self.captured_systems.append(system)
        # Return minimal valid BriefSections JSON
        return """{
            "positioning_statement": "Test",
            "key_messages": ["M1", "M2", "M3", "M4", "M5"],
            "objections_and_responses": [
                {"objection": "O1", "response": "R1"},
                {"objection": "O2", "response": "R2"},
                {"objection": "O3", "response": "R3"}
            ],
            "launch_plan": ["L1", "L2", "L3", "L4", "L5", "L6", "L7"],
            "seo_keywords": ["k1", "k2", "k3", "k4", "k5", "k6", "k7", "k8", "k9", "k10", "k11", "k12"],
            "content_ideas": ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"]
        }"""


def test_writer_prompt_includes_exact_counts() -> None:
    """Writer prompt should include exact counts: 5, 7, 12, 8, 3."""
    llm = SpyLLMClient()

    findings = ResearchFindings(
        market_summary="Test market summary",
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
            product_name="Test Product",
            product_description="Test description with at least 20 characters",
            target_audience="Test audience",
        ),
        plan=None,
        sources=sources,
        findings=findings,
        brief=None,
        approval_status="pending",
        revision_notes=None,
        metadata={"revision_count": 0},
    )

    writer_agent(state, llm)

    assert len(llm.captured_prompts) > 0
    prompt = llm.captured_prompts[0]

    # Check for exact counts in REQUIREMENTS CHECKLIST
    assert "exactly 5" in prompt or "key_messages: exactly 5" in prompt
    assert "exactly 7" in prompt or "launch_plan: exactly 7" in prompt
    assert "exactly 12" in prompt or "seo_keywords: exactly 12" in prompt
    assert "exactly 8" in prompt or "content_ideas: exactly 8" in prompt
    assert "exactly 3" in prompt or "objections_and_responses: exactly 3" in prompt

    # Check that REQUIREMENTS CHECKLIST section exists
    assert "REQUIREMENTS CHECKLIST" in prompt or "CHECKLIST" in prompt
