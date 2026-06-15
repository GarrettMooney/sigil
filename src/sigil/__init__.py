"""Core runtime for Sigil."""

from __future__ import annotations


def zeta_context_for_sigil():
    from zeta.context import ZetaContext, zeta_state_dir
    from zeta.events import SqliteEventStore, event_store_path
    from zeta.tools.registry import registry
    from zeta.trace import SqliteStore, zeta_sqlite_path

    from .session import session_id
    from .state import session_dir

    active_session = session_id()
    zeta_dir = zeta_state_dir()
    return ZetaContext(
        session_id=active_session,
        event_sink=SqliteEventStore(event_store_path(zeta_dir)),
        trace_store=SqliteStore(zeta_sqlite_path(zeta_dir), session_id=active_session),
        tool_registry=registry,
        state_dir=zeta_dir,
        session_dir=session_dir(active_session),
    )
