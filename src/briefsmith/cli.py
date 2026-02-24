"""Typer CLI for Briefsmith."""

import typer

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


def main() -> None:
    """Entry point for the briefsmith CLI."""
    app()


if __name__ == "__main__":
    main()
