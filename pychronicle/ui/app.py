"""Main Textual Application for PyChronicle Time-Travel Debugger (Weeks 1 & 2).

Integrates Code Viewer, Timeline Scrubber, and Variable Viewer into a unified,
hacker-style terminal user interface scaffolding.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input

from pychronicle.storage.manager import StorageManager
from pychronicle.storage.models import ExecutionRecord, TraceEvent
from pychronicle.ui.code_viewer import CodeViewer
from pychronicle.ui.modals import HelpModal
from pychronicle.ui.timeline import TimelineControl
from pychronicle.ui.variable_viewer import VariableViewer


class PyChronicleApp(App[None]):
    """PyChronicle Terminal User Interface (TUI) — Weeks 1 & 2 Scaffolding."""

    TITLE = "PyChronicle — Time-Travel Debugger"
    SUB_TITLE = "Step through execution state"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True, priority=True),
        Binding("left,h", "step_backward", "Step Prev", show=True),
        Binding("right,l", "step_forward", "Step Next", show=True),
        Binding("home,g", "jump_start", "Start", show=True, priority=True),
        Binding("end,G", "jump_end", "End", show=True, priority=True),
        Binding("space,p", "toggle_play", "Play/Pause", show=True),
        Binding("f", "focus_filter", "Filter", show=True),
        Binding("question_mark", "show_help", "Help", show=True),
    ]

    CSS = """
    Screen {
        background: #181825;
        color: #cdd6f4;
        layout: vertical;
    }

    Header {
        background: #11111b;
        color: #89b4fa;
        text-style: bold;
    }

    Footer {
        background: #11111b;
        color: #a6adc8;
    }

    #workspace-container {
        height: 1fr;
        layout: horizontal;
    }

    #left-column {
        width: 58%;
        height: 100%;
        border-right: solid #313244;
    }

    #right-column {
        width: 42%;
        height: 100%;
        layout: vertical;
    }

    #var-container {
        height: 100%;
    }

    #timeline-container {
        height: auto;
        dock: bottom;
    }
    """

    def __init__(
        self,
        storage: Optional[StorageManager] = None,
        db_path: Optional[str] = None,
        execution_id: Optional[int] = None,
        source_code: Optional[str] = None,
        script_path: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._owns_storage = False

        if storage is not None:
            self.storage = storage
        elif db_path is not None:
            self.storage = StorageManager(db_path)
            self._owns_storage = True
        else:
            # Self-contained in-memory demo session with realistic trace
            self.storage = StorageManager(":memory:")
            self._owns_storage = True
            execution_id = self._create_demo_trace(self.storage)

        self.execution_id = execution_id or self.storage.active_execution_id or 1
        self.script_path = script_path
        self.source_code = source_code
        self.events: List[TraceEvent] = []
        self.execution_record: Optional[ExecutionRecord] = None

    def _create_demo_trace(self, storage: StorageManager) -> int:
        """Populate in-memory storage with a rich algorithm trace for standalone demo."""
        demo_script = "sample_scripts/demo_algorithm.py"
        exec_id = storage.start_execution(demo_script, metadata={"mode": "demo_trace"})

        # Simulate execution steps corresponding to demo_algorithm.py
        steps = [
            (6, {"limit": 6}, "compute_fibonacci_stats"),
            (7, {"limit": 6, "total_sum": 0}, "compute_fibonacci_stats"),
            (8, {"limit": 6, "total_sum": 0, "fib_sequence": []}, "compute_fibonacci_stats"),
            (9, {"limit": 6, "total_sum": 0, "fib_sequence": [], "a": 0, "b": 1}, "compute_fibonacci_stats"),
            # Loop step 0 (a=0, b=1)
            (11, {"limit": 6, "total_sum": 0, "fib_sequence": [], "a": 0, "b": 1, "step": 0}, "compute_fibonacci_stats"),
            (12, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 0, "b": 1, "step": 0}, "compute_fibonacci_stats"),
            (13, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 0, "b": 1, "step": 0}, "compute_fibonacci_stats"),
            (14, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 0, "b": 1, "step": 0, "next_val": 1}, "compute_fibonacci_stats"),
            (15, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 1, "b": 1, "step": 0, "next_val": 1}, "compute_fibonacci_stats"),
            (16, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 1, "b": 1, "step": 0, "next_val": 1}, "compute_fibonacci_stats"),
            # Loop step 1 (a=1, b=1)
            (11, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 1, "b": 1, "step": 1, "next_val": 1}, "compute_fibonacci_stats"),
            (12, {"limit": 6, "total_sum": 0, "fib_sequence": [0, 1], "a": 1, "b": 1, "step": 1, "next_val": 1}, "compute_fibonacci_stats"),
            (13, {"limit": 6, "total_sum": 1, "fib_sequence": [0, 1], "a": 1, "b": 1, "step": 1, "next_val": 1}, "compute_fibonacci_stats"),
            (14, {"limit": 6, "total_sum": 1, "fib_sequence": [0, 1], "a": 1, "b": 1, "step": 1, "next_val": 2}, "compute_fibonacci_stats"),
            (15, {"limit": 6, "total_sum": 1, "fib_sequence": [0, 1], "a": 1, "b": 2, "step": 1, "next_val": 2}, "compute_fibonacci_stats"),
            # Loop step 2 (a=1, b=2)
            (11, {"limit": 6, "total_sum": 1, "fib_sequence": [0, 1], "a": 1, "b": 2, "step": 2, "next_val": 2}, "compute_fibonacci_stats"),
            (12, {"limit": 6, "total_sum": 1, "fib_sequence": [0, 1, 1], "a": 1, "b": 2, "step": 2, "next_val": 2}, "compute_fibonacci_stats"),
            (13, {"limit": 6, "total_sum": 2, "fib_sequence": [0, 1, 1], "a": 1, "b": 2, "step": 2, "next_val": 2}, "compute_fibonacci_stats"),
            (14, {"limit": 6, "total_sum": 2, "fib_sequence": [0, 1, 1], "a": 1, "b": 2, "step": 2, "next_val": 3}, "compute_fibonacci_stats"),
            (15, {"limit": 6, "total_sum": 2, "fib_sequence": [0, 1, 1], "a": 2, "b": 3, "step": 2, "next_val": 3}, "compute_fibonacci_stats"),
            # Loop step 3 (a=2, b=3)
            (11, {"limit": 6, "total_sum": 2, "fib_sequence": [0, 1, 1], "a": 2, "b": 3, "step": 3, "next_val": 3}, "compute_fibonacci_stats"),
            (12, {"limit": 6, "total_sum": 2, "fib_sequence": [0, 1, 1, 2], "a": 2, "b": 3, "step": 3, "next_val": 3}, "compute_fibonacci_stats"),
            (13, {"limit": 6, "total_sum": 4, "fib_sequence": [0, 1, 1, 2], "a": 2, "b": 3, "step": 3, "next_val": 3}, "compute_fibonacci_stats"),
            # Post-loop
            (18, {"limit": 6, "total_sum": 4, "fib_sequence": [0, 1, 1, 2], "a": 2, "b": 3, "is_even_total": True}, "compute_fibonacci_stats"),
            (19, {"limit": 6, "total_sum": 4, "fib_sequence": [0, 1, 1, 2], "summary": {"sum": 4, "count": 6}}, "compute_fibonacci_stats"),
            (25, {"result": {"sum": 4, "count": 6}}, "<module>"),
        ]

        for line, state, func in steps:
            storage.record_event(
                line_number=line,
                state=state,
                function_name=func,
            )

        storage.finish_execution(exec_id)
        return exec_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="workspace-container"):
            with Vertical(id="left-column"):
                yield CodeViewer(
                    source_code=self.source_code,
                    file_path=self.script_path or "sample_scripts/demo_algorithm.py",
                    id="code-viewer",
                )
            with Vertical(id="right-column"):
                with Vertical(id="var-container"):
                    yield VariableViewer(id="var-viewer")
        with Vertical(id="timeline-container"):
            yield TimelineControl(id="timeline-control")
        yield Footer()

    def on_mount(self) -> None:
        self._load_trace_data()

    def _load_trace_data(self) -> None:
        """Fetch all execution events and configure sub-widgets."""
        self.execution_record = self.storage.get_execution(self.execution_id)
        if self.execution_record and not self.script_path:
            self.script_path = self.execution_record.script_name

        self.events = self.storage.get_events(self.execution_id)

        code_viewer = self.query_one("#code-viewer", CodeViewer)
        timeline = self.query_one("#timeline-control", TimelineControl)

        if self.script_path and not self.source_code:
            code_viewer.load_file(self.script_path)
        elif self.source_code:
            code_viewer.set_code(self.source_code, self.script_path)

        if self.events:
            timeline.set_total_steps(len(self.events))
            self._display_step(1)
        else:
            timeline.set_total_steps(1)
            code_viewer.highlight_line(1)

    def _display_step(self, step_index: int) -> None:
        """Update code highlight and variable table for a given step."""
        if not self.events:
            return

        idx = min(max(1, step_index), len(self.events)) - 1
        event = self.events[idx]
        prev_event = self.events[idx - 1] if idx > 0 else None

        code_viewer = self.query_one("#code-viewer", CodeViewer)
        timeline = self.query_one("#timeline-control", TimelineControl)
        var_viewer = self.query_one("#var-viewer", VariableViewer)

        code_viewer.highlight_line(event.line_number)
        timeline.set_step_info(event.line_number, event.function_name, event.event_type)
        var_viewer.update_state(event.state, prev_event.state if prev_event else None)

    def on_timeline_control_step_changed(self, message: TimelineControl.StepChanged) -> None:
        """Handle scrub/step update from timeline."""
        self._display_step(message.step_index)

    def action_step_forward(self) -> None:
        self.query_one("#timeline-control", TimelineControl).step_forward()

    def action_step_backward(self) -> None:
        self.query_one("#timeline-control", TimelineControl).step_backward()

    def action_jump_start(self) -> None:
        self.query_one("#timeline-control", TimelineControl).jump_to_start()

    def action_jump_end(self) -> None:
        self.query_one("#timeline-control", TimelineControl).jump_to_end()

    def action_toggle_play(self) -> None:
        self.query_one("#timeline-control", TimelineControl).toggle_play()

    def action_focus_filter(self) -> None:
        try:
            self.query_one("#var-filter", Input).focus()
        except Exception:
            pass

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    def action_quit(self) -> None:
        if self._owns_storage:
            try:
                self.storage.close()
            except Exception:
                pass
        self.exit()


if __name__ == "__main__":
    app = PyChronicleApp()
    app.run()
