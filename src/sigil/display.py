"""Small terminal rendering helpers for Sigil routes."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from typing import Any, Iterable, TextIO, cast

from .protocol import (
    SHELL_HANDOFF_OUTCOME_CANCELLED,
    SHELL_HANDOFF_OUTCOME_EXECUTED,
    SHELL_HANDOFF_OUTCOME_NO_PENDING,
)
from .tty import MUTED, RESET

DEFAULT_GLOW_STYLE = "notty"
DEFAULT_GLOW_WIDTH = "88"
TRACE_LABEL_WIDTH = 5


def render_tool_start(name: str, params: dict[str, Any], *, output: TextIO) -> None:
    """Print a visible tool-start line using the same shape as the stream renderer."""
    detail = summarize(name, params)
    status = f"❯ {name:<{TRACE_LABEL_WIDTH}}  {detail}" if detail else f"❯ {name}"
    print(muted(status, enabled=should_color(output)), file=output, flush=True)


def render_zeta_status(
    glyph: str,
    tools: Iterable[object],
    suffix: str,
    *,
    output: TextIO,
    color_enabled: bool | None = None,
) -> None:
    """Print a compact Zeta route status line."""
    if color_enabled is None:
        color_enabled = should_color(output)
    print(
        muted(render_zeta_status_line(glyph, tools, suffix), enabled=color_enabled),
        file=output,
    )


def render_zeta_status_line(
    glyph: str,
    tools: Iterable[object],
    suffix: str,
) -> str:
    """Return the compact status line shared by Zeta routes."""
    return f"❯ zeta {glyph:<5} · {render_tool_label(tools)} · {suffix}"


def render_tool_label(tools: Iterable[object]) -> str:
    """Return a compact plus-joined tool label."""
    label = "+".join(str(tool) for tool in tools if str(tool))
    return label or "no tools"


def render_act_objective_line(act: dict[str, Any]) -> str:
    """Return a compact act overview line."""
    return f"objective: {act.get('objective')}"


def render_act_tools_line(tools: str) -> str:
    """Return the tools line shown before a pending Zeta act step."""
    return f"❯ {'tools':<{TRACE_LABEL_WIDTH}}  {tools}"


def render_handoff_lines(handoff: dict[str, Any]) -> list[str]:
    """Return user-facing lines for a staged tool handoff."""
    reason = str(handoff.get("reason") or "")
    command = str(handoff.get("command") or "")
    artifact = str(handoff.get("artifact") or "")
    lines = []
    if reason:
        lines.append(reason)
    if artifact:
        lines.append(f"artifact: {artifact}")
    if command:
        lines.append(command)
    return lines


def renderer_command() -> list[str]:
    """Return the Markdown renderer command for interactive answers."""
    if not shutil.which("glow"):
        return ["cat"]
    style = os.environ.get("ZETA_GLOW_STYLE") or DEFAULT_GLOW_STYLE
    width = os.environ.get("ZETA_GLOW_WIDTH") or DEFAULT_GLOW_WIDTH
    return ["glow", "--style", style, "--width", width, "-"]


def render_answer(answer: str, stdout: TextIO) -> None:
    """Render the finished answer once, through Markdown rendering on a tty."""
    if not answer:
        return
    cmd = renderer_command()
    if cmd[0] != "cat" and is_interactive(stdout):
        try:
            stdout.write("\n")
            stdout.flush()
            subprocess.run(cmd, input=answer, text=True, stdout=stdout, check=False)
            return
        except OSError:
            pass
    stdout.write(f"\n{answer}\n")
    stdout.flush()


def is_interactive(stream: TextIO) -> bool:
    """Return whether a stream is attached to an interactive terminal."""
    return bool(getattr(stream, "isatty", lambda: False)())


def should_color(stream: TextIO) -> bool:
    """Return whether terminal color should be emitted to a stream."""
    return is_interactive(stream) and "NO_COLOR" not in os.environ


def open_terminal_output() -> TextIO | None:
    """Open the controlling terminal for live-only output when available."""
    try:
        return open("/dev/tty", "w", encoding="utf-8", errors="replace")
    except OSError:
        return None


def muted(text: str, *, enabled: bool) -> str:
    """Apply muted terminal styling when color is enabled."""
    if not enabled:
        return text
    return f"{MUTED}{text}{RESET}"


def clear_status(stderr: TextIO) -> None:
    """Erase a transient spinner/status line before durable output."""
    stderr.write("\r\033[K")
    stderr.flush()


def summarize(tool: str, args: object) -> str:
    """Extract a short human-readable label for a tool call."""
    if not isinstance(args, dict):
        return ""
    tool_args = cast(dict[str, object], args)
    fields_by_tool = {
        "read": ("path", "file_path"),
        "edit": ("path", "file_path"),
        "write": ("path", "file_path"),
        "bash": ("command", "cmd"),
        "grep": ("pattern", "query", "path", "glob"),
        "find": ("pattern", "query", "path", "glob"),
        "ls": ("pattern", "query", "path", "glob"),
    }
    for field in fields_by_tool.get(tool, ()):
        value = tool_args.get(field)
        if value:
            return str(value)
    return " ".join(
        f"{key}={value}"
        for key, value in tool_args.items()
        if isinstance(value, (str, int, float, bool))
    )


def compact_tool_label(tool: object) -> str:
    """Return the short label used in compact traces."""
    if tool == "bash":
        return "check"
    if tool == "grep":
        return "search"
    if tool == "ls":
        return "list"
    return str(tool or "tool")


def compact_detail(detail: str, *, limit: int = 120) -> str:
    """Shorten paths and commands for compact terminal display."""
    text = " ".join(detail.split())
    if not text:
        return ""
    try:
        path = os.path.relpath(text, os.getcwd())
    except ValueError:
        path = text
    if not path.startswith(".."):
        text = path
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def compact_answer_summary(answer: str, *, limit: int = 180) -> str:
    """Return a one-line completion summary from a final answer."""
    lines = []
    in_fence = False
    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue
        line = line.strip("*`- ")
        if line.lower().startswith("verification command"):
            break
        lines.append(line)
    start = compact_summary_start(lines)
    selected = lines[-2:] if start is None else lines[start : start + 3]
    text = " ".join(selected) or "completed"
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def compact_summary_start(lines: list[str]) -> int | None:
    """Return the preferred start line for a compact answer summary."""
    for index in range(len(lines) - 1, -1, -1):
        lower = lines[index].lower()
        if "all tests pass" in lower or "what changed" in lower:
            return index
    for index in range(len(lines) - 1, -1, -1):
        lower = lines[index].lower()
        if lower.startswith(("updated", "changed", "done")):
            return index
    return None


def render_stream_tool_start(
    output: TextIO,
    tool: str,
    detail: str,
    *,
    compact: bool,
    color_enabled: bool,
) -> None:
    """Print a stream tool-start status line."""
    if compact:
        label = compact_tool_label(tool)
        short_detail = compact_detail(detail)
        status = f"  {label:<6} {short_detail}" if short_detail else f"  {label}"
        print(status, file=output, flush=True)
        return
    status = f"❯ {tool:<{TRACE_LABEL_WIDTH}}  {detail}" if detail else f"❯ {tool}"
    print(muted(status, enabled=color_enabled), file=output, flush=True)


class Spinner:
    """Transient `thinking` status line driven by a background thread."""

    def __init__(self, stderr: TextIO, *, enabled: bool, color: bool) -> None:
        self._stderr = stderr
        self._color = color
        self._running = enabled
        self._paused = False
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        """Return whether the spinner is still active."""
        return self._running

    def start(self) -> None:
        """Start the background thread when the spinner is enabled."""
        if not self._running:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        """Pause animation and clear the current status line."""
        with self._lock:
            self._paused = True
        clear_status(self._stderr)

    def resume(self) -> None:
        """Resume animation if the spinner is still running."""
        with self._lock:
            if self._running:
                self._paused = False

    def stop(self) -> None:
        """Stop the background thread and clear the status line."""
        if self._thread is None:
            return
        with self._lock:
            self._running = False
            self._paused = False
        self._thread.join()

    def _run(self) -> None:
        frames = ["thinking", "thinking.", "thinking..", "thinking..."]
        index = 0
        while True:
            with self._lock:
                if not self._running:
                    clear_status(self._stderr)
                    return
                paused = self._paused
            if not paused:
                status = muted(f"❯ {frames[index % len(frames)]}", enabled=self._color)
                self._stderr.write(f"\r\033[K{status}")
                self._stderr.flush()
                index += 1
            time.sleep(0.35)


def tool_result_summary(name: str, result: dict[str, Any]) -> list[str]:
    """Return compact user-facing lines for a Zeta tool result."""
    handoff = result.get("handoff")
    if isinstance(handoff, dict):
        return handoff_summary(name, handoff)

    metadata = result.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    text = text_content(result)
    if name == "read":
        return [f"{count_lines(text)} lines · {len(text.encode())} bytes"]
    if name == "ls":
        entries = metadata.get("entries")
        if isinstance(entries, int):
            return [f"{entries} entries"]
        return [f"{count_lines(text)} entries"]
    if name == "grep":
        matches = [line for line in text.splitlines() if line]
        files = {line.split(":", 1)[0] for line in matches if ":" in line}
        if files:
            return [f"{len(matches)} matches · {len(files)} files"]
        return [f"{len(matches)} matches"]
    if result.get("ok") is False:
        return [str(result.get("message") or result.get("error") or "failed")]
    if result.get("ok") is True:
        return ["ok"]
    return []


def shell_result_summary(event: dict[str, Any]) -> list[str]:
    """Return compact user-facing lines for a shell handoff result event."""
    result = event.get("result")
    if not isinstance(result, dict):
        return []
    outcome = str(result.get("outcome") or "")
    if outcome == SHELL_HANDOFF_OUTCOME_EXECUTED:
        command = result.get("executed_command") or result.get("command") or ""
        status = result.get("status")
        turns = result.get("shell_turns")
        turn_count = len(turns) if isinstance(turns, list) else 0
        suffix = f" · {turn_count} shell turn" + ("" if turn_count == 1 else "s")
        return [
            "❯ shell  captured",
            f"  {truncate(command)}",
            f"  exit {status}{suffix}",
        ]
    if outcome == SHELL_HANDOFF_OUTCOME_CANCELLED:
        expected = result.get("expected_command") or ""
        actual = result.get("actual_command") or ""
        lines = [
            "❯ shell  changed" if actual else "❯ shell  cancelled",
            f"  expected: {truncate(expected)}",
        ]
        if actual:
            lines.append(f"  ran:      {truncate(actual)}")
        return lines
    if outcome == SHELL_HANDOFF_OUTCOME_NO_PENDING:
        return ["❯ shell  no handoff"]
    return []


def handoff_summary(name: str, handoff: dict[str, Any]) -> list[str]:
    """Return compact lines for a tool result that stages shell work."""
    artifact = str(handoff.get("artifact") or "")
    if name == "bash":
        return ["staged in prompt"]
    if name == "edit":
        return [f"staged patch · {artifact}" if artifact else "staged patch"]
    if name == "write":
        return [f"staged write · {artifact}" if artifact else "staged write"]
    if artifact:
        return [f"staged in prompt · {artifact}"]
    return ["staged in prompt"]


def text_content(value: dict[str, Any]) -> str:
    """Return joined text content from a tool result."""
    parts = value.get("content")
    if not isinstance(parts, list):
        return ""
    return "\n".join(
        str(part.get("text") or "")
        for part in parts
        if isinstance(part, dict) and part.get("type") == "text"
    )


def count_lines(text: str) -> int:
    """Return the display line count for a string."""
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def truncate(value: object, limit: int = 96) -> str:
    """Return a single display line bounded to a fixed width."""
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
