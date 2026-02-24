"""Utility functions for brief output: Markdown export and completeness validation."""

from briefsmith.schemas.output import BriefOutput


def to_markdown(output: BriefOutput) -> str:
    """Generate a recruiter-friendly Markdown brief with sections and bullet lists."""
    lines: list[str] = []

    # Input context
    lines.append("# Brief: " + output.input.product_name)
    lines.append("")
    lines.append("## Input context")
    lines.append("")
    lines.append(f"- **Product:** {output.input.product_name}")
    lines.append(f"- **Description:** {output.input.product_description}")
    lines.append(f"- **Target audience:** {output.input.target_audience}")
    lines.append(f"- **Region:** {output.input.region}")
    lines.append(f"- **Tone:** {output.input.tone}")
    if output.input.competitors:
        lines.append("- **Competitors:**")
        for c in output.input.competitors:
            lines.append(f"  - {c}")
    if output.input.channels:
        lines.append("- **Channels:** " + ", ".join(output.input.channels))
    if output.input.constraints:
        lines.append("- **Constraints:**")
        for c in output.input.constraints:
            lines.append(f"  - {c}")
    lines.append("")

    # Research findings
    lines.append("## Research findings")
    lines.append("")
    lines.append("### Market summary")
    lines.append("")
    lines.append(output.findings.market_summary)
    lines.append("")
    if output.findings.competitor_notes:
        lines.append("### Competitor notes")
        lines.append("")
        for n in output.findings.competitor_notes:
            lines.append(f"- {n}")
        lines.append("")
    if output.findings.positioning_angles:
        lines.append("### Positioning angles")
        lines.append("")
        for a in output.findings.positioning_angles:
            lines.append(f"- {a}")
        lines.append("")
    if output.findings.proof_points:
        lines.append("### Proof points")
        lines.append("")
        for p in output.findings.proof_points:
            lines.append(f"- {p}")
        lines.append("")
    if output.findings.risks:
        lines.append("### Risks")
        lines.append("")
        for r in output.findings.risks:
            lines.append(f"- {r}")
        lines.append("")

    # Brief sections
    lines.append("## Brief")
    lines.append("")
    lines.append("### Positioning statement")
    lines.append("")
    lines.append(output.brief.positioning_statement)
    lines.append("")
    lines.append("### Key messages")
    lines.append("")
    for m in output.brief.key_messages:
        lines.append(f"- {m}")
    lines.append("")
    lines.append("### Objections & Responses")
    lines.append("")
    for o in output.brief.objections_and_responses:
        lines.append(f"- **Objection:** {o.objection}")
        lines.append(f"  - Response: {o.response}")
    lines.append("")
    lines.append("### Launch plan")
    lines.append("")
    for s in output.brief.launch_plan:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("### SEO keywords")
    lines.append("")
    for k in output.brief.seo_keywords:
        lines.append(f"- {k}")
    lines.append("")
    lines.append("### Content ideas")
    lines.append("")
    for i in output.brief.content_ideas:
        lines.append(f"- {i}")
    lines.append("")

    # Sources (numbered links)
    lines.append("## Sources")
    lines.append("")
    for i, src in enumerate(output.sources, start=1):
        title = src.title or src.url
        lines.append(f"{i}. [{title}]({src.url})")
        if src.snippet:
            lines.append(f"   {src.snippet}")
    lines.append("")

    return "\n".join(lines)


def validate_completeness(output: BriefOutput) -> list[dict[str, str]]:
    """Return structured issues with severity for an incomplete brief.
    
    Returns list of dicts with keys:
    - severity: "hard" | "soft"
    - message: str
    """
    issues: list[dict[str, str]] = []

    # Hard fails: missing required fields, sources < 3, market_summary < 80 chars
    pos = output.brief.positioning_statement
    if not pos or not pos.strip():
        issues.append({"severity": "hard", "message": "Missing positioning_statement"})

    if len(output.sources) < 3:
        issues.append({
            "severity": "hard",
            "message": f"Too few sources (need >= 3, got {len(output.sources)})"
        })

    if len(output.findings.market_summary.strip()) < 80:
        issues.append({
            "severity": "hard",
            "message": (
                "market_summary too short (need >= 80 characters, "
                f"got {len(output.findings.market_summary.strip())})"
            )
        })

    # Soft fails: seo_keywords < 8, content_ideas < 6, objections < 3, launch_plan < 5
    n_kw = len(output.brief.seo_keywords)
    if n_kw < 8:
        issues.append({
            "severity": "soft",
            "message": f"Too few seo_keywords (need >= 8, got {n_kw})"
        })

    n_ideas = len(output.brief.content_ideas)
    if n_ideas < 6:
        issues.append({
            "severity": "soft",
            "message": f"Too few content_ideas (need >= 6, got {n_ideas})"
        })

    n_obj = len(output.brief.objections_and_responses)
    if n_obj < 3:
        issues.append({
            "severity": "soft",
            "message": f"Too few objections_and_responses (need >= 3, got {n_obj})"
        })
    else:
        for i, o in enumerate(output.brief.objections_and_responses):
            if not (o.objection and o.objection.strip()):
                issues.append({
                    "severity": "hard",
                    "message": f"objections_and_responses[{i}]: objection is empty"
                })
            if not (o.response and o.response.strip()):
                issues.append({
                    "severity": "hard",
                    "message": f"objections_and_responses[{i}]: response is empty"
                })

    n_launch = len(output.brief.launch_plan)
    if n_launch < 5:
        issues.append({
            "severity": "soft",
            "message": f"Too few launch_plan (need >= 5, got {n_launch})"
        })

    return issues
