"""Zeta v1 runtime services used by Sigil step runners."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, TextIO

from ..state import append_jsonl, read_jsonl
from . import tools as tool_registry
from .prompt import system_prompt

TRANSCRIPT = "zeta-transcript.jsonl"
DEFAULT_TAIL_LIMIT = 50
TOOL_SPECS = tool_registry.TOOL_SPECS
PROJECT_CONTEXT_FILES = ("AGENTS.md", "AGENTS.MD", "CLAUDE.md", "CLAUDE.MD")


def tool_metadata(name: str) -> dict[str, Any]:
    return tool_registry.tool_metadata(name)


def allowed_tool_names(allowed_tools: Iterable[str] | None = None) -> list[str]:
    return tool_registry.allowed_tool_names(allowed_tools)


def tools_list(allowed_tools: Iterable[str] | None = None) -> dict[str, Any]:
    return tool_registry.tools_list(allowed_tools)


def model_tool_descriptors(
    allowed_tools: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    return tool_registry.model_tool_descriptors(allowed_tools)


def analyze_tool(name: str, params: dict[str, Any]) -> dict[str, Any]:
    return tool_registry.analyze_tool(name, params)


def run_tool(name: str, params: dict[str, Any]) -> dict[str, Any]:
    return tool_registry.run_tool(name, params)


def append_transcript(event: dict[str, Any]) -> dict[str, Any]:
    return append_jsonl(TRANSCRIPT, event)


def transcript_tail(limit: int = DEFAULT_TAIL_LIMIT) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    return read_jsonl(TRANSCRIPT)[-limit:]


def load_project_context(cwd: str | Path | None = None) -> str:
    """Load project instruction files from parent directories, global to local."""
    current = Path(cwd or os.getcwd()).resolve()
    directories = [*reversed(current.parents), current]
    sections: list[str] = []
    seen: set[Path] = set()
    for directory in directories:
        for filename in PROJECT_CONTEXT_FILES:
            path = directory / filename
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen or not path.is_file():
                continue
            seen.add(resolved)
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if text.strip():
                sections.append(f"Project context from {path}:\n{text.strip()}")
    return "\n\n".join(sections)


def zeta_system_prompt(
    route_prompt: str | None = None,
    *,
    allowed_tools: Iterable[str] | None = None,
) -> str:
    return system_prompt(route_prompt, allowed_tools=allowed_tools)


def zeta_context_message(
    objective: str,
    *,
    context: str = "",
) -> str:
    sections = [
        f"Objective:\n{objective}",
        f"cwd:\n{os.getcwd()}",
    ]
    if context.strip():
        sections.append(context.strip())
    return "\n\n".join(sections)


def zeta_chat_messages(
    objective: str,
    transcript: list[dict[str, Any]],
    *,
    system: str | None = None,
    allowed_tools: Iterable[str] | None = None,
    context: str = "",
) -> list[dict[str, Any]]:
    messages = [
        {
            "role": "system",
            "content": zeta_system_prompt(system, allowed_tools=allowed_tools),
        },
        {"role": "user", "content": zeta_context_message(objective, context=context)},
    ]
    messages.extend(transcript_chat_messages(transcript[-20:]))
    return messages


def transcript_chat_messages(
    transcript: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    tool_call_ids: set[str] = set()
    for index, event in enumerate(transcript):
        message = role_chat_message(event)
        if message is not None:
            messages.append(message)
            continue
        event_type = str(event.get("type") or "")
        message = event_chat_message(event_type, event)
        if message is not None:
            messages.append(message)
            record_tool_call_ids(message, tool_call_ids)
            continue
        if event_type == "tool_call":
            tool_call_id = str(event.get("id") or event.get("tool_call_id") or "")
            if tool_call_id and tool_call_id in tool_call_ids:
                continue
            message = tool_call_message(event, fallback_id=f"call-{index}")
            messages.append(message)
            record_tool_call_ids(message, tool_call_ids)
            continue
        if event_type == "tool_result":
            messages.append(tool_result_message(event, tool_call_ids))
    return messages


def role_chat_message(event: dict[str, Any]) -> dict[str, Any] | None:
    role = str(event.get("role") or "")
    if role not in {"user", "assistant"}:
        return None
    content = str(event.get("content") or "")
    if not content:
        return None
    return {"role": role, "content": content}


def event_chat_message(
    event_type: str,
    event: dict[str, Any],
) -> dict[str, Any] | None:
    role_by_type = {
        "user_message": "user",
        "assistant_message": "assistant",
    }
    role = role_by_type.get(event_type)
    if role is None:
        return None
    content = str(event.get("content") or "")
    tool_calls = event.get("tool_calls")
    if isinstance(tool_calls, list) and role == "assistant":
        return {
            "role": "assistant",
            "content": content or None,
            "tool_calls": tool_calls,
        }
    if not content:
        return None
    return {"role": role, "content": content}


def record_tool_call_ids(
    message: dict[str, Any],
    tool_call_ids: set[str],
) -> None:
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return
    for call in tool_calls:
        if isinstance(call, dict):
            tool_call_ids.add(str(call.get("id") or ""))


def tool_call_message(
    event: dict[str, Any],
    *,
    fallback_id: str,
) -> dict[str, Any]:
    tool_call_id = str(event.get("id") or event.get("tool_call_id") or fallback_id)
    tool_name = str(event.get("name") or "")
    tool_input = event.get("input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(
                        tool_input,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            }
        ],
    }


def tool_result_message(
    event: dict[str, Any],
    tool_call_ids: set[str],
) -> dict[str, Any]:
    tool_call_id = str(event.get("tool_call_id") or "")
    if tool_call_id and tool_call_id in tool_call_ids:
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(
                event.get("result") or {},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
    return {
        "role": "user",
        "content": "Tool result JSON:\n"
        + json.dumps(event, ensure_ascii=False, separators=(",", ":")),
    }


def read_json_stdin(stdin: TextIO) -> dict[str, Any]:
    raw = stdin.read()
    if not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data
