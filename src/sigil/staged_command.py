"""State plumbing for staged commands.

Pi can propose a command through its bash tool call. Sigil blocks that execution
in a Pi extension, stages the proposed command here, and lets the shell binding
put the command back under the user's cursor.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

from .state import append_event, read_jsonl, session_dir, write_jsonl

PENDING_STAGED_COMMANDS_FILE = "pending-staged-commands.jsonl"
LAST_STAGED_COMMAND_FILE = "last-staged-command.jsonl"
STAGED_COMMAND_EXTENSION = "pi_extensions/staged_command.ts"


def staged_command_extension_path() -> Path | None:
    """Return the bundled Pi extension path if it is available on disk."""
    resource = files("sigil").joinpath(STAGED_COMMAND_EXTENSION)
    if not resource.is_file():
        return None
    return Path(str(resource))


def prepare_staged_commands() -> Path:
    """Clear stale staged-command state and return the pending file path."""
    root = session_dir()
    root.mkdir(parents=True, exist_ok=True)
    for name in (PENDING_STAGED_COMMANDS_FILE, LAST_STAGED_COMMAND_FILE):
        path = root / name
        if path.exists():
            path.unlink()
    return root / PENDING_STAGED_COMMANDS_FILE


def record_staged_commands(
    *,
    glyph: str,
) -> list[dict[str, Any]]:
    """Promote raw staged commands into Sigil session state."""
    records = []
    for raw in read_jsonl(PENDING_STAGED_COMMANDS_FILE):
        command = str(raw.get("command") or "").strip()
        if not command:
            continue
        event = append_event(
            {
                "type": "staged_command",
                "command": command,
                "tool_call_id": raw.get("toolCallId"),
                "source": "pi_tool_call",
                "glyph": glyph,
            }
        )
        records.append(
            {
                "event_id": event["id"],
                "command": command,
                "tool_call_id": raw.get("toolCallId"),
                "source": "pi_tool_call",
                "glyph": glyph,
            }
        )

    write_jsonl(LAST_STAGED_COMMAND_FILE, records)
    (session_dir() / PENDING_STAGED_COMMANDS_FILE).unlink(missing_ok=True)
    return records


def latest_staged_command() -> dict[str, Any] | None:
    """Return the latest command staged from Pi, if any."""
    records = read_jsonl(LAST_STAGED_COMMAND_FILE)
    if not records:
        return None
    return records[-1]


def consume_latest_staged_command() -> dict[str, Any] | None:
    """Return and clear the latest staged command."""
    record = latest_staged_command()
    write_jsonl(LAST_STAGED_COMMAND_FILE, [])
    return record
