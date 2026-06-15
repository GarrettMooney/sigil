"""Core runtime for Sigil."""

from __future__ import annotations


def configure_zeta_for_sigil(*, responses: bool = False) -> None:
    from zeta.models import set_profile_session_dir_factory
    from zeta.timeline import set_session_id_factory
    from zeta.trace import set_trace_path_factories, trace_state_dir

    from .session import session_id as current_session_id
    from .state import session_dir

    def trace_session_dir(session_id: str | None = None):
        return trace_state_dir() / "sessions" / (session_id or current_session_id())

    set_session_id_factory(current_session_id)
    set_profile_session_dir_factory(session_dir)
    set_trace_path_factories(session_dir_factory=trace_session_dir)
    if responses:
        from zeta.models import set_responses_session_id_factory

        set_responses_session_id_factory(current_session_id)
