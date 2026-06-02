"""The `command` verb: generate a single command proposal."""

from __future__ import annotations

import click

from ._base import cli
from ._shared import piped_stdin_text, print_json_line
from ..operators import run_command_proposal


@cli.command("command")
@click.argument("prompt", required=False)
@click.option("--json", "json_output", is_flag=True)
def cmd_command(
    prompt: str | None,
    json_output: bool,
) -> int:
    """Generate a single command proposal."""
    stdin_text = piped_stdin_text()
    if stdin_text is None and prompt is None:
        raise click.UsageError("PROMPT is required unless stdin is piped.")
    try:
        result = run_command_proposal(
            prompt=prompt or "",
            stdin=stdin_text or "",
            mode="pipeline" if stdin_text is not None else "interactive",
        )
    except RuntimeError as exc:
        click.echo(f"sigil command: {exc}", err=True)
        raise click.exceptions.Exit(1) from exc
    if json_output:
        print_json_line(
            {
                "prompt": prompt or "",
                "command": result.command,
                "explanation": result.explanation,
            }
        )
        return 0
    print(result.output, end="" if result.output.endswith("\n") else "\n")
    return 0
