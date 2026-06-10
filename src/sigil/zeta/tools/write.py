"""Write tool implementation."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from .base import (
    ToolSpec,
    analysis,
    content_hash,
    effect,
    error_result,
    file_content_hash,
    handoff,
    missing,
    write_temp,
)

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
    "Write content directly or stage a cp handoff, depending on the active workflow.",
    SCHEMA,
    interactive=True,
    effects=("write",),
)


def analyze(params: dict[str, Any]) -> dict[str, Any]:
    path = str(params.get("path") or "")
    if not path:
        return missing("path")
    return analysis(effects=[effect("write", path)])


def stage(params: dict[str, Any]) -> dict[str, Any]:
    dest = str(params.get("path") or "")
    if not dest:
        return error_result("missing-path", "missing path")
    content = str(params.get("content") or "")
    path = write_temp("zeta-write-", ".tmp", content)
    result = handoff(
        f"cp {shlex.quote(str(path))} {shlex.quote(dest)}",
        str(params.get("reason") or f"Write {dest}."),
        artifact=str(path),
    )
    result["metadata"] = write_hashes(dest, content) | {"path": dest}
    return result


def run(params: dict[str, Any]) -> dict[str, Any]:
    dest = str(params.get("path") or "")
    if not dest:
        return error_result("missing-path", "missing path")
    content = str(params.get("content") or "")
    hashes = write_hashes(dest, content)
    try:
        Path(dest).write_text(content, encoding="utf-8")
    except OSError as exc:
        return error_result("write-failed", str(exc))
    return {
        "ok": True,
        "content": [{"type": "text", "text": f"wrote {dest}"}],
        "metadata": {"mode": "direct", "path": dest, **hashes},
    }


def write_hashes(dest: str, content: str) -> dict[str, str]:
    """Hash the current file (when readable) and the content replacing it."""
    hashes = {"after_hash": content_hash(content)}
    before_hash = file_content_hash(dest)
    if before_hash is not None:
        hashes["before_hash"] = before_hash
    return hashes
