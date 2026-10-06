"""Timeline and execution scrubber control for PyChronicle.

Allows developers to scrub back and forth through execution steps, jump
to arbitrary points in time, and autoplay forward execution.
"""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Button, Label, Static


class TimelineControl(Widget):
    """Interactive time-scrubbing controller with playback controls and progress tracking."""

    DEFAULT_CSS = """
    TimelineControl {
        height: auto;
        min-height: 5;
        background: #11111b;
        border-top: solid #45475a;
        padding: 0 1;
    }

    #timeline-status-row {
        height: 1;
        margin-top: 0;
        margin-bottom: 0;
    }

    #step-badge {
        width: auto;
        min-width: 18;
        background: #313244;
        color: #89dceb;
        text-style: bold;
        padding: 0 1;
        margin-right: 1;
    }

    #track-bar {
        width: 1fr;
        color: #a6e3a1;
        padding: 0 1;
    }

    #event-info-badge {
        width: auto;
        background: #1e1e2e;
        color: #f9e2af;
        padding: 0 1;
        text-style: bold;
    }

    #controls-row {
        height: 3;
        align-horizontal: center;
        margin-top: 0;
    }

    .timeline-btn {
        margin: 0 1;
        min-width: 9;
        height: 3;
    }

    #btn-first {
        background: #313244;
        color: #cdd6f4;
    }

    #btn-prev {
        background: #45475a;
        color: #89b4fa;
        text-style: bold;
    }

    #btn-play {
        background: #a6e3a1;
        color: #11111b;
        text-style: bold;
        min-width: 12;
    }

    #btn-next {
        background: #45475a;
        color: #89b4fa;
        text-style: bold;
    }

    #btn-last {
        background: #313244;
        color: #cdd6f4;
    }

    #btn-speed {
        background: #313244;
        color: #cba6f7;
        min-width: 8;
    }
    """

    class StepChanged(Message):
        """Emitted whenever the active execution step changes."""

        def __init__(self, step_index: int) -> None:
            super().__init__()
            self.step_index = step_index

    class PlayStateChanged(Message):
        """Emitted when autoplay state toggles."""

        def __init__(self, is_playing: bool) -> None:
            super().__init__()
            self.is_playing = is_playing

    current_step: reactive[int] = reactive(1)
    total_steps: reactive[int] = reactive(1)
    is_playing: reactive[bool] = reactive(False)

    SPEEDS = [("0.5x", 0.6), ("1x", 0.3), ("2x", 0.15), ("4x", 0.06)]

    def __init__(
        self,
        total_steps: int = 1,
        current_step: int = 1,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.total_steps = max(1, total_steps)
        self.current_step = min(max(1, current_step), self.total_steps)
        self.speed_index: int = 1  # 1x default
        self._timer: Optional[Timer] = None
        self.line_number: int = 1
        self.function_name: str = "<module>"
        self.event_type: str = "line"

    def compose(self) -> ComposeResult:
        with Horizontal(id="timeline-status-row"):
            yield Label(self._format_badge(), id="step-badge")
            yield Static(self._format_track_bar(), id="track-bar")
            yield Label(self._format_info(), id="event-info-badge")

        with Horizontal(id="controls-row"):
            yield Button("⏮ First", id="btn-first", classes="timeline-btn")
            yield Button("◀ Prev", id="btn-prev", classes="timeline-btn")
            yield Button("▶ Play", id="btn-play", classes="timeline-btn")
            yield Button("Next ▶", id="btn-next", classes="timeline-btn")
            yield Button("Last ⏭", id="btn-last", classes="timeline-btn")
            yield Button("Speed: 1x", id="btn-speed", classes="timeline-btn")

    def _format_badge(self) -> str:
        pct = (self.current_step / self.total_steps) * 100 if self.total_steps > 0 else 0.0
        return f"Step {self.current_step} / {self.total_steps} ({pct:.0f}%)"

    def _format_track_bar(self) -> str:
        """Render a clean Unicode progress scrubber track."""
        width = 36
        if self.total_steps <= 1:
            ratio = 1.0
        else:
            ratio = (self.current_step - 1) / (self.total_steps - 1)

        filled = int(round(ratio * (width - 1)))
        bar = "━" * filled + "●" + "─" * (width - 1 - filled)
        return f"[{bar}]"

    def _format_info(self) -> str:
        return f"Line {self.line_number} | {self.function_name}() | {self.event_type}"

    def update_display(self) -> None:
        try:
            self.query_one("#step-badge", Label).update(self._format_badge())
            self.query_one("#track-bar", Static).update(self._format_track_bar())
            self.query_one("#event-info-badge", Label).update(self._format_info())
        except Exception:
            pass

    def set_total_steps(self, total: int) -> None:
        """Update total steps in trace."""
        self.total_steps = max(1, total)
        self.current_step = min(self.current_step, self.total_steps)
        self.update_display()

    def set_step_info(self, line_number: int, function_name: str, event_type: str = "line") -> None:
        """Update active execution metadata."""
        self.line_number = line_number
        self.function_name = function_name
        self.event_type = event_type
        self.update_display()

    def set_step(self, step: int, notify: bool = True) -> None:
        """Explicitly set step index and emit message."""
        target = min(max(1, step), self.total_steps)
        if target != self.current_step:
            self.current_step = target
            self.update_display()
            if notify:
                self.post_message(self.StepChanged(self.current_step))

    def step_forward(self) -> bool:
        """Scrub forward 1 step."""
        if self.current_step < self.total_steps:
            self.set_step(self.current_step + 1)
            return True
        else:
            if self.is_playing:
                self.pause()
            return False

    def step_backward(self) -> bool:
        """Scrub backward 1 step."""
        if self.current_step > 1:
            self.set_step(self.current_step - 1)
            return True
        return False

    def jump_to_start(self) -> None:
        """Jump to step 1."""
        self.set_step(1)

    def jump_to_end(self) -> None:
        """Jump to last recorded step."""
        self.set_step(self.total_steps)

    def toggle_play(self) -> None:
        """Toggle autoplay mode."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        """Start autoplaying forward in time."""
        if self.current_step >= self.total_steps:
            # If at the end, restart from step 1
            self.set_step(1)

        self.is_playing = True
        try:
            self.query_one("#btn-play", Button).label = "⏸ Pause"
            self.query_one("#btn-play", Button).variant = "warning"
        except Exception:
            pass

        self._start_timer()
        self.post_message(self.PlayStateChanged(True))

    def pause(self) -> None:
        """Pause autoplay."""
        self.is_playing = False
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

        try:
            self.query_one("#btn-play", Button).label = "▶ Play"
            self.query_one("#btn-play", Button).variant = "default"
        except Exception:
            pass

        self.post_message(self.PlayStateChanged(False))

    def _start_timer(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        interval = self.SPEEDS[self.speed_index][1]
        self._timer = self.set_interval(interval, self._on_tick)

    def _on_tick(self) -> None:
        if not self.step_forward():
            self.pause()

    def cycle_speed(self) -> None:
        """Cycle through playback speeds: 0.5x -> 1x -> 2x -> 4x."""
        self.speed_index = (self.speed_index + 1) % len(self.SPEEDS)
        label_text, _ = self.SPEEDS[self.speed_index]
        try:
            self.query_one("#btn-speed", Button).label = f"Speed: {label_text}"
        except Exception:
            pass
        if self.is_playing:
            self._start_timer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-first":
            self.jump_to_start()
        elif button_id == "btn-prev":
            self.step_backward()
        elif button_id == "btn-play":
            self.toggle_play()
        elif button_id == "btn-next":
            self.step_forward()
        elif button_id == "btn-last":
            self.jump_to_end()
        elif button_id == "btn-speed":
            self.cycle_speed()
