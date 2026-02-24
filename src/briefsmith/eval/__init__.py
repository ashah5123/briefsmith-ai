"""Evaluation harness for Briefsmith AI."""

from .metrics import (
    brief_length_stats,
    count_citations_in_markdown,
    findings_length,
    score_completeness,
)
from .report import build_eval_summary, write_eval_report
from .runner import EvalRunner

__all__ = [
    "EvalRunner",
    "brief_length_stats",
    "count_citations_in_markdown",
    "findings_length",
    "score_completeness",
    "build_eval_summary",
    "write_eval_report",
]

