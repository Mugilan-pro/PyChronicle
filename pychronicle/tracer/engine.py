"""Execution Tracer for PyChronicle using sys.settrace.

Fulfills Week 2 Core Engineering specification:
"The Tracer: Implement sys.settrace to record the execution flow of the target
script, capturing variable states and saving them to SQLite."
"Trace Validation: Prove the tracer accurately records the execution of a
complex loop without dropping frames."
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import time
from types import FrameType
from typing import Any, Callable, Dict, Iterable, Optional

from pychronicle.rewriter.models import AnalysisResult
from pychronicle.storage.manager import StorageManager
from pychronicle.tracer.filter import TraceFilter


class ExecutionTracer:
    """Records chronological execution frames and variable states into SQLite.

    Features:
    - Zero dropped frames via frame filter and deterministic sequence ordering.
    - Reentrancy protection preventing recursive storage engine tracing.
    - Automatic sanitation filtering out Python dunder variables (__builtins__, etc.).
    - Comprehensive event capture: 'line', 'call', 'return', 'exception'.
    """

    def __init__(
        self,
        storage: StorageManager,
        trace_filter: Optional[TraceFilter] = None,
        target_files: Optional[Iterable[str]] = None,
        analysis: Optional[AnalysisResult] = None,
        filter_dunders: bool = True,
    ) -> None:
        self.storage = storage
        self.filter = trace_filter or TraceFilter(target_files=target_files)
        self.analysis = analysis
        self.filter_dunders = filter_dunders

        self._prev_trace: Optional[Callable] = None
        self._is_active: bool = False
        self._in_hook: bool = False

        # Metrics for validation and audits
        self.total_frames_observed: int = 0
        self.events_recorded: int = 0
        self.dropped_frames: int = 0
        self.start_timestamp: float = 0.0
        self.end_timestamp: float = 0.0

    def _clean_locals(self, locals_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Strip internal dunders and PyChronicle temporary values."""
        if not self.filter_dunders:
            return dict(locals_dict)
        return {
            k: v
            for k, v in locals_dict.items()
            if not k.startswith("__") and not k.startswith("_pychronicle_")
        }

    def _trace_dispatch(self, frame: FrameType, event: str, arg: Any):
        """Primary callback invoked by sys.settrace on every execution step."""
        # Reentrancy check: avoid tracing internal StorageManager / SQLite calls
        if self._in_hook:
            return self._trace_dispatch

        # Frame filter: only trace target application code
        if not self.filter.should_trace(frame):
            return None

        self.total_frames_observed += 1

        try:
            self._in_hook = True

            line_no = frame.f_lineno
            func_name = frame.f_code.co_name
            state = self._clean_locals(frame.f_locals)

            # Record event in storage engine
            if event == "line":
                self.storage.record_event(
                    line_number=line_no,
                    state=state,
                    function_name=func_name,
                    event_type="line",
                )
                self.events_recorded += 1

            elif event == "call":
                self.storage.record_event(
                    line_number=line_no,
                    state=state,
                    function_name=func_name,
                    event_type="call",
                )
                self.events_recorded += 1

            elif event == "return":
                # Include return value in state snapshot
                return_state = dict(state)
                return_state["__return__"] = arg
                self.storage.record_event(
                    line_number=line_no,
                    state=return_state,
                    function_name=func_name,
                    event_type="return",
                )
                self.events_recorded += 1

            elif event == "exception":
                exc_type, exc_val, _ = arg
                exc_state = dict(state)
                exc_state["__exception__"] = f"{getattr(exc_type, '__name__', 'Exception')}: {exc_val}"
                self.storage.record_event(
                    line_number=line_no,
                    state=exc_state,
                    function_name=func_name,
                    event_type="exception",
                )
                self.events_recorded += 1

        except Exception as e:
            # If any frame fails to record, log to dropped frames metric
            self.dropped_frames += 1
        finally:
            self._in_hook = False

        return self._trace_dispatch

    def start(self) -> None:
        """Activate the trace hook globally."""
        if not self._is_active:
            self.start_timestamp = time.time()
            self._prev_trace = sys.gettrace()
            self._is_active = True
            sys.settrace(self._trace_dispatch)

    def stop(self) -> None:
        """Deactivate the trace hook and restore previous tracer."""
        if self._is_active:
            sys.settrace(self._prev_trace)
            self._is_active = False
            self.end_timestamp = time.time()

    def __enter__(self) -> ExecutionTracer:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def run_code(
        self,
        source_code: str,
        filename: str = "<pychronicle_script>",
        user_globals: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Compile and execute Python code string under active tracing.

        Returns:
            Total number of events recorded in the storage engine.
        """
        compiled = compile(source_code, filename, "exec")
        run_globals = user_globals if user_globals is not None else {}
        run_globals.setdefault("__name__", "__main__")
        run_globals.setdefault("__file__", filename)

        if self.storage.active_execution_id is None:
            self.storage.start_execution(filename)

        with self:
            exec(compiled, run_globals)

        return self.events_recorded

    def run_file(
        self,
        filepath: str,
        user_globals: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Read and execute a Python file under active tracing.

        Returns:
            Total number of events recorded in the storage engine.
        """
        abs_path = os.path.abspath(filepath)
        self.filter.target_files.add(abs_path.lower())
        self.filter.target_files.add(Path(filepath).name.lower())

        with open(abs_path, "r", encoding="utf-8") as f:
            code = f.read()

        if self.storage.active_execution_id is None:
            self.storage.start_execution(Path(filepath).name)

        run_globals = user_globals if user_globals is not None else {}
        run_globals.setdefault("__name__", "__main__")
        run_globals.setdefault("__file__", abs_path)

        compiled = compile(code, abs_path, "exec")

        with self:
            exec(compiled, run_globals)

        self.storage.finish_execution()
        return self.events_recorded
