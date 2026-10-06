"""Typed records shared by tracing and storage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TraceEvent:
    id: int
    run_id: int
    sequence: int
    timestamp: float
    filename: str
    line_number: int
    function_name: str
    frame_id: int
    changes: dict[str, Any]