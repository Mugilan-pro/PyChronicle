"""Convenient indexed navigation through recorded events."""

from __future__ import annotations

from pychronicle.storage.database import SQLiteStore
from pychronicle.storage.models import TraceEvent
from pychronicle.timeline.snapshot import Snapshot


class Timeline:
    def __init__(self, store: SQLiteStore, run_id: int | None = None) -> None:
        self.store = store
        self.events: list[TraceEvent] = store.events(run_id)

    def __len__(self) -> int:
        return len(self.events)

    def at(self, index: int) -> Snapshot:
        if not self.events:
            raise IndexError("The trace contains no events")
        if index < 0 or index >= len(self.events):
            raise IndexError(f"Timeline index out of range: {index}")
        event = self.events[index]
        return Snapshot(event=event, variables=self.store.state_at(event.id, event.frame_id))