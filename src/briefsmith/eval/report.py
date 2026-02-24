"""Evaluation reporting utilities (summary + JSON/Markdown reports)."""

from __future__ import annotations

import json
import secrets
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _generate_eval_id() -> str:
    now = datetime.now(UTC)
    ts = now.strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(3)
    return f"{ts}_{suffix}"


def build_eval_summary(results: list[dict[str, Any]], notes: str | None = None) -> dict[str, Any]:
    """Build an aggregate evaluation summary from per-run results."""
    eval_id = _generate_eval_id()
    created_at = datetime.now(UTC).isoformat()

    runs_requested = len(results)
    completed = [r for r in results if not r.get("error")]
    failures = [r for r in results if r.get("error")]

    runs_completed = len(completed)
    failures_count = len(failures)

    approvals = sum(1 for r in completed if r.get("approval_status") == "approved")
    approval_rate = (approvals / runs_completed) if runs_completed else 0.0

    rev_counts = [int(r.get("revision_count") or 0) for r in completed]
    avg_revision_count = (sum(rev_counts) / len(rev_counts)) if rev_counts else 0.0

    citations = [int(r.get("citations") or 0) for r in completed]
    citation_stats = {
        "min": min(citations) if citations else 0,
        "avg": (sum(citations) / len(citations)) if citations else 0.0,
        "max": max(citations) if citations else 0,
    }

    # Common issues by message (top 5)
    issue_counter: Counter[str] = Counter()
    for r in completed:
        issues = r.get("issues") or []
        if isinstance(issues, list):
            for i in issues:
                if isinstance(i, dict) and "message" in i:
                    msg = str(i.get("message"))
                    if msg:
                        issue_counter[msg] += 1
    common_issues = [
        {"message": msg, "count": count}
        for msg, count in issue_counter.most_common(5)
    ]

    summary: dict[str, Any] = {
        "eval_id": eval_id,
        "created_at": created_at,
        "runs_requested": runs_requested,
        "runs_completed": runs_completed,
        "approval_rate": approval_rate,
        "avg_revision_count": avg_revision_count,
        "citation_stats": citation_stats,
        "failures_count": failures_count,
        "common_issues": common_issues,
        "notes": notes,
    }
    return summary


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_eval_report(eval_dir: Path, summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    """Write eval_report.json and eval_report.md into eval_dir."""
    eval_dir.mkdir(parents=True, exist_ok=True)

    payload = {"summary": summary, "results": results}
    _atomic_write_text(
        eval_dir / "eval_report.json",
        json.dumps(payload, indent=2, ensure_ascii=False),
    )

    md_lines: list[str] = []
    md_lines.append(f"# Briefsmith Evaluation: {summary.get('eval_id')}")
    md_lines.append("")
    md_lines.append("## Summary")
    md_lines.append("")
    md_lines.append(f"- **Created at:** {summary.get('created_at')}")
    md_lines.append(f"- **Runs requested:** {summary.get('runs_requested')}")
    md_lines.append(f"- **Runs completed:** {summary.get('runs_completed')}")
    md_lines.append(f"- **Failures:** {summary.get('failures_count')}")
    md_lines.append(f"- **Approval rate:** {summary.get('approval_rate'):.2f}")
    md_lines.append(f"- **Avg revision count:** {summary.get('avg_revision_count'):.2f}")
    cs = summary.get("citation_stats") or {}
    md_lines.append(
        f"- **Citations (min/avg/max):** {cs.get('min')}/{cs.get('avg'):.2f}/{cs.get('max')}"
    )
    if summary.get("notes"):
        md_lines.append(f"- **Notes:** {summary.get('notes')}")
    md_lines.append("")

    common = summary.get("common_issues") or []
    if common:
        md_lines.append("## Common issues (top 5)")
        md_lines.append("")
        for item in common:
            md_lines.append(f"- {item.get('message')} (x{item.get('count')})")
        md_lines.append("")

    md_lines.append("## Runs")
    md_lines.append("")
    md_lines.append("| run_id | status | revisions | citations | hard | soft | duration_ms | error |")
    md_lines.append("|---|---|---:|---:|---:|---:|---:|---|")
    for r in results:
        md_lines.append(
            "| "
            + " | ".join(
                [
                    str(r.get("run_id") or ""),
                    str(r.get("approval_status") or ""),
                    str(r.get("revision_count") or ""),
                    str(r.get("citations") or ""),
                    str(r.get("hard_issues_count") or ""),
                    str(r.get("soft_issues_count") or ""),
                    str(r.get("duration_ms") or ""),
                    str(r.get("error") or ""),
                ]
            )
            + " |"
        )
    md_lines.append("")

    _atomic_write_text(eval_dir / "eval_report.md", "\n".join(md_lines))

