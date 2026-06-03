"""Render Zeta JSON events while preserving structured state.

Zeta emits machine-readable events. This filter turns tool calls into live grey
status lines, streams answer text to stdout for `glow`, and writes only the
right pieces into session state: assistant turns to the answer transcript and
tool calls to the tool trace.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import TextIO, cast

from .display import (
    Spinner,
    compact_answer_summary,
    is_interactive,
    open_terminal_output,
    render_answer,
    render_stream_tool_start,
    should_color,
    summarize,
)
from .state import ANSWER_TRANSCRIPT, append_event, append_jsonl


def run_zeta_stream(
    zeta_cmd: list[str],
    *,
    zeta_env: dict[str, str] | None = None,
    question: str = "",
    prompt: str = "",
    follow_up: bool = False,
    capture_answer: bool = True,
    capture_trace: bool = True,
    json_output: bool = False,
    compact: bool = False,
    tool_output_stdout: bool = False,
) -> int:
    """Run Zeta and render its JSON event stream in-process; return Zeta's exit code."""
    zeta_proc = subprocess.Popen(
        zeta_cmd,
        stdout=subprocess.PIPE,
        env=zeta_env,
        pass_fds=inherited_terminal_fds(zeta_env),
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert zeta_proc.stdout is not None
    try:
        stream_events(
            cast(TextIO, zeta_proc.stdout),
            question=question,
            prompt=prompt,
            follow_up=follow_up,
            capture_answer=capture_answer,
            capture_trace=capture_trace,
            json_output=json_output,
            compact=compact,
            tool_output_stdout=tool_output_stdout,
        )
    finally:
        zeta_proc.stdout.close()
    return zeta_proc.wait()


def inherited_terminal_fds(env: dict[str, str] | None = None) -> tuple[int, ...]:
    """Return terminal fds that Zeta extensions need Python to keep open."""
    raw = (env or os.environ).get("ZETA_TTY_FD")
    if not raw:
        return ()
    try:
        fd = int(raw)
    except ValueError:
        return ()
    if fd < 0:
        return ()
    try:
        os.fstat(fd)
    except OSError:
        return ()
    return (fd,)


TOOL_START_EVENT_TYPES = {
    "tool_execution_start",
    "tool_call",
    "toolcall_end",
    "function_call",
}
TOOL_END_EVENT_TYPES = {
    "tool_execution_end",
    "tool_result",
    "tool_call_result",
    "function_call_result",
}


def event_payload(event: dict[str, object]) -> dict[str, object]:
    """Return the event object that carries Zeta payload fields."""
    update = event.get("assistantMessageEvent")
    if event.get("type") == "message_update" and isinstance(update, dict):
        return cast(dict[str, object], update)
    return event


def event_kind(event: dict[str, object]) -> str:
    """Return the concrete Zeta event kind, including nested message updates."""
    payload = event_payload(event)
    return str(payload.get("type") or "")


def tool_name(payload: dict[str, object]) -> str:
    """Extract a tool/function name from known Zeta event shapes."""
    for key in ("toolName", "functionName", "name", "tool"):
        value = payload.get(key)
        if value:
            return str(value)
    tool_call = payload.get("toolCall")
    if isinstance(tool_call, dict):
        tool_call_payload = cast(dict[str, object], tool_call)
        name = tool_call_payload.get("name")
        if name:
            return str(name)
    indexed_tool_call = tool_call_from_partial(payload)
    if indexed_tool_call is not None:
        name = indexed_tool_call.get("name")
        if name:
            return str(name)
    function = payload.get("function")
    if isinstance(function, dict):
        function_payload = cast(dict[str, object], function)
        name = function_payload.get("name")
        if name:
            return str(name)
    return ""


def tool_args(payload: dict[str, object]) -> object:
    """Extract tool/function arguments from known Zeta event shapes."""
    for key in ("args", "input", "arguments"):
        if key in payload:
            return decoded_args(payload.get(key))
    tool_call = payload.get("toolCall")
    if isinstance(tool_call, dict):
        tool_call_payload = cast(dict[str, object], tool_call)
        return decoded_args(tool_call_payload.get("arguments"))
    indexed_tool_call = tool_call_from_partial(payload)
    if indexed_tool_call is not None:
        return decoded_args(indexed_tool_call.get("arguments"))
    function = payload.get("function")
    if isinstance(function, dict):
        function_payload = cast(dict[str, object], function)
        return decoded_args(function_payload.get("arguments"))
    return None


def tool_call_id(payload: dict[str, object]) -> str:
    """Extract a stable tool-call id from known Zeta event shapes."""
    for key in ("toolCallId", "tool_call_id", "id"):
        value = payload.get(key)
        if value:
            return str(value)
    tool_call = payload.get("toolCall")
    if isinstance(tool_call, dict):
        tool_call_payload = cast(dict[str, object], tool_call)
        value = tool_call_payload.get("id")
        if value:
            return str(value)
    indexed_tool_call = tool_call_from_partial(payload)
    if indexed_tool_call is not None:
        value = indexed_tool_call.get("id")
        if value:
            return str(value)
    return ""


def tool_call_from_partial(payload: dict[str, object]) -> dict[str, object] | None:
    """Return the indexed toolCall block from a partial assistant message."""
    content_index = payload.get("contentIndex")
    if not isinstance(content_index, int):
        return None
    partial = payload.get("partial")
    if not isinstance(partial, dict):
        return None
    partial_payload = cast(dict[str, object], partial)
    content = partial_payload.get("content")
    if (
        not isinstance(content, list)
        or content_index < 0
        or content_index >= len(content)
    ):
        return None
    block = content[content_index]
    if not isinstance(block, dict):
        return None
    block_payload = cast(dict[str, object], block)
    if block_payload.get("type") != "toolCall":
        return None
    return block_payload


def decoded_args(value: object) -> object:
    """Decode JSON argument strings used by function-call events."""
    if not isinstance(value, str):
        return value
    try:
        decoded = json.loads(value)
    except Exception:
        return value
    return decoded


def tool_start_event(event: dict[str, object]) -> tuple[str, object, str] | None:
    """Return normalized tool start data when an event begins a call."""
    payload = event_payload(event)
    if event_kind(event) not in TOOL_START_EVENT_TYPES:
        return None
    name = tool_name(payload)
    if not name:
        return None
    return name, tool_args(payload), tool_call_id(payload)


def tool_end_event(event: dict[str, object]) -> str | None:
    """Return a normalized tool name when an event ends a call."""
    payload = event_payload(event)
    if event_kind(event) not in TOOL_END_EVENT_TYPES:
        return None
    return tool_name(payload)


@dataclass
class _StreamContext:
    """Output destinations and rendering flags for one Zeta stream."""

    stdout: TextIO
    stderr: TextIO
    compact: bool
    json_output: bool
    color_enabled: bool
    tool_output_stdout: bool = False
    tool_output_terminal: TextIO | None = None
    question: str = ""
    prompt: str = ""
    follow_up: bool = False
    capture_answer: bool = False
    capture_trace: bool = False


def _record_tool_trace(ctx: _StreamContext, trace_event: dict[str, object]) -> None:
    """Persist a tool trace event to the trace log and global event log."""
    if ctx.capture_trace:
        append_jsonl("last-tools.jsonl", trace_event)
    append_event(trace_event)


def _handle_tool_start(
    event: dict[str, object],
    ctx: _StreamContext,
    spinner: Spinner,
    tool_events: list[dict[str, object]],
    seen_tool_calls: dict[str, str],
) -> bool:
    """Handle a tool-start event; return True when the event was consumed."""
    tool_start = tool_start_event(event)
    if tool_start is None:
        return False
    tool, args, call_id = tool_start
    detail = summarize(tool, args)
    if call_id:
        previous_detail = seen_tool_calls.get(call_id)
        if previous_detail or not detail:
            return True
        seen_tool_calls[call_id] = detail
    if spinner.running:
        spinner.pause()
    trace_event: dict[str, object] = {
        "type": "tool_start",
        "tool": tool,
        "detail": detail,
        "args": args,
        "tool_call_id": call_id,
    }
    tool_events.append(trace_event)
    _record_tool_trace(ctx, trace_event)
    if not ctx.json_output:
        output = ctx.stderr
        if ctx.tool_output_stdout:
            output = (
                ctx.tool_output_terminal if ctx.tool_output_terminal else ctx.stdout
            )
        render_stream_tool_start(
            output,
            tool,
            detail,
            compact=ctx.compact,
            color_enabled=ctx.color_enabled,
        )
    return True


def _handle_tool_end(
    event: dict[str, object],
    ctx: _StreamContext,
    spinner: Spinner,
    tool_events: list[dict[str, object]],
) -> bool:
    """Handle a tool-end event; return True when the event was consumed."""
    tool_end = tool_end_event(event)
    if tool_end is None:
        return False
    trace_event: dict[str, object] = {"type": "tool_end", "tool": tool_end}
    tool_events.append(trace_event)
    _record_tool_trace(ctx, trace_event)
    if spinner.running:
        spinner.resume()
    return True


def _handle_text_delta(
    event: dict[str, object],
    ctx: _StreamContext,
    spinner: Spinner,
    answer_chunks: list[str],
    started_text: bool,
) -> bool:
    """Stream an assistant text delta; return the updated started_text flag."""
    if event.get("type") != "message_update":
        return started_text
    raw_update = event.get("assistantMessageEvent")
    if not isinstance(raw_update, dict):
        return started_text
    update = cast(dict[str, object], raw_update)
    if update.get("type") != "text_delta":
        return started_text
    delta = str(update.get("delta", ""))
    if not ctx.json_output and not ctx.compact and not started_text:
        spinner.stop()
        started_text = True
    answer_chunks.append(delta)
    return started_text


def _record_answer(ctx: _StreamContext, answer: str) -> str | None:
    """Record the finished answer to the event log and transcript."""
    if not answer:
        return None
    answer_event = append_event(
        {"type": "answer_done", "bytes": len(answer.encode("utf-8"))}
    )
    if ctx.capture_answer:
        append_jsonl(
            ANSWER_TRANSCRIPT,
            {
                "role": "assistant",
                "content": answer,
                "event_id": answer_event["id"],
            },
        )
    return answer_event["id"]


def _write_json_result(
    ctx: _StreamContext,
    answer: str,
    answer_event_id: str | None,
    tool_events: list[dict[str, object]],
    malformed_events: int,
) -> None:
    """Write the machine-readable answer envelope to stdout."""
    ctx.stdout.write(
        json.dumps(
            {
                "ok": True,
                "type": "answer",
                "question": ctx.question,
                "prompt": ctx.prompt,
                "follow_up": ctx.follow_up,
                "answer": answer,
                "answer_event_id": answer_event_id,
                "tools": tool_events,
                "malformed_events": malformed_events,
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    ctx.stdout.flush()


def _finalize(
    ctx: _StreamContext,
    answer_chunks: list[str],
    tool_events: list[dict[str, object]],
    malformed_events: int,
) -> None:
    """Emit the final answer output once the stream is drained."""
    answer = "".join(answer_chunks)
    answer_event_id = _record_answer(ctx, answer)
    if ctx.json_output:
        _write_json_result(ctx, answer, answer_event_id, tool_events, malformed_events)
    elif ctx.compact:
        ctx.stdout.write(f"done: {compact_answer_summary(answer)}\n")
        ctx.stdout.flush()
    else:
        render_answer(answer, ctx.stdout)
        if malformed_events:
            noun = "event" if malformed_events == 1 else "events"
            print(
                f"zeta: ignored {malformed_events} malformed Zeta {noun}",
                file=ctx.stderr,
            )


def stream_events(
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    *,
    question: str = "",
    prompt: str = "",
    follow_up: bool = False,
    capture_answer: bool = False,
    capture_trace: bool = False,
    json_output: bool = False,
    compact: bool = False,
    tool_output_stdout: bool = False,
) -> int:
    """Filter Zeta's event stream into terminal output and session state files."""
    started_text = False
    answer_chunks: list[str] = []
    tool_events: list[dict[str, object]] = []
    seen_tool_calls: dict[str, str] = {}
    malformed_events = 0
    tool_output_terminal = (
        open_terminal_output()
        if tool_output_stdout and not is_interactive(stdout)
        else None
    )
    tool_color_stream = (
        (tool_output_terminal if tool_output_terminal else stdout)
        if tool_output_stdout
        else stderr
    )
    ctx = _StreamContext(
        stdout=stdout,
        stderr=stderr,
        compact=compact,
        json_output=json_output,
        color_enabled=should_color(tool_color_stream),
        tool_output_stdout=tool_output_stdout,
        tool_output_terminal=tool_output_terminal,
        question=question,
        prompt=prompt,
        follow_up=follow_up,
        capture_answer=capture_answer,
        capture_trace=capture_trace,
    )
    spinner_active = not json_output and not compact and is_interactive(stderr)
    spinner = Spinner(stderr, enabled=spinner_active, color=ctx.color_enabled)
    spinner.start()

    try:
        for raw_line in stdin:
            try:
                event = json.loads(raw_line)
            except Exception:
                malformed_events += 1
                continue
            if _handle_tool_start(event, ctx, spinner, tool_events, seen_tool_calls):
                continue
            if _handle_tool_end(event, ctx, spinner, tool_events):
                continue
            started_text = _handle_text_delta(
                event, ctx, spinner, answer_chunks, started_text
            )
    finally:
        spinner.stop()
        _finalize(ctx, answer_chunks, tool_events, malformed_events)
        if tool_output_terminal is not None:
            tool_output_terminal.close()
    return 0
