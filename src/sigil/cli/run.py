"""Explicit command execution with bounded stdout/stderr capture."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
from typing import BinaryIO, Protocol

import click

from ._base import cli
from ..session import record_turn

DEFAULT_CAPTURE_BYTES = 6000
READ_SIZE = 65536


class TextStream(Protocol):
    def write(self, text: str) -> object: ...
    def flush(self) -> object: ...


class TailBuffer:
    """Keep the last N bytes written by one command stream."""

    def __init__(self, limit: int) -> None:
        self.limit = max(0, limit)
        self.data = bytearray()

    def append(self, chunk: bytes) -> None:
        if self.limit == 0 or not chunk:
            return
        self.data.extend(chunk)
        overflow = len(self.data) - self.limit
        if overflow > 0:
            del self.data[:overflow]

    def text(self) -> str:
        return self.data.decode("utf-8", errors="replace")


@cli.command(
    "run",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.pass_context
@click.argument("argv", nargs=-1, type=click.UNPROCESSED)
def cmd_run(ctx: click.Context, argv: tuple[str, ...]) -> int:
    """Run a command, stream output live, and record clean output snippets."""
    if not argv:
        raise click.UsageError("missing command to run")

    capture_bytes = configured_capture_bytes()
    stdout_tail = TailBuffer(capture_bytes)
    stderr_tail = TailBuffer(capture_bytes)
    command = shlex.join(argv)

    try:
        proc = subprocess.Popen(
            list(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=None,
        )
    except FileNotFoundError as error:
        program = error.filename or argv[0]
        stderr = (
            f"sigil: missing executable: {program}\n"
            "Install it or make sure it is on PATH, then retry.\n"
        )
        click.echo(stderr, err=True, nl=False)
        record_turn(command, 127, os.getcwd(), stderr_snippet=stderr)
        ctx.exit(127)
    except PermissionError as error:
        target = error.filename or argv[0]
        stderr = f"sigil: permission denied: {target}\n"
        click.echo(stderr, err=True, nl=False)
        record_turn(command, 126, os.getcwd(), stderr_snippet=stderr)
        ctx.exit(126)
    assert proc.stdout is not None
    assert proc.stderr is not None

    stdout_thread = threading.Thread(
        target=mirror_stream,
        args=(proc.stdout, sys.stdout, stdout_tail),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=mirror_stream,
        args=(proc.stderr, sys.stderr, stderr_tail),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    status = proc.wait()
    stdout_thread.join()
    stderr_thread.join()

    record_turn(
        command,
        status,
        os.getcwd(),
        stdout_snippet=stdout_tail.text(),
        stderr_snippet=stderr_tail.text(),
    )
    ctx.exit(status)


def configured_capture_bytes() -> int:
    raw = os.environ.get("SIGIL_RUN_CAPTURE_BYTES", str(DEFAULT_CAPTURE_BYTES))
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_CAPTURE_BYTES


def mirror_stream(source: BinaryIO, target: TextStream, tail: TailBuffer) -> None:
    while True:
        chunk = source.read(READ_SIZE)
        if not chunk:
            break
        tail.append(chunk)
        write_bytes(target, chunk)


def write_bytes(target: TextStream, chunk: bytes) -> None:
    buffer = getattr(target, "buffer", None)
    if buffer is not None:
        buffer.write(chunk)
        buffer.flush()
        return
    target.write(chunk.decode("utf-8", errors="replace"))
    target.flush()
