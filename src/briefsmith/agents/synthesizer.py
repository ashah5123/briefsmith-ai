"""Synthesizer agent: converts sources into ResearchFindings with citations."""

from datetime import UTC, datetime

from briefsmith.llm import LLMClient, generate_structured
from briefsmith.schemas import ResearchFindings, SourceItem, WorkflowState

SYNTHESIZER_SYSTEM = (
    "You are a research analyst. Synthesize the given sources into "
    "structured findings. Whenever you reference a claim or fact from a "
    "source, cite it as (Source #n) where n is the 1-based index of that "
    "source in the provided list. Use at least 80 characters for "
    "market_summary."
)


def synthesizer_agent(state: WorkflowState, llm: LLMClient) -> WorkflowState:
    """Convert state.sources into ResearchFindings via LLM; store in state."""
    sources = state.sources
    if not sources:
        empty = ResearchFindings(
            market_summary="No sources available.",
            competitor_notes=[],
            positioning_angles=[],
            proof_points=[],
            risks=[],
        )
        return state.model_copy(
            update={
                "findings": empty,
                "metadata": {
                    **state.metadata,
                    "synthesizer_completed_at": datetime.now(UTC).isoformat(),
                },
            }
        )

    sources_text = _format_sources(sources)
    inp = state.input
    prompt = (
        f"Product: {inp.product_name}\n"
        f"Target audience: {inp.target_audience}\n\n"
        "Sources (cite as Source #1, Source #2, ...):\n\n"
        f"{sources_text}\n\n"
        "Produce: market_summary (≥80 chars), competitor_notes, "
        "positioning_angles, proof_points, risks. Include citations."
    )

    findings = generate_structured(
        llm,
        system=SYNTHESIZER_SYSTEM,
        prompt=prompt,
        model=ResearchFindings,
        max_retries=2,
    )

    return state.model_copy(
        update={
            "findings": findings,
            "metadata": {
                **state.metadata,
                "synthesizer_completed_at": datetime.now(UTC).isoformat(),
            },
        }
    )


def _format_sources(sources: list[SourceItem]) -> str:
    """Format sources as numbered list for the prompt."""
    lines = []
    for i, s in enumerate(sources, start=1):
        title = s.title or s.url
        lines.append(f"Source #{i}: {title}")
        lines.append(f"  URL: {s.url}")
        lines.append(f"  Snippet: {s.snippet.strip()}")
        lines.append("")
    return "\n".join(lines).strip()
