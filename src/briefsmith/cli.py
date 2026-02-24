"""Typer CLI for Briefsmith."""

import json
from datetime import UTC, datetime
from pathlib import Path

import typer
from pydantic import BaseModel

from briefsmith.llm import OllamaClient, generate_structured, generate_text
from briefsmith.schemas import (
    BriefInput,
    BriefOutput,
    BriefSections,
    ResearchFindings,
    SourceItem,
    WorkflowState,
    to_markdown,
    validate_completeness,
)
from briefsmith.runs import RunMetadata, RunStore
from briefsmith.tools import DuckDuckGoSearchClient, SearchCache
from briefsmith.workflows import build_graph

app = typer.Typer(
    name="briefsmith",
    help="Multi-agent workflow automator.",
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def root_callback(ctx: typer.Context) -> None:
    """Root callback; subcommands handle the rest."""
    if ctx.invoked_subcommand is not None:
        return
    # No subcommand: show help
    typer.echo(ctx.get_help())


@app.command()
def hello() -> None:
    """Print a hello world message."""
    typer.echo("Hello world!")


class _LlmCheckModel(BaseModel):
    """Tiny model for llm-check structured output test."""

    answer: str = "ok"


@app.command()
def llm_check() -> None:
    """Verify Ollama connection: plain text then structured JSON."""
    typer.echo("Checking Ollama connection...")
    client = OllamaClient()
    try:
        out = generate_text(
            client,
            system="You are a helpful assistant.",
            prompt="Reply with exactly: OK",
        )
        typer.echo(f"Plain text: {out.strip()!r}")
    except Exception as e:
        typer.echo(f"Plain text failed: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo("Testing structured output (expect JSON with 'answer' field)...")
    try:
        obj = generate_structured(
            client,
            system="You output JSON only.",
            prompt="Return JSON: {\"answer\": \"ok\"}",
            model=_LlmCheckModel,
            max_retries=2,
        )
        typer.echo(f"Validated: {obj!r}")
    except Exception as e:
        typer.echo(f"Structured output failed: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo("llm-check passed.")


DEFAULT_INPUT_PATH = Path("inputs/sample.json")
DEFAULT_OUTDIR = Path("runs")


def _findings_to_markdown(findings: ResearchFindings) -> str:
    """Render findings as simple markdown (findings only)."""
    lines = [
        "# Research findings",
        "",
        "## Market summary",
        "",
        findings.market_summary,
        "",
    ]
    if findings.competitor_notes:
        lines.extend(["## Competitor notes", ""])
        for n in findings.competitor_notes:
            lines.append(f"- {n}")
        lines.append("")
    if findings.positioning_angles:
        lines.extend(["## Positioning angles", ""])
        for a in findings.positioning_angles:
            lines.append(f"- {a}")
        lines.append("")
    if findings.proof_points:
        lines.extend(["## Proof points", ""])
        for p in findings.proof_points:
            lines.append(f"- {p}")
        lines.append("")
    if findings.risks:
        lines.extend(["## Risks", ""])
        for r in findings.risks:
            lines.append(f"- {r}")
        lines.append("")
    return "\n".join(lines)


@app.command()
def sample_input(
    path: Path = typer.Option(
        DEFAULT_INPUT_PATH,
        "--path",
        "-p",
        help="Path for sample input JSON.",
        path_type=Path,
    ),
) -> None:
    """Write a sample BriefInput JSON template if the file does not exist."""
    if path.exists():
        typer.echo(f"Already exists: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = BriefInput(
        product_name="My Product",
        product_description="A clear, compelling description of at least 20 chars.",
        target_audience="Product managers and team leads",
        competitors=["Competitor A", "Competitor B"],
        tone="clear",
        region="US",
        channels=["web", "email"],
        constraints=[],
    )
    path.write_text(sample.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Created: {path}")


@app.command()
def run(
    input_path: Path = typer.Option(
        DEFAULT_INPUT_PATH,
        "--input",
        "-i",
        help="Path to BriefInput JSON file.",
        path_type=Path,
    ),
    outdir: Path = typer.Option(
        DEFAULT_OUTDIR,
        "--outdir",
        "-o",
        help="Directory for output files.",
        path_type=Path,
    ),
) -> None:
    """Run full workflow (planner -> ... -> critic) and save outputs."""
    if not input_path.exists():
        typer.echo(f"Input file not found: {input_path}", err=True)
        raise typer.Exit(1)

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
        brief_input = BriefInput.model_validate(data)
    except Exception as e:
        typer.echo(f"Invalid input JSON: {e}", err=True)
        raise typer.Exit(1) from e

    llm = OllamaClient()
    cache = SearchCache()
    search = DuckDuckGoSearchClient(cache=cache)
    graph = build_graph(llm, search)

    store = RunStore(base_dir=outdir)

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

    typer.echo("Running workflow (planner -> ... -> writer -> critic)...")
    try:
        final = graph.invoke(state_dict)
    except Exception as e:
        typer.echo(f"Workflow failed: {e}", err=True)
        raise typer.Exit(1) from e

    # Persist artifacts via RunStore
    run_id = store.create_run(brief_input)

    sources = final.get("sources") or []
    store.save_json(run_id, "sources.json", sources)

    findings_data = final.get("findings")
    if findings_data is not None:
        store.save_json(run_id, "findings.json", findings_data)
        findings = ResearchFindings.model_validate(findings_data)
        md = _findings_to_markdown(findings)
        store.save_artifact(run_id, "findings.md", md.encode("utf-8"), "text/markdown")

    brief_data = final.get("brief")
    if brief_data is not None:
        store.save_json(run_id, "brief.json", brief_data)
        brief = BriefSections.model_validate(brief_data)
        if findings_data is not None and sources:
            source_list = [SourceItem.model_validate(s) for s in sources]
            output = BriefOutput(
                input=brief_input,
                findings=ResearchFindings.model_validate(findings_data),
                brief=brief,
                sources=source_list,
                metadata=final.get("metadata") or {},
            )
            final_md = to_markdown(output)
            store.save_artifact(
                run_id, "final_brief.md", final_md.encode("utf-8"), "text/markdown"
            )

    meta = final.get("metadata") or {}
    approval_status = final.get("approval_status", "pending")
    run_metadata = RunMetadata(
        run_id=run_id,
        created_at=datetime.now(UTC),
        approval_status=str(approval_status),
        revision_count=int(meta.get("revision_count", 0)),
        ollama_model=str(meta.get("writer_model", "ollama")),
        search_provider="duckduckgo",
        durations_ms=meta.get("durations_ms") or {},
        notes=final.get("revision_notes"),
    )
    store.save_json(run_id, "run_metadata.json", run_metadata)

    typer.echo("")
    typer.echo("Summary")
    typer.echo("  run_id:         " + run_id)
    typer.echo("  approval_status: " + str(approval_status))
    typer.echo("  revision_count:  " + str(run_metadata.revision_count))

    # Print critic notes even if approved
    revision_notes = final.get("revision_notes")
    if revision_notes:
        typer.echo("")
        typer.echo("Critic notes:")
        for line in revision_notes.split("\n"):
            typer.echo("  " + line)
    
    # If revise, show top 5 issues
    if (
        approval_status == "revise"
        and brief_data is not None
        and findings_data is not None
    ):
        try:
            brief = BriefSections.model_validate(brief_data)
            source_list = [SourceItem.model_validate(s) for s in sources]
            output = BriefOutput(
                input=brief_input,
                findings=ResearchFindings.model_validate(findings_data),
                brief=brief,
                sources=source_list,
                metadata=final.get("metadata") or {},
            )
            issues = validate_completeness(output)
            if issues:
                typer.echo("")
                typer.echo("Top issues:")
                for issue in issues[:5]:
                    severity = issue.get("severity", "unknown")
                    message = issue.get("message", "")
                    typer.echo(f"  [{severity.upper()}] {message}")
        except Exception:
            pass  # Skip if we can't validate
    
    run_dir = store.path_for(run_id, "run_metadata.json").parent
    typer.echo("")
    typer.echo("  outputs:        " + str(run_dir.absolute()))
    if approval_status == "revise":
        typer.echo("  Note: Review run directory for details.")
    typer.echo("Done.")


@app.command()
def runs(
    base_dir: Path = typer.Option(
        Path("runs"),
        "--base-dir",
        "-b",
        help="Base directory where runs are stored.",
        path_type=Path,
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Maximum number of recent runs to list.",
    ),
) -> None:
    """List recent runs from the run registry."""
    store = RunStore(base_dir=base_dir)
    items = store.list_runs(limit=limit)
    if not items:
        typer.echo("No runs found.")
        return

    for meta in items:
        created = meta.created_at.isoformat()
        typer.echo(
            f"{meta.run_id}  {created}  status={meta.approval_status} "
            f"revisions={meta.revision_count}"
        )


if __name__ == "__main__":
    app()
