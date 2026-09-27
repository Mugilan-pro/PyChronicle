"""Execution tracer for PyChronicle.

Uses sys.settrace to record execution events (call, line, return, exception)
and local variable snapshots for a target Python script.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any


@dataclass
class TraceEvent:
    """Represents a single execution event captured by the ExecutionTracer."""

    event: str
    line_number: int
    function: str
    filename: str
    locals: dict[str, Any]
    arg: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the event to a dictionary for SQLite storage."""
        return {
            "event": self.event,
            "line_number": self.line_number,
            "function": self.function,
            "filename": self.filename,
            "locals": self.locals,
            "arg": self.arg,
        }


def _safe_copy(val: Any) -> Any:
    """Deep-copy mutable objects so later modifications do not alter past events."""
    try:
        return copy.deepcopy(val)
    except Exception:
        return repr(val)


def _snapshot_locals(frame_locals: dict[str, Any]) -> dict[str, Any]:
    """Capture a snapshot of local variables, omitting __builtins__."""
    snapshot = {}
    for key, value in frame_locals.items():
        if key == "__builtins__":
            continue
        snapshot[key] = _safe_copy(value)
    return snapshot


class ExecutionTracer:
    """Traces execution of a target Python file using sys.settrace."""

    def __init__(self, target_file: str | Path) -> None:
        self.target_path = Path(target_file).resolve()
        if not self.target_path.is_file():
            raise FileNotFoundError(f"Target file not found: {self.target_path}")

        self.events: list[TraceEvent] = []

    def _trace(self, frame: Any, event: str, arg: Any):
        # Ignore frames from outside the target file (standard library, etc.)
        if Path(frame.f_code.co_filename).resolve() != self.target_path:
            return None

        event_arg = None
        if event == "return":
            event_arg = _safe_copy(arg)
        elif event == "exception":
            exc_type, exc_value, _ = arg
            event_arg = {"type": exc_type.__name__, "message": str(exc_value)}

        self.events.append(
            TraceEvent(
                event=event,
                line_number=frame.f_lineno,
                function=frame.f_code.co_name,
                filename=self.target_path.name,
                locals=_snapshot_locals(frame.f_locals),
                arg=event_arg,
            )
        )
        return self._trace

    def run(self) -> list[TraceEvent]:
        """Execute the target file and return the recorded events."""
        source = self.target_path.read_text(encoding="utf-8")
        code = compile(source, str(self.target_path), "exec")

        execution_namespace = {
            "__name__": "__main__",
            "__file__": str(self.target_path),
            "__doc__": None,
        }

        self.events = []
        sys.settrace(self._trace)
        try:
            exec(code, execution_namespace)
        finally:
            sys.settrace(None)

        return self.events
