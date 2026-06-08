"""OpenAI-compatible chat completions transport for Zeta."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Protocol
from urllib.parse import urlparse

DEFAULT_MODEL_URL = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_MODEL_NAME = "local-model"
DEFAULT_MODEL_IDLE_TIMEOUT_SECONDS = None


class ChatCompletionStreamSink(Protocol):
    """Receive visible chat completion stream events."""

    def content_delta(self, text: str) -> None:
        """Handle one visible assistant text delta."""
        ...


def model_url(selected_url: str | None = None) -> str:
    """Return the OpenAI-compatible chat completions endpoint."""
    if selected_url:
        return selected_url
    return model_url_from_env(os.environ)


def model_name(selected_model: str | None = None) -> str:
    """Return the model name sent to the configured endpoint."""
    if selected_model:
        return selected_model
    return os.environ.get("ZETA_MODEL_NAME") or DEFAULT_MODEL_NAME


def model_url_from_env(env: Mapping[str, str]) -> str:
    """Return the configured model URL from explicit environment values."""
    return env.get("ZETA_MODEL_URL") or DEFAULT_MODEL_URL


def model_idle_timeout_from_env(env: Mapping[str, str]) -> float | None:
    """Return the configured client-side model stream idle timeout."""
    value = env.get("ZETA_MODEL_IDLE_TIMEOUT_SECONDS")
    if value is None or value.strip() == "":
        return DEFAULT_MODEL_IDLE_TIMEOUT_SECONDS
    try:
        seconds = float(value)
    except ValueError:
        return DEFAULT_MODEL_IDLE_TIMEOUT_SECONDS
    if seconds <= 0:
        return None
    return seconds


def model_idle_timeout() -> float | None:
    """Return the configured client-side model stream idle timeout."""
    return model_idle_timeout_from_env(os.environ)


def model_endpoint_valid(url: str) -> bool:
    """Return whether a model endpoint URL includes a host."""
    return urlparse(url).hostname is not None


def endpoint_reachable(url: str) -> bool:
    """Return whether the configured endpoint accepts TCP connections."""
    parsed = urlparse(url)
    host = parsed.hostname
    if host is None:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def model_endpoint_open(selected_url: str | None = None) -> bool:
    """Return whether the configured OpenAI-compatible server is listening."""
    return endpoint_reachable(model_url(selected_url))


def request_chat_completion(
    body: dict[str, Any],
    *,
    selected_url: str | None = None,
    stream_sink: ChatCompletionStreamSink | None = None,
) -> dict[str, Any]:
    """POST one streaming chat completions request and return the final response."""
    stream_body = {**body, "stream": True}
    data = json.dumps(stream_body).encode("utf-8")
    req = urllib.request.Request(
        model_url(selected_url),
        data=data,
        headers={
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=model_idle_timeout()) as resp:
            payload = read_streamed_chat_completion(resp, stream_sink=stream_sink)
    except (
        OSError,
        TimeoutError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimeError(f"model request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("model request failed: response was not a JSON object")
    return payload


def read_streamed_chat_completion(
    lines: Iterable[bytes],
    *,
    stream_sink: ChatCompletionStreamSink | None = None,
) -> dict[str, Any]:
    """Read OpenAI-style chat completion SSE frames into one final response."""
    accumulator = ChatStreamAccumulator(stream_sink=stream_sink)
    done = False
    for data in iter_sse_data(lines):
        if data == "[DONE]":
            done = True
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"model stream failed: invalid JSON event: {exc}"
            ) from exc
        if not isinstance(chunk, dict):
            raise RuntimeError("model stream failed: event was not a JSON object")
        error = chunk.get("error")
        if error is not None:
            raise RuntimeError(f"model request failed: {format_stream_error(error)}")
        accumulator.add_chunk(chunk)
    if not done:
        raise RuntimeError("model stream failed: stream ended before [DONE]")
    return accumulator.response()


def iter_sse_data(lines: Iterable[bytes]) -> Iterator[str]:
    """Yield joined ``data:`` payloads from a Server-Sent Events byte stream."""
    data_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if line == "":
            if data_lines:
                yield "\n".join(data_lines)
                data_lines = []
            continue
        if line.startswith(":"):
            continue
        if not line.startswith("data:"):
            continue
        data = line[5:]
        if data.startswith(" "):
            data = data[1:]
        data_lines.append(data)
    if data_lines:
        yield "\n".join(data_lines)


def format_stream_error(error: Any) -> str:
    """Return a compact model stream error message."""
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
    if isinstance(error, str):
        return error
    return json.dumps(error, sort_keys=True)


class ChatStreamAccumulator:
    """Accumulate OpenAI-style chat completion chunks into a final message."""

    def __init__(
        self,
        *,
        stream_sink: ChatCompletionStreamSink | None = None,
    ) -> None:
        self.metadata: dict[str, Any] = {}
        self.role: str | None = None
        self.content: list[str] = []
        self.reasoning_content: list[str] = []
        self.tool_calls: dict[int, dict[str, Any]] = {}
        self.finish_reason: Any = None
        self.seen_choice = False
        self.stream_sink = stream_sink

    def add_chunk(self, chunk: dict[str, Any]) -> None:
        for key in ("id", "object", "created", "model", "system_fingerprint"):
            value = chunk.get(key)
            if value is not None and key not in self.metadata:
                self.metadata[key] = value
        choices = chunk.get("choices")
        if not isinstance(choices, list):
            raise RuntimeError("model stream failed: event choices were invalid")
        for choice in choices:
            if not isinstance(choice, dict):
                raise RuntimeError("model stream failed: event choice was invalid")
            if choice.get("index", 0) != 0:
                continue
            self.seen_choice = True
            finish_reason = choice.get("finish_reason")
            if finish_reason is not None:
                self.finish_reason = finish_reason
            delta = choice.get("delta", {})
            if not isinstance(delta, dict):
                raise RuntimeError("model stream failed: event delta was invalid")
            self.add_delta(delta)

    def add_delta(self, delta: dict[str, Any]) -> None:
        role = delta.get("role")
        if isinstance(role, str):
            self.role = role
        content = delta.get("content")
        if isinstance(content, str):
            self.content.append(content)
            if self.stream_sink is not None:
                self.stream_sink.content_delta(content)
        reasoning_content = delta.get("reasoning_content")
        if isinstance(reasoning_content, str):
            self.reasoning_content.append(reasoning_content)
        tool_calls = delta.get("tool_calls")
        if tool_calls is not None:
            self.add_tool_calls(tool_calls)

    def add_tool_calls(self, tool_calls: Any) -> None:
        if not isinstance(tool_calls, list):
            raise RuntimeError("model stream failed: tool call delta was invalid")
        for raw_call in tool_calls:
            if not isinstance(raw_call, dict):
                raise RuntimeError("model stream failed: tool call was invalid")
            index = raw_call.get("index")
            if not isinstance(index, int):
                raise RuntimeError("model stream failed: tool call index was invalid")
            call = self.tool_calls.setdefault(
                index,
                {"function": {"name": "", "arguments": ""}},
            )
            call_id = raw_call.get("id")
            if isinstance(call_id, str):
                call["id"] = call_id
            call_type = raw_call.get("type")
            if isinstance(call_type, str):
                call["type"] = call_type
            function = raw_call.get("function")
            if function is not None:
                self.add_tool_function_delta(call, function)

    def add_tool_function_delta(
        self,
        call: dict[str, Any],
        function: Any,
    ) -> None:
        if not isinstance(function, dict):
            raise RuntimeError("model stream failed: tool function was invalid")
        call_function = call.setdefault("function", {"name": "", "arguments": ""})
        if not isinstance(call_function, dict):
            raise RuntimeError("model stream failed: tool function state was invalid")
        name = function.get("name")
        if isinstance(name, str):
            call_function["name"] = str(call_function.get("name") or "") + name
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            call_function["arguments"] = (
                str(call_function.get("arguments") or "") + arguments
            )

    def response(self) -> dict[str, Any]:
        if not self.seen_choice:
            raise RuntimeError("model stream failed: no completion choices received")
        message: dict[str, Any] = {
            "role": self.role or "assistant",
            "content": "".join(self.content),
        }
        if self.reasoning_content:
            message["reasoning_content"] = "".join(self.reasoning_content)
        if self.tool_calls:
            message["tool_calls"] = [
                self.final_tool_call(index) for index in sorted(self.tool_calls)
            ]
        return {
            **self.metadata,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": self.finish_reason,
                }
            ],
        }

    def final_tool_call(self, index: int) -> dict[str, Any]:
        call = self.tool_calls[index]
        function = call.get("function")
        if not isinstance(function, dict):
            function = {"name": "", "arguments": ""}
        return {
            "id": str(call.get("id") or f"call-{index}"),
            "type": str(call.get("type") or "function"),
            "function": {
                "name": str(function.get("name") or ""),
                "arguments": str(function.get("arguments") or ""),
            },
        }


def chat_completion_messages(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] = "auto",
    max_tokens: int = 1200,
    selected_model: str | None = None,
    selected_url: str | None = None,
    stream_sink: ChatCompletionStreamSink | None = None,
) -> dict[str, Any]:
    """Request one native OpenAI-compatible chat completion message."""
    body: dict[str, Any] = {
        "model": model_name(selected_model),
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice
    request_kwargs: dict[str, Any] = {}
    if selected_url is not None:
        request_kwargs["selected_url"] = selected_url
    if stream_sink is not None:
        request_kwargs["stream_sink"] = stream_sink
    payload = request_chat_completion(body, **request_kwargs)
    message = payload["choices"][0]["message"]
    if not isinstance(message, dict):
        raise RuntimeError("model request failed: assistant message was invalid")
    return message


def chat_text(
    system: str,
    user: str,
    *,
    max_tokens: int = 1200,
    selected_model: str | None = None,
    selected_url: str | None = None,
    stream_sink: ChatCompletionStreamSink | None = None,
) -> str:
    """Request plain text from the configured model endpoint."""
    body = {
        "model": model_name(selected_model),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request_kwargs: dict[str, Any] = {}
    if selected_url is not None:
        request_kwargs["selected_url"] = selected_url
    if stream_sink is not None:
        request_kwargs["stream_sink"] = stream_sink
    payload = request_chat_completion(body, **request_kwargs)
    return str(payload["choices"][0]["message"]["content"])
