"""Directory listing tool implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import ToolSpec, analysis, effect, error_result

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "path": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1},
    },
}

SPEC = ToolSpec("ls", "List directory contents.", SCHEMA)


def analyze(params: dict[str, Any]) -> dict[str, Any]:
    path = str(params.get("path") or ".")
    return analysis(effects=[effect("read", path)])


def run(params: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(params.get("path") or "."))
    limit = int(params.get("limit") or 200)
    try:
        entries = sorted(
            path.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name)
        )
    except OSError as exc:
        return error_result("ls-failed", str(exc))
    lines = []
    for entry in entries[:limit]:
        name = entry.name + ("/" if entry.is_dir() else "")
        lines.append(name)
    omitted = max(len(entries) - limit, 0)
    if omitted:
        lines.append(f"... {omitted} more")
    return {
        "ok": True,
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "metadata": {"path": str(path), "limit": limit, "entries": len(entries)},
    }
