"""Typer CLI for Briefsmith."""

import json
from pathlib import Path

import typer
from pydantic import BaseModel

from briefsmith.llm import OllamaClient, generate_structured, generate_text
from briefsmith.schemas import BriefInput, ResearchFindings, WorkflowState
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
DEFAULT_OUTDIR = Path("outputs")


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
    """Run the planner -> researcher -> synthesizer workflow and save outputs."""
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

    initial = WorkflowState(
        input=brief_input,
        plan=None,
        sources=[],
        findings=None,
        brief=None,
        approval_status="pending",
        revision_notes=None,
        metadata={},
    )
    state_dict = initial.model_dump(mode="json")

    typer.echo("Running workflow (planner -> researcher -> synthesizer)...")
    try:
        final = graph.invoke(state_dict)
    except Exception as e:
        typer.echo(f"Workflow failed: {e}", err=True)
        raise typer.Exit(1) from e

    outdir.mkdir(parents=True, exist_ok=True)

    sources = final.get("sources") or []
    outdir.joinpath("sources.json").write_text(
        json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    typer.echo(f"Wrote {outdir / 'sources.json'}")

    findings_data = final.get("findings")
    if findings_data is not None:
        outdir.joinpath("findings.json").write_text(
            json.dumps(findings_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        typer.echo(f"Wrote {outdir / 'findings.json'}")
        findings = ResearchFindings.model_validate(findings_data)
        md = _findings_to_markdown(findings)
        outdir.joinpath("findings.md").write_text(md, encoding="utf-8")
        typer.echo(f"Wrote {outdir / 'findings.md'}")

    run_meta = {
        "metadata": final.get("metadata") or {},
        "sources_count": len(sources),
        "has_findings": findings_data is not None,
    }
    outdir.joinpath("run_metadata.json").write_text(
        json.dumps(run_meta, indent=2), encoding="utf-8"
    )
    typer.echo(f"Wrote {outdir / 'run_metadata.json'}")
    typer.echo("Done.")


if __name__ == "__main__":
    app()
