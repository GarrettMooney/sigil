"""Core runtime for Sigil."""

from __future__ import annotations


def zeta_context_for_sigil():
    configure_zeta_for_sigil()

    from zeta.context import ZetaContext
    from zeta.events import EVENT_STORE_NAME, SqliteEventStore
    from zeta.tools.registry import registry
    from zeta.trace import SqliteStore

    from .session import session_id
    from .state import session_dir, state_dir, trace_store_path

    active_session = session_id()
    return ZetaContext(
        session_id=active_session,
        event_sink=SqliteEventStore(state_dir() / EVENT_STORE_NAME),
        trace_store=SqliteStore(trace_store_path(active_session)),
        tool_registry=registry,
        state_dir=state_dir(),
        session_dir=session_dir(active_session),
    )


def configure_zeta_for_sigil(*, responses: bool = False) -> None:
    del responses
    from zeta.timeline import set_session_id_factory

    from .session import session_id as current_session_id

    set_session_id_factory(current_session_id)
