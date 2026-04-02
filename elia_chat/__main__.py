"""Elia research-agent CLI."""

import click

from elia_chat.app import AgentResearchApp


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Run the research-agent chat tool."""
    if ctx.invoked_subcommand is None:
        AgentResearchApp().run()


@cli.command("run")
def run_app() -> None:
    """Run as terminal Textual app."""
    AgentResearchApp().run()


@cli.command("web")
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8000, type=int)
def run_web(host: str, port: int) -> None:
    """Run via Textual web server mode."""
    app = AgentResearchApp()
    try:
        app.run(web=True, host=host, port=port)
    except TypeError:
        # Backward-compatible fallback for older Textual builds.
        app.run(web=True)


if __name__ == "__main__":
    cli()
