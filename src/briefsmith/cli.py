"""Typer CLI for Briefsmith."""

from pydantic import BaseModel

import typer

from briefsmith.llm import OllamaClient, generate_structured, generate_text

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


if __name__ == "__main__":
    app()
