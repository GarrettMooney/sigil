"""Write handoff tool implementation."""

from __future__ import annotations

import shlex
from typing import Any

from .base import ToolSpec, analysis, effect, error_result, handoff, missing, write_temp

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["path", "content"],
    "properties": {
        "path": {"type": "string"},
        "content": {"type": "string"},
        "reason": {"type": "string"},
    },
}

SPEC = ToolSpec(
    "write",
    "Write content to an artifact and stage cp.",
    SCHEMA,
    True,
)


def analyze(params: dict[str, Any]) -> dict[str, Any]:
    path = str(params.get("path") or "")
    if not path:
        return missing("path")
    return analysis(effects=[effect("write", path)])


def run(params: dict[str, Any]) -> dict[str, Any]:
    dest = str(params.get("path") or "")
    if not dest:
        return error_result("missing-path", "missing path")
    content = str(params.get("content") or "")
    path = write_temp("zeta-write-", ".tmp", content)
    return handoff(
        f"cp {shlex.quote(str(path))} {shlex.quote(dest)}",
        str(params.get("reason") or f"Write {dest}."),
        artifact=str(path),
    )
