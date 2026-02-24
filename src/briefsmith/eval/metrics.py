"""Evaluation metrics for Briefsmith runs."""

from __future__ import annotations

from typing import Any

from briefsmith.schemas import BriefOutput, BriefSections, ResearchFindings
from briefsmith.schemas.utils import validate_completeness


def count_citations_in_markdown(text: str) -> int:
    """Count occurrences of '(Source #' in markdown text."""
    return text.count("(Source #")


def brief_length_stats(brief: BriefSections) -> dict[str, int]:
    """Return section counts for a BriefSections object."""
    return {
        "key_messages": len(brief.key_messages),
        "launch_plan": len(brief.launch_plan),
        "seo_keywords": len(brief.seo_keywords),
        "content_ideas": len(brief.content_ideas),
        "objections_and_responses": len(brief.objections_and_responses),
    }


def findings_length(findings: ResearchFindings) -> int:
    """Return market_summary length in characters."""
    return len(findings.market_summary)


def score_completeness(output: BriefOutput) -> dict[str, Any]:
    """Score completeness using hard/soft issue counts and the issue list."""
    issues = validate_completeness(output)
    hard = sum(1 for i in issues if i.get("severity") == "hard")
    soft = sum(1 for i in issues if i.get("severity") == "soft")
    return {
        "hard_issues_count": hard,
        "soft_issues_count": soft,
        "issues": issues,
    }

