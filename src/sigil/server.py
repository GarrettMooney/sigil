"""Lifecycle checks for the local model server used by Sigil and Pi."""

from __future__ import annotations

import sys

from .openai_compat import endpoint_reachable, model_url


def model_endpoint_open() -> bool:
    """Return whether the configured OpenAI-compatible server is listening."""
    return endpoint_reachable(model_url())


def ensure_model_for_pi() -> bool:
    """Check that the local model endpoint is reachable before invoking Pi."""
    if model_endpoint_open():
        return True
    print(
        f"pi: local model endpoint is not reachable at {model_url()}",
        file=sys.stderr,
    )
    print("pi: start the model server or set SIGIL_MODEL_URL", file=sys.stderr)
    return False
