"""Bash tool implementation."""

from __future__ import annotations

import re
import shlex
import subprocess
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
    "Execute or stage a shell command, depending on the active route.",
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


def run_direct(params: dict[str, Any]) -> dict[str, Any]:
    command = str(params.get("command") or "").strip()
    if not command:
        return error_result("missing-command", "missing command")
    try:
        completed = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return error_result("bash-failed", str(exc))
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return {
        "ok": completed.returncode == 0,
        "content": [
            {
                "type": "text",
                "text": direct_output_text(
                    command, completed.returncode, stdout, stderr
                ),
            }
        ],
        "metadata": {
            "mode": "direct",
            "command": command,
            "status": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
        },
    }


def direct_output_text(command: str, status: int, stdout: str, stderr: str) -> str:
    sections = [
        f"$ {command}",
        f"exit {status}",
    ]
    if stdout:
        sections.extend(["stdout:", stdout])
    if stderr:
        sections.extend(["stderr:", stderr])
    return "\n".join(sections)
