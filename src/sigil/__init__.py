"""Core runtime for Sigil."""

from __future__ import annotations


def configure_zeta_for_sigil(*, responses: bool = False) -> None:
    from zeta.events import publish_event, set_event_store_path_factory
    from zeta.models import set_profile_session_dir_factory
    from zeta.timeline import (
        set_durable_event_publisher,
        set_session_id_factory,
    )
    from zeta.trace import set_trace_path_factories

    from .session import session_id
    from .state import session_dir, state_dir

    set_durable_event_publisher(publish_event)
    set_event_store_path_factory(lambda: state_dir() / "events.sqlite3")
    set_session_id_factory(session_id)
    set_profile_session_dir_factory(session_dir)
    set_trace_path_factories(
        state_dir_factory=state_dir,
        session_dir_factory=session_dir,
    )
    if responses:
        from zeta.models import set_responses_session_id_factory

        set_responses_session_id_factory(session_id)
