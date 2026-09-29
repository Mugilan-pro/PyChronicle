"""An immutable historical view of one execution event."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pychronicle.storage.database import SQLiteStore
from pychronicle.storage.models import TraceEvent


@dataclass(frozen=True)
class Snapshot:
    event: TraceEvent
    variables: dict[str, Any]