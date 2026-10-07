"""A line-event tracer that writes variable deltas into SQLite."""

from __future__ import annotations

import runpy
import sys
import time
from pathlib import Path
from types import FrameType
from typing import Any, Sequence

from pychronicle.storage.database import SQLiteStore
from pychronicle.tracer.frame import FrameState
from pychronicle.tracer.state import local_changes


class TraceEngine:
    """Capture line history for Python files beneath a target directory."""

    def __init__(self, store: SQLiteStore, target: str | Path, run_id: int) -> None:
        self.store = store
        self.target = Path(target).resolve()
        self.root = self.target.parent
        self.run_id = run_id
        self.sequence = 0
        self._next_frame_id = 1
        self._frames: dict[int, FrameState] = {}

    def _is_traced(self, filename: str) -> bool:
        try:
            Path(filename).resolve().relative_to(self.root)
        except (OSError, ValueError):
            return False
        return True

    def _record(self, frame: FrameType, state: FrameState, line_number: int | None = None) -> None:
        values = dict(frame.f_locals)
        if frame.f_code.co_name != "<module>":
            local_names = set(values)
            values.update(
                {
                    f"global:{name}": frame.f_globals[name]
                    for name in frame.f_code.co_names
                    if name not in local_names and name in frame.f_globals
                }
            )
        changes, removed, state.previous_locals = local_changes(
            state.previous_locals, values
        )
        recorded_line = line_number if line_number is not None else (
            state.last_line if state.last_line is not None else frame.f_lineno
        )
        self.sequence += 1
        self.store.record_event(
            run_id=self.run_id,
            sequence=self.sequence,
            timestamp=time.time(),
            filename=frame.f_code.co_filename,
            line_number=recorded_line,
            function_name=frame.f_code.co_name,
            frame_id=state.frame_id,
            changes=changes,
            deleted=removed,
        )

    def _trace(self, frame: FrameType, event: str, arg: Any) -> Any:
        if not self._is_traced(frame.f_code.co_filename):
            return None
        identity = id(frame)
        if event == "call":
            state = FrameState(self._next_frame_id)
            self._next_frame_id += 1
            self._frames[identity] = state
            frame.f_trace_lines = True
            return self._trace
        state = self._frames.get(identity)
        if state is None:
            return self._trace
        if event == "line":
            self._record(frame, state)
            state.last_line = frame.f_lineno
        elif event == "return":
            self._record(frame, state)
        elif event == "exception":
            self._record(frame, state, frame.f_lineno)
        if event == "return":
            self._frames.pop(identity, None)
            return None
        return self._trace

    def run(self, script_args: Sequence[str] = ()) -> None:
        script = str(self.target)
        old_argv = sys.argv[:]
        old_path = sys.path[:]
        old_trace = sys.gettrace()
        sys.argv = [script, *script_args]
        sys.path.insert(0, str(self.root))
        try:
            sys.settrace(self._trace)
            runpy.run_path(script, run_name="__main__")
        finally:
            sys.settrace(old_trace)
            sys.argv = old_argv
            sys.path[:] = old_path
            self._frames.clear()


def run_script(
    script: str | Path,
    script_args: Sequence[str] = (),
    database: str | Path = ":memory:",
) -> SQLiteStore:
    """Run a script under tracing and return its still-open history store."""
    target = Path(script).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Python script does not exist: {target}")
    store = SQLiteStore(database)
    run_id = store.create_run(str(target))
    engine = TraceEngine(store, target, run_id)
    try:
        engine.run(script_args)
    except BaseException as error:
        status = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        store.finish_run(run_id, status, f"{type(error).__name__}: {error}")
        store.close()
        raise
    else:
        store.finish_run(run_id, "completed")
    return store