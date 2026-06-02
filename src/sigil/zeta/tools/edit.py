"""Patch-edit handoff tool implementation."""

from __future__ import annotations

import shlex
from typing import Any

from .base import (
    ToolSpec,
    analysis,
    diagnostic,
    effect,
    error_result,
    handoff,
    missing,
    write_temp,
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["patch"],
    "properties": {
        "patch": {"type": "string"},
        "reason": {"type": "string"},
    },
}

SPEC = ToolSpec(
    "edit",
    "Write a patch artifact and stage git apply.",
    SCHEMA,
    True,
)


def analyze(params: dict[str, Any]) -> dict[str, Any]:
    patch = str(params.get("patch") or "")
    if not patch:
        return missing("patch")
    paths = patch_paths(patch)
    resolved = bool(paths)
    diagnostics = (
        [] if resolved else [diagnostic("patch-paths", "no patch paths found")]
    )
    return analysis(
        resolved=resolved,
        effects=[effect("write", path) for path in paths],
        diagnostics=diagnostics,
    )


def run(params: dict[str, Any]) -> dict[str, Any]:
    patch = str(params.get("patch") or "")
    if not patch:
        return error_result("missing-patch", "missing patch")
    path = write_temp("zeta-edit-", ".patch", patch)
    return handoff(
        f"git apply {shlex.quote(str(path))}",
        str(params.get("reason") or "Apply the staged patch."),
        artifact=str(path),
    )


def patch_paths(patch: str) -> list[str]:
    paths: list[str] = []
    for line in patch.splitlines():
        path = patch_path_from_line(line)
        if path and path not in paths:
            paths.append(path)
    return paths


def patch_path_from_line(line: str) -> str | None:
    if line.startswith("+++ "):
        raw = line[4:].strip().split("\t", 1)[0]
    elif line.startswith("--- "):
        raw = line[4:].strip().split("\t", 1)[0]
    else:
        return None
    if raw == "/dev/null":
        return None
    if raw.startswith("a/") or raw.startswith("b/"):
        return raw[2:]
    return raw
