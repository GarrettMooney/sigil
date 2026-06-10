"""The `ask` verb: ask about shell context, optionally continuing the prior one."""

from __future__ import annotations

import click

from ..workflows.ask import (
    ZETA_ASK_TOOLS,
    ask,
    discussion_turns,
)
from ._base import cli
from ._shared import piped_stdin_text, question_with_stdin

DEFAULT_QUESTION = "Inspect and summarize the current shell context."


@cli.command("ask")
@click.argument("question", required=False)
@click.option("--follow-up", is_flag=True, help="Continue the previous ask thread.")
@click.option("--json", "json_output", is_flag=True, help="Emit the answer as JSON.")
def cmd_ask(question: str | None, follow_up: bool, json_output: bool) -> int:
    """Ask a shell question, optionally continuing the prior ask."""
    stdin_text = piped_stdin_text()
    if follow_up:
        prompt = question_with_stdin(question or "", stdin_text or "")
        history = discussion_turns()
        return ask(
            prompt,
            glyph="ask",
            tools=ZETA_ASK_TOOLS,
            follow_up=True,
            json_output=json_output,
            history=history,
        )
    if stdin_text is not None:
        prompt = question_with_stdin(question or "", stdin_text)
        return ask(
            prompt,
            glyph="ask",
            tools=ZETA_ASK_TOOLS,
            json_output=json_output,
        )
    return ask(
        question or DEFAULT_QUESTION,
        glyph="ask",
        tools=ZETA_ASK_TOOLS,
        json_output=json_output,
    )
