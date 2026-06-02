"""Grep tool implementation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .base import ToolSpec, analysis, effect, error_result, missing

MAX_TOOL_RESULT_CHARS = 12_000

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["pattern"],
    "properties": {
        "pattern": {"type": "string"},
        "path": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1},
    },
}

SPEC = ToolSpec("grep", "Search text with ripgrep or a Python fallback.", SCHEMA)


def analyze(params: dict[str, Any]) -> dict[str, Any]:
    path = str(params.get("path") or ".")
    pattern = str(params.get("pattern") or "")
    if not pattern:
        return missing("pattern")
    return analysis(effects=[effect("search", path)])


def run(params: dict[str, Any]) -> dict[str, Any]:
    pattern = str(params.get("pattern") or "")
    path = str(params.get("path") or ".")
    limit = int(params.get("limit") or 100)
    if not pattern:
        return error_result("missing-pattern", "missing pattern")
    try:
        proc = subprocess.run(
            ["rg", "--line-number", "--max-count", str(limit), pattern, path],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        text = proc.stdout if proc.returncode in {0, 1} else proc.stderr
    except FileNotFoundError:
        text = grep_fallback(pattern, Path(path), limit)
    return {
        "ok": True,
        "content": [{"type": "text", "text": text[:MAX_TOOL_RESULT_CHARS]}],
        "metadata": {"pattern": pattern, "path": path},
    }


def grep_fallback(pattern: str, root: Path, limit: int) -> str:
    matches: list[str] = []
    paths = [root] if root.is_file() else root.rglob("*")
    for path in paths:
        if len(matches) >= limit:
            break
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for index, line in enumerate(lines, start=1):
            if pattern in line:
                matches.append(f"{path}:{index}:{line}")
                if len(matches) >= limit:
                    break
    return "\n".join(matches)
