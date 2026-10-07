"""Main Textual Application for PyChronicle Time-Travel Debugger.

Fulfills Week 2 Scaffolding, Week 3 Time-Scrubbing UI, and Week 4 Polish & Watch Variables:
- Code-view pane highlighting the exact line executed historically.
- Timeline scrubber allowing sliding backward and forward through time.
- Variables table with real-time delta highlighting.
- Watch Variables panel allowing tracking specific variables across time.
- Unhandled Exception detection enabling stepping backward from a crash.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, Static

from pychronicle.storage.manager import StorageManager
from pychronicle.storage.models import TraceEvent
from pychronicle.ui.widgets import (
    CodePane,
    ExceptionBanner,
    TimelineScrubber,
    VariablesTable,
    WatchPanel,
)


class PyChronicleApp(App):
    """Textual Terminal User Interface for PyChronicle Time-Travel Debugger."""

    CSS = """
    Screen {
        background: #0f141c;
        color: #e6edf3;
    }

    #main-container {
        height: 1fr;
        layout: horizontal;
    }

    #left-pane {
        width: 55%;
        height: 100%;
        border-right: solid #30363d;
    }

    #right-pane {
        width: 45%;
        height: 100%;
        layout: vertical;
    }

    #variables-pane {
        height: 50%;
        border-bottom: solid #30363d;
    }

    #watch-container {
        height: 50%;
        layout: vertical;
    }

    #watch-input {
        dock: bottom;
        margin: 0 1;
        background: #161b22;
        border: tall #388bfd;
    }

    #timeline-container {
        height: 5;
        dock: bottom;
        background: #161b22;
        border-top: solid #30363d;
        padding: 0 1;
    }

    #controls-bar {
        height: 3;
        dock: bottom;
        layout: horizontal;
        align: center middle;
        background: #090d13;
    }

    #controls-bar Button {
        margin: 0 1;
        min-width: 8;
        height: 1;
    }

    ExceptionBanner {
        dock: top;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("h", "step_backward", "Step Back", show=True),
        Binding("left", "step_backward", "Step Back", show=False),
        Binding("l", "step_forward", "Step Fwd", show=True),
        Binding("right", "step_forward", "Step Fwd", show=False),
        Binding("j", "jump_backward", "-10 Steps", show=True),
        Binding("down", "jump_backward", "-10 Steps", show=False),
        Binding("k", "jump_forward", "+10 Steps", show=True),
        Binding("up", "jump_forward", "+10 Steps", show=False),
        Binding("g", "jump_start", "Start", show=True),
        Binding("home", "jump_start", "Start", show=False),
        Binding("G", "jump_end", "End", show=True),
        Binding("end", "jump_end", "End", show=False),
        Binding("space", "toggle_play", "Play/Pause", show=True),
        Binding("w", "focus_watch", "Watch Var", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(
        self,
        events: List[TraceEvent],
        source_code: str = "",
        script_name: str = "target_script.py",
        storage: Optional[StorageManager] = None,
        exception_info: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.events = events or []
        self.source_code = source_code
        self.script_name = script_name
        self.storage = storage
        self.exception_info = exception_info or ""

        self.total_steps = max(1, len(self.events))
        # Default position: if crashed, start at crash event; otherwise at step 1
        self.current_idx: int = len(self.events) - 1 if self.exception_info and self.events else 0
        self.is_playing: bool = False
        self._playback_timer = None
        self.current_watched_var: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        if self.exception_info:
            yield ExceptionBanner(id="exc-banner")

        with Container(id="main-container"):
            with Vertical(id="left-pane"):
                yield CodePane(
                    source_code=self.source_code,
                    script_name=self.script_name,
                    id="code-pane",
                )

            with Vertical(id="right-pane"):
                with Vertical(id="variables-pane"):
                    yield VariablesTable(id="variables-table")
                with Vertical(id="watch-container"):
                    yield WatchPanel(id="watch-panel")
                    yield Input(
                        placeholder="Type variable name to watch and press Enter...",
                        id="watch-input",
                    )

        with Vertical(id="timeline-container"):
            yield TimelineScrubber(id="timeline-scrubber")

        with Horizontal(id="controls-bar"):
            yield Button("⏮ Start", id="btn-start", variant="default")
            yield Button("◀ Back", id="btn-back", variant="primary")
            yield Button("▶ Play", id="btn-play", variant="success")
            yield Button("Fwd ▶", id="btn-fwd", variant="primary")
            yield Button("End ⏭", id="btn-end", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize UI widgets with the first execution frame."""
        if self.exception_info:
            banner = self.query_one(ExceptionBanner)
            banner.exc_info = self.exception_info

        scrubber = self.query_one(TimelineScrubber)
        scrubber.total_steps = self.total_steps

        # Auto-watch first non-trivial variable if available
        if self.events and self.events[0].state:
            candidate_vars = [k for k in self.events[0].state if not k.startswith("_")]
            if candidate_vars:
                self._apply_watch(candidate_vars[0])

        self._render_current_step()

    def _render_current_step(self) -> None:
        """Synchronize CodePane, VariablesTable, and Scrubber with current timeline step."""
        if not self.events:
            return

        idx = max(0, min(self.current_idx, len(self.events) - 1))
        event = self.events[idx]
        prev_event = self.events[idx - 1] if idx > 0 else None

        # 1. Update Code Pane active line
        code_pane = self.query_one(CodePane)
        code_pane.active_line = event.line_number

        # 2. Update Timeline Scrubber
        scrubber = self.query_one(TimelineScrubber)
        scrubber.current_step = event.sequence
        scrubber.total_steps = self.total_steps
        scrubber.current_func = event.function_name
        scrubber.event_type = event.event_type
        scrubber.is_playing = self.is_playing

        # 3. Update Variables Table
        var_table = self.query_one(VariablesTable)
        curr_state = event.state or {}
        prev_state = prev_event.state if prev_event else {}
        var_table.update_variables(curr_state, prev_state)

        # 4. Refresh Watch Panel if active
        if self.current_watched_var:
            self._refresh_watch_panel(self.current_watched_var)

    def _apply_watch(self, var_name: str) -> None:
        """Set active watched variable and load its mutation history."""
        self.current_watched_var = var_name
        self._refresh_watch_panel(var_name)

    def _refresh_watch_panel(self, var_name: str) -> None:
        history: List[Dict[str, Any]] = []
        if self.storage:
            history = self.storage.get_variable_history(var_name)
        else:
            # Reconstruct from in-memory events
            prev_val = None
            for ev in self.events:
                if ev.state and var_name in ev.state:
                    val = ev.state[var_name]
                    if val != prev_val:
                        history.append({
                            "sequence": ev.sequence,
                            "line_number": ev.line_number,
                            "value": val,
                        })
                        prev_val = val

        watch_panel = self.query_one(WatchPanel)
        watch_panel.set_watch(var_name, history)

    # --------------------------------------------------------------------------
    # Interactive Actions & Keybindings
    # --------------------------------------------------------------------------

    def action_step_forward(self) -> None:
        """Step forward 1 execution frame."""
        if self.current_idx < len(self.events) - 1:
            self.current_idx += 1
            self._render_current_step()

    def action_step_backward(self) -> None:
        """Step backward 1 execution frame (Time-Travel!)."""
        if self.current_idx > 0:
            self.current_idx -= 1
            self._render_current_step()

    def action_jump_forward(self) -> None:
        """Jump forward 10 execution frames."""
        self.current_idx = min(len(self.events) - 1, self.current_idx + 10)
        self._render_current_step()

    def action_jump_backward(self) -> None:
        """Jump backward 10 execution frames."""
        self.current_idx = max(0, self.current_idx - 10)
        self._render_current_step()

    def action_jump_start(self) -> None:
        """Jump to the very beginning of execution."""
        self.current_idx = 0
        self._render_current_step()

    def action_jump_end(self) -> None:
        """Jump to the final recorded frame."""
        self.current_idx = max(0, len(self.events) - 1)
        self._render_current_step()

    def action_toggle_play(self) -> None:
        """Toggle auto-playback mode."""
        self.is_playing = not self.is_playing
        btn = self.query_one("#btn-play", Button)
        if self.is_playing:
            btn.label = "⏸ Pause"
            self._playback_timer = self.set_interval(0.15, self._playback_tick)
        else:
            btn.label = "▶ Play"
            if self._playback_timer:
                self._playback_timer.stop()
                self._playback_timer = None
        self.query_one(TimelineScrubber).is_playing = self.is_playing

    def _playback_tick(self) -> None:
        """Timer callback for animated playback."""
        if not self.is_playing:
            return
        if self.current_idx < len(self.events) - 1:
            self.current_idx += 1
            self._render_current_step()
        else:
            # Reached end: stop playback
            self.action_toggle_play()

    def action_focus_watch(self) -> None:
        """Focus the watch input box."""
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle variable watch request from input box."""
        var_name = event.value.strip()
        if var_name:
            self._apply_watch(var_name)
            event.input.value = ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks from controls bar."""
        btn_id = event.button.id
        if btn_id == "btn-start":
            self.action_jump_start()
        elif btn_id == "btn-back":
            self.action_step_backward()
        elif btn_id == "btn-play":
            self.action_toggle_play()
        elif btn_id == "btn-fwd":
            self.action_step_forward()
        elif btn_id == "btn-end":
            self.action_jump_end()

    @classmethod
    def from_database(
        cls,
        db_path: str,
        script_path: Optional[str] = None,
        execution_id: Optional[int] = None,
    ) -> PyChronicleApp:
        """Construct a PyChronicleApp directly from a recorded SQLite trace file."""
        storage = StorageManager(db_path=db_path)
        events = storage.get_events(execution_id=execution_id)
        exec_record = storage.get_execution(execution_id)

        source_code = ""
        script_name = exec_record.script_name if exec_record else "script.py"

        resolved_path = script_path or script_name
        if resolved_path and os.path.exists(resolved_path):
            with open(resolved_path, "r", encoding="utf-8") as f:
                source_code = f.read()

        return cls(
            events=events,
            source_code=source_code,
            script_name=script_name,
            storage=storage,
        )


def launch_debugger(
    events: List[TraceEvent],
    source_code: str = "",
    script_name: str = "script.py",
    storage: Optional[StorageManager] = None,
    exception_info: Optional[str] = None,
) -> None:
    """Convenience launcher for the PyChronicle Textual app."""
    app = PyChronicleApp(
        events=events,
        source_code=source_code,
        script_name=script_name,
        storage=storage,
        exception_info=exception_info,
    )
    app.run()
