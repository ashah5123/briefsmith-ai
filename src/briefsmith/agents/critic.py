"""Critic agent: reviews brief and decides approved or revise."""

import re
from typing import Literal

from pydantic import BaseModel

from briefsmith.llm import LLMClient, generate_structured
from briefsmith.schemas import BriefOutput, BriefSections, WorkflowState
from briefsmith.schemas.utils import to_markdown, validate_completeness

MIN_CITATIONS = 5
CITATION_PATTERN = re.compile(r"\(Source\s*#\s*\d+\)", re.IGNORECASE)

CRITIC_SYSTEM = (
    "You are a strict QA reviewer. Your job is to ensure completeness, "
    "source-citation, and internal consistency. If anything is missing or "
    "weak, request a revision. Output approved only if the brief is ready."
)


class CriticDecision(BaseModel):
    """Critic output: status and feedback."""

    status: Literal["approved", "revise"]
    notes: str
    issues: list[str]


def critic_agent(state: WorkflowState, llm: LLMClient) -> WorkflowState:
    """Review brief; set approval_status, revision_notes; bump revision_count."""
    brief = state.brief
    if brief is None or state.findings is None:
        return state

    output = BriefOutput(
        input=state.input,
        findings=state.findings,
        brief=brief,
        sources=state.sources,
        metadata=state.metadata,
    )
    completeness_issues = validate_completeness(output)

    # Count citations in markdown output
    markdown_text = to_markdown(output)
    citation_count = len(CITATION_PATTERN.findall(markdown_text))
    citation_ok = citation_count >= MIN_CITATIONS
    if not citation_ok:
        completeness_issues.append({
            "severity": "soft",
            "message": f"Too few source citations (need >= {MIN_CITATIONS}, got {citation_count})"
        })

    # Separate hard and soft issues
    hard_issues = [i for i in completeness_issues if i["severity"] == "hard"]
    soft_issues = [i for i in completeness_issues if i["severity"] == "soft"]

    prompt = (
        "Brief content to review:\n\n"
        f"Positioning: {brief.positioning_statement}\n"
        f"Key messages: {len(brief.key_messages)} items\n"
        f"Launch plan: {len(brief.launch_plan)} items\n"
        f"SEO keywords: {len(brief.seo_keywords)} items\n"
        f"Content ideas: {len(brief.content_ideas)} items\n"
        f"Citations found: {citation_count}\n\n"
    )
    if completeness_issues:
        prompt += "Validation issues:\n"
        for i in completeness_issues:
            prompt += f"- [{i['severity'].upper()}] {i['message']}\n"

    prompt += "\n\nDecide: approved (brief ready) or revise (with notes and issues)."

    decision = generate_structured(
        llm,
        system=CRITIC_SYSTEM,
        prompt=prompt,
        model=CriticDecision,
        max_retries=2,
    )

    meta = dict(state.metadata)
    meta.setdefault("revision_count", 0)

    # Calibration: approve if 0 hard issues and <= 2 soft issues
    should_approve = len(hard_issues) == 0 and len(soft_issues) <= 2

    if should_approve:
        # Include improvement suggestions in notes if soft issues exist
        notes_parts = []
        if decision.notes and decision.notes.strip():
            notes_parts.append(decision.notes.strip())
        if soft_issues:
            notes_parts.append("Improvement suggestions:")
            for i, issue in enumerate(soft_issues, start=1):
                notes_parts.append(f"- {issue['message']}")
        notes = "\n".join(notes_parts) if notes_parts else ""
        
        return state.model_copy(
            update={
                "approval_status": "approved",
                "revision_notes": notes if notes else None,
                "metadata": meta,
            }
        )

    # REVISE: generate checklist format revision notes
    meta["revision_count"] = meta["revision_count"] + 1
    
    revision_parts = []
    if decision.notes and decision.notes.strip():
        revision_parts.append(decision.notes.strip())
    
    # Add checklist format for issues
    all_issue_messages = [i["message"] for i in completeness_issues]
    if all_issue_messages:
        revision_parts.append("Fix checklist:")
        for i, msg in enumerate(all_issue_messages, start=1):
            revision_parts.append(f"Fix {i}: {msg}")
    
    revision_notes = "\n".join(revision_parts).strip()
    
    return state.model_copy(
        update={
            "approval_status": "revise",
            "revision_notes": revision_notes if revision_notes else None,
            "metadata": meta,
        }
    )


def _brief_to_text(brief: BriefSections) -> str:
    """Concatenate brief fields for citation counting."""
    parts = [
        brief.positioning_statement,
        " ".join(brief.key_messages),
        " ".join(
            f"{o.objection} {o.response}" for o in brief.objections_and_responses
        ),
        " ".join(brief.launch_plan),
        " ".join(brief.seo_keywords),
        " ".join(brief.content_ideas),
    ]
    return " ".join(parts)
