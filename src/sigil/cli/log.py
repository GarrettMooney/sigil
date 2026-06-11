"""The `log` group: queries over the delegation ledger."""

from __future__ import annotations

import os
import re
import time
from typing import Any

import click

from ._base import cli
from ._shared import pretty_print_json

DEFAULT_LOG_LIMIT = 20
SINCE_PATTERN = re.compile(r"(\d+)([dhm])")
SINCE_SCALES = {"d": 86400, "h": 3600, "m": 60}


@cli.group("log", invoke_without_command=True)
@click.option(
    "--touched",
    help="Only turns that wrote or edited PATH through the write/edit tools.",
)
@click.option("--workflow", help="Only turns from this workflow (ask|propose|do|run).")
@click.option(
    "--since",
    help="Only turns at or after a time: YYYY-MM-DD, or an age like 2d, 6h, 30m.",
)
@click.option("--failed", is_flag=True, help="Only failed or aborted turns.")
@click.option("--session", "session_filter", help="Scope to one session id.")
@click.option("--all-sessions", is_flag=True, help="Query every session.")
@click.option(
    "--limit",
    default=DEFAULT_LOG_LIMIT,
    show_default=True,
    type=int,
    help="Maximum number of turns.",
)
@click.option("--cost", "show_cost", is_flag=True, help="Append token and call counts.")
@click.option("--json", "json_output", is_flag=True, help="Emit raw turn records.")
@click.pass_context
def cmd_log(
    ctx: click.Context,
    touched: str | None,
    workflow: str | None,
    since: str | None,
    failed: bool,
    session_filter: str | None,
    all_sessions: bool,
    limit: int,
    show_cost: bool,
    json_output: bool,
) -> int:
    """List ledger turns for this session, newest first.

    Every delegation and recorded shell command is one turn. Subcommands
    query deeper; `sigil events` stays the raw event view.
    """
    if ctx.invoked_subcommand is not None:
        return 0
    # Imported lazily: `sigil.cli` must stay light at import time.
    from ..ledger import default_ledger_index
    from ..state import session_id

    session = None if all_sessions else (session_filter or session_id())
    turns = default_ledger_index().query_turns(
        session=session,
        workflow=workflow,
        since=since_epoch(since) if since else None,
        failed=failed,
        touched=touched_path_variants(touched) if touched else None,
        limit=limit,
    )
    if json_output:
        pretty_print_json({"turns": turns})
        return 0
    if not turns:
        click.echo("no turns recorded", err=True)
        return 0
    for turn in turns:
        click.echo(format_turn_line(turn, show_cost=show_cost))
    return 0


def since_epoch(value: str) -> float:
    """Parse an absolute date or relative age into an epoch lower bound."""
    relative = SINCE_PATTERN.fullmatch(value.strip())
    if relative is not None:
        return time.time() - int(relative.group(1)) * SINCE_SCALES[relative.group(2)]
    try:
        parsed = time.strptime(value.strip(), "%Y-%m-%d")
    except ValueError as error:
        raise click.BadParameter(
            "expected YYYY-MM-DD or an age like 2d, 6h, 30m"
        ) from error
    return time.mktime(parsed)


def touched_path_variants(path: str) -> tuple[str, ...]:
    """Return the path as given plus its absolute form, deduplicated."""
    variants = [path]
    absolute = os.path.abspath(path)
    if absolute not in variants:
        variants.append(absolute)
    return tuple(variants)


def format_turn_line(turn: dict[str, Any], *, show_cost: bool) -> str:
    """Format one ledger turn as a log listing line."""
    from ..display.summarize import first_line, truncate

    turn_id = str(turn.get("turn_id") or "")[:8]
    when = format_turn_time(turn.get("time"))
    workflow = str(turn.get("workflow") or "?")
    outcome = str(turn.get("outcome") or "?")
    objective = truncate(first_line(str(turn.get("objective") or "")), 72)
    line = f"{turn_id:<8}  {when}  {workflow:<7} {outcome:<9} {objective}".rstrip()
    if show_cost:
        line += cost_suffix(turn.get("cost"))
    return line


def format_turn_time(value: Any) -> str:
    """Render an epoch timestamp as a compact local time."""
    if not isinstance(value, (int, float)):
        return "?" * 11
    return time.strftime("%m-%d %H:%M", time.localtime(value))


def cost_suffix(cost: Any) -> str:
    """Render a turn's cost block as a listing suffix."""
    if not isinstance(cost, dict):
        return ""
    tokens = int(cost.get("input_tokens") or 0) + int(cost.get("output_tokens") or 0)
    calls = int(cost.get("model_calls") or 0)
    if not tokens and not calls:
        return ""
    return f"  · {tokens} tok · {calls} calls"


@cmd_log.command("reindex")
def cmd_log_reindex() -> int:
    """Rebuild the ledger index from the event log."""
    # Imported lazily: `sigil.cli` must stay light at import time.
    from ..ledger import default_ledger_index, reindex

    turns, effects = reindex(default_ledger_index())
    click.echo(f"indexed {turns} turn record(s), {effects} effect record(s)")
    return 0


@cmd_log.command("show")
@click.argument("turn_id")
@click.option("--json", "json_output", is_flag=True, help="Emit the raw records.")
def cmd_log_show(turn_id: str, json_output: bool) -> int:
    """Show one turn record in full: contract, cost, effects, prompts.

    TURN_ID may be a full id or a unique prefix.
    """
    from ..ledger import default_ledger_index

    index = default_ledger_index()
    resolved = resolve_turn_id(index, turn_id)
    turn = index.turn(resolved)
    if turn is None:
        raise click.ClickException(f"turn not found: {turn_id}")
    effects = index.effects_for_turn(resolved)
    if json_output:
        pretty_print_json({"turn": turn, "effects": effects})
        return 0
    for line in render_turn_record(turn, effects):
        click.echo(line)
    return 0


@cli.command("blame")
@click.argument("file")
def cmd_blame(file: str) -> int:
    """List every turn that wrote or edited FILE, oldest first.

    Covers writes made through the write/edit tools, which record paths
    and content hashes. Bash commands record what ran, not which files
    it touched — find those with `sigil log` and the command text.
    """
    from ..ledger import default_ledger_index

    index = default_ledger_index()
    effects: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in touched_path_variants(file):
        for effect in index.effects_touching(path):
            effect_id = str(effect.get("effect_id") or "")
            if effect_id not in seen:
                seen.add(effect_id)
                effects.append(effect)
    effects.sort(key=lambda effect: effect.get("time") or 0.0)
    if not effects:
        click.echo(f"no recorded writes touch {file}", err=True)
        return 0
    for effect in effects:
        turn = index.turn(str(effect.get("turn_id") or ""))
        for line in render_blame_block(effect, turn):
            click.echo(line)
    return 0


def resolve_turn_id(index: Any, token: str) -> str:
    """Resolve a full turn id or unique prefix, mirroring the trace resolver."""
    if index.turn(token) is not None:
        return token
    matches = index.turn_ids_with_prefix(token)
    if len(matches) == 1:
        return matches[0]
    if matches:
        candidates = "\n  ".join(matches)
        raise click.ClickException(
            f"ambiguous turn id '{token}' matches:\n  {candidates}"
        )
    raise click.ClickException(f"turn not found: {token}")


def render_turn_record(
    turn: dict[str, Any],
    effects: list[dict[str, Any]],
) -> list[str]:
    """Render one turn record as human-readable lines."""
    lines = [
        f"turn     {turn.get('turn_id') or '?'}",
        f"time     {format_turn_time(turn.get('time'))}",
        f"session  {turn.get('session') or '?'}",
        f"workflow {turn.get('workflow') or '?'}",
        f"outcome  {turn.get('outcome') or '?'}",
    ]
    objective = str(turn.get("objective") or "").strip()
    if objective:
        lines.extend(["", "objective"])
        lines.extend(f"  {line}" for line in objective.splitlines()[:8])
    contract = turn.get("contract")
    if isinstance(contract, dict):
        tools = ", ".join(str(tool) for tool in contract.get("allowed_tools") or [])
        staged = " (staged)" if contract.get("staged") else ""
        lines.extend(["", "contract", f"  tools: {tools or 'none'}{staged}"])
    agent = turn.get("agent")
    if isinstance(agent, dict):
        endpoint = " @ ".join(
            part for part in (agent.get("model"), agent.get("url")) if part
        )
        if endpoint:
            lines.extend(["", "agent", f"  {endpoint}"])
    cost_line = format_cost_block(turn.get("cost"))
    if cost_line:
        lines.extend(["", "cost", f"  {cost_line}"])
    if effects:
        lines.extend(["", "effects"])
        lines.extend(f"  {format_effect_line(effect)}" for effect in effects)
    prompt_ids = turn.get("prompt_object_ids")
    if isinstance(prompt_ids, list) and prompt_ids:
        from ..display.summarize import short_trace_id

        shorts = " ".join(short_trace_id(str(value)) for value in prompt_ids)
        lines.extend(["", "prompts", f"  {shorts}  (sigil zeta trace show ID)"])
    return lines


def render_blame_block(
    effect: dict[str, Any],
    turn: dict[str, Any] | None,
) -> list[str]:
    """Render one touching effect joined to its turn."""
    from ..display.summarize import first_line, short_trace_id, truncate

    when = format_turn_time(effect.get("time"))
    workflow = str((turn or {}).get("workflow") or "?")
    outcome = str((turn or {}).get("outcome") or "?")
    kind = str(effect.get("kind") or "?")
    turn_id = str(effect.get("turn_id") or "?")[:8]
    lines = [f"{when}  {workflow:<7} {outcome:<9} {kind:<10} turn {turn_id}"]
    objective = truncate(first_line(str((turn or {}).get("objective") or "")), 72)
    detail = [objective] if objective else []
    prompt_ids = (turn or {}).get("prompt_object_ids")
    if isinstance(prompt_ids, list) and prompt_ids:
        shorts = " ".join(short_trace_id(str(value)) for value in prompt_ids)
        detail.append(f"prompts {shorts}")
    if detail:
        lines.append("  " + " · ".join(detail))
    return lines


def format_effect_line(effect: dict[str, Any]) -> str:
    """Render one effect record as a single listing line."""
    from ..display.summarize import short_trace_id, truncate

    kind = str(effect.get("kind") or "?")
    parts = [f"{kind:<10}"]
    path = effect.get("path")
    if path:
        parts.append(str(path))
    command = effect.get("command")
    if command:
        parts.append(truncate(str(command), 60))
    before = effect.get("before_hash")
    after = effect.get("after_hash")
    if before or after:
        parts.append(
            f"{short_trace_id(str(before or '?'))}→{short_trace_id(str(after or '?'))}"
        )
    exit_status = effect.get("exit_status")
    if isinstance(exit_status, int):
        parts.append(f"exit {exit_status}")
    if effect.get("staged"):
        outcome = effect.get("resolved_outcome")
        parts.append(f"staged → {outcome}" if outcome else "staged")
    return " ".join(parts).rstrip()


def format_cost_block(cost: Any) -> str:
    """Render the turn cost block as one line."""
    if not isinstance(cost, dict):
        return ""
    tokens_in = int(cost.get("input_tokens") or 0)
    tokens_out = int(cost.get("output_tokens") or 0)
    parts = []
    if tokens_in or tokens_out:
        parts.append(f"{tokens_in + tokens_out} tok ({tokens_in} in, {tokens_out} out)")
    calls = int(cost.get("model_calls") or 0)
    if calls:
        parts.append(f"{calls} calls")
    wall_ms = cost.get("wall_ms")
    if isinstance(wall_ms, int):
        parts.append(f"{wall_ms} ms")
    return " · ".join(parts)
