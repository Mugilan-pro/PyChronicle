"""Small data-access facade for consumers of stored trace histories."""

from __future__ import annotations

from typing import Any

from pychronicle.storage.database import SQLiteStore
from pychronicle.storage.models import TraceEvent


class TraceRepository:
    """Expose ordered events, run metadata, and reconstructed state."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def list_events(self, run_id: int | None = None) -> list[TraceEvent]:
        return self.store.events(run_id)

    def state_at(self, event_id: int, frame_id: int | None = None) -> dict[str, Any]:
        return self.store.state_at(event_id, frame_id)

    def get_run(self, run_id: int) -> dict[str, Any]:
        return self.store.run_info(run_id)