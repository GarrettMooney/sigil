"""Bash handoff tool implementation."""

from __future__ import annotations

import re
import shlex
from typing import Any

from .base import ToolSpec, analysis, diagnostic, effect, error_result, handoff, missing

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["command"],
    "properties": {
        "command": {"type": "string"},
        "reason": {"type": "string"},
    },
}

SPEC = ToolSpec(
    "bash",
    "Stage a shell command into the user's prompt.",
    SCHEMA,
    True,
)

SHELL_META_PATTERN = re.compile(r"[|&;<>()`$*?{}\[\]~]")


def analyze(params: dict[str, Any]) -> dict[str, Any]:
    command = str(params.get("command") or "").strip()
    if not command:
        return missing("command")
    diagnostics = []
    resolved = True
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        argv = []
        resolved = False
        diagnostics.append(diagnostic("shell-parse-error", str(exc)))
    if SHELL_META_PATTERN.search(command):
        resolved = False
        diagnostics.append(
            diagnostic("shell-grammar", "command contains shell grammar")
        )
    target = argv[0] if argv else command
    return analysis(
        resolved=resolved,
        effects=[effect("execute", target, resource="process")],
        diagnostics=diagnostics,
    )


def run(params: dict[str, Any]) -> dict[str, Any]:
    command = str(params.get("command") or "").strip()
    if not command:
        return error_result("missing-command", "missing command")
    return handoff(command, str(params.get("reason") or "Run the proposed command."))
