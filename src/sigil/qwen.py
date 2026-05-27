"""Backward-compatible names for the OpenAI-compatible model client."""

from __future__ import annotations

from .openai_compat import (
    DEFAULT_MODEL_NAME as DEFAULT_MODEL,
    DEFAULT_MODEL_URL as DEFAULT_URL,
    chat_json,
    chat_text,
    ensure_server,
    model_name as qwen_model,
    model_path as qwen_model_path,
    model_url as qwen_url,
)

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_URL",
    "chat_json",
    "chat_text",
    "ensure_server",
    "qwen_model",
    "qwen_model_path",
    "qwen_url",
]
