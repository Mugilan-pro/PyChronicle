"""Frame-local state maintained by the execution tracer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FrameState:
    frame_id: int
    previous_locals: dict[str, str] = field(default_factory=dict)
    last_line: int | None = None