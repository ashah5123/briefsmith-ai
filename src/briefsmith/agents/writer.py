"""Writer agent: produces BriefSections from findings and sources with citations."""

from datetime import UTC, datetime

from briefsmith.llm import LLMClient, generate_structured
from briefsmith.schemas import (
    BriefSections,
    SourceItem,
    WorkflowState,
)

WRITER_SYSTEM = (
    "You are a senior brand marketer. Write a complete marketing brief with "
    "clear structure, concise bullets, and source-cited claims. Cite sources "
    "in parentheses like (Source #1), (Source #2) in relevant bullets. "
    "Include at least 3 key_messages, 5 launch_plan items, 8 seo_keywords, "
    "6 content_ideas, and objections_and_responses where relevant."
)


def writer_agent(state: WorkflowState, llm: LLMClient) -> WorkflowState:
    """Produce BriefSections; address revision_notes when present."""
    findings = state.findings
    sources = state.sources
    if findings is None or not sources:
        return state

    revision_notes = state.revision_notes or ""
    revision_count = state.metadata.get("revision_count", 0)

    sources_text = _format_sources_for_writer(sources)
    inp = state.input
    prompt = (
        f"Product: {inp.product_name}\n"
        f"Target audience: {inp.target_audience}\n"
        f"Tone: {inp.tone}, Region: {inp.region}\n\n"
        "Research findings:\n"
        f"Market summary: {findings.market_summary}\n"
    )
    if findings.competitor_notes:
        prompt += "Competitor notes: " + "; ".join(findings.competitor_notes[:5]) + "\n"
    if findings.positioning_angles:
        prompt += "Positioning angles: "
        prompt += "; ".join(findings.positioning_angles[:5]) + "\n"
    if findings.proof_points:
        prompt += "Proof points: " + "; ".join(findings.proof_points[:5]) + "\n"
    if findings.risks:
        prompt += "Risks: " + "; ".join(findings.risks[:3]) + "\n"

    prompt += "\nSources (cite as Source #1, Source #2, ...):\n\n" + sources_text

    if revision_notes.strip():
        prompt += (
            "\n\nRevision feedback (address explicitly):\n" + revision_notes.strip()
        )

    prompt += "\n\nREQUIREMENTS CHECKLIST (STRICT):"
    prompt += "\n- key_messages: exactly 5"
    prompt += "\n- launch_plan: exactly 7 steps"
    prompt += "\n- seo_keywords: exactly 12"
    prompt += "\n- content_ideas: exactly 8"
    prompt += "\n- objections_and_responses: exactly 3 objects"
    prompt += "\n  (each object: { \"objection\": \"...\", \"response\": \"...\" })"

    prompt += "\n\nCITATION REQUIREMENTS (MANDATORY):"
    prompt += "\n- Include at least 8 total citations across the brief."
    prompt += "\n- Include at least 1 citation in each major section:"
    prompt += "\n  - positioning_statement"
    prompt += "\n  - key_messages (at least 2 cited)"
    prompt += "\n  - launch_plan (at least 2 cited)"
    prompt += "\n  - content_ideas (at least 2 cited)"
    prompt += "\n- Use format: (Source #n)"
    prompt += "\n- Do not fabricate source numbers beyond the provided list."
    prompt += "\n- Only reference source numbers that exist in the numbered sources list."
    prompt += "\n- If insufficient citations are used, the output will be rejected."

    prompt += "\n\nOUTPUT FORMAT (STRICT):"
    prompt += "\n- Return ONLY valid JSON."
    prompt += "\n- Return an INSTANCE, not a schema."
    prompt += "\n- Include ALL required keys: positioning_statement, key_messages,"
    prompt += " objections_and_responses, launch_plan, seo_keywords, content_ideas"
    prompt += "\n- Follow the exact counts in REQUIREMENTS CHECKLIST above"
    prompt += "\n\nIf you cannot find info, still fill fields with best-effort"
    prompt += " generic content and cite sources where possible."
    prompt += "\n\nProduce: positioning_statement, key_messages (exactly 5), "
    prompt += "objections_and_responses (exactly 3), launch_plan (exactly 7), "
    prompt += "seo_keywords (exactly 12), content_ideas (exactly 8). Use citations."

    brief = generate_structured(
        llm,
        system=WRITER_SYSTEM,
        prompt=prompt,
        model=BriefSections,
        max_retries=2,
    )

    meta = dict(state.metadata)
    meta["writer_timestamp"] = datetime.now(UTC).isoformat()
    meta["writer_model"] = "ollama"
    meta["revision_attempt"] = revision_count

    return state.model_copy(
        update={
            "brief": brief,
            "metadata": meta,
        }
    )


def _format_sources_for_writer(sources: list[SourceItem]) -> str:
    """Format sources as numbered list for the writer prompt."""
    lines = []
    for i, s in enumerate(sources, start=1):
        title = s.title or s.url
        lines.append(f"Source #{i}: {title}")
        lines.append(f"  {s.snippet.strip()}")
        lines.append("")
    return "\n".join(lines).strip()
