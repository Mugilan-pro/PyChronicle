"""Custom UI Widgets for PyChronicle Time-Travel Debugger."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Input, Label, Static


class CodePane(Static):
    """Source code viewing pane with line numbering and dynamic execution pointer."""

    active_line: reactive[int] = reactive(1)

    def __init__(
        self,
        source_code: str,
        script_name: str = "script.py",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.script_name = script_name
        self.lines = source_code.splitlines() if source_code else ["# No source code available"]

    def watch_active_line(self, new_line: int) -> None:
        self.refresh()

    def render(self) -> Panel:
        table = Table(
            box=None,
            show_header=False,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("pointer", width=3, justify="right")
        table.add_column("lineno", width=5, justify="right", style="dim cyan")
        table.add_column("code", style="white")

        total_lines = len(self.lines)
        # Window around the active line to make display neat
        window_size = 25
        half = window_size // 2
        start_idx = max(0, self.active_line - 1 - half)
        end_idx = min(total_lines, start_idx + window_size)
        if end_idx - start_idx < window_size:
            start_idx = max(0, end_idx - window_size)

        for idx in range(start_idx, end_idx):
            lineno = idx + 1
            code_text = self.lines[idx]
            is_active = (lineno == self.active_line)

            if is_active:
                pointer = Text("▶", style="bold green")
                num_text = Text(f"{lineno:4d}", style="bold black on green")
                line_content = Text(f" {code_text}", style="bold white on #1e3a29")
            else:
                pointer = Text(" ")
                num_text = Text(f"{lineno:4d}", style="dim cyan")
                line_content = Text(f" {code_text}")

            table.add_row(pointer, num_text, line_content)

        return Panel(
            table,
            title=f"[bold green] Source: {self.script_name} [/bold green] (Line {self.active_line}/{total_lines})",
            border_style="green" if self.active_line > 0 else "blue",
        )


class TimelineScrubber(Static):
    """Scrubbable timeline showing current step, total frames, and playback state."""

    current_step: reactive[int] = reactive(1)
    total_steps: reactive[int] = reactive(1)
    is_playing: reactive[bool] = reactive(False)
    current_func: reactive[str] = reactive("<module>")
    event_type: reactive[str] = reactive("line")

    def watch_current_step(self, step: int) -> None:
        self.refresh()

    def watch_is_playing(self, playing: bool) -> None:
        self.refresh()

    def render(self) -> Panel:
        pct = (self.current_step / max(1, self.total_steps)) * 100.0
        bar_len = 30
        filled = int((pct / 100.0) * bar_len)
        bar = "━" * filled + "╸" + "─" * max(0, bar_len - filled - 1)

        play_indicator = "[bold green]▶ PLAYING[/bold green]" if self.is_playing else "[bold yellow]⏸ PAUSED[/bold yellow]"
        ev_style = {
            "line": "cyan",
            "call": "yellow",
            "return": "magenta",
            "exception": "bold red",
        }.get(self.event_type, "white")

        msg = (
            f" [bold white]Step:[/bold white] [bold cyan]{self.current_step:4d}[/bold cyan] / {self.total_steps:<4d}  "
            f"[bold green][{bar}][/bold green] [dim]{pct:5.1f}%[/dim]   "
            f"{play_indicator}   "
            f"[bold white]Scope:[/bold white] [green]{self.current_func}()[/green]   "
            f"[bold white]Event:[/bold white] [{ev_style}]{self.event_type.upper()}[/{ev_style}]"
        )

        return Panel(
            Text.from_markup(msg),
            title="[bold yellow] Execution Timeline (Time-Travel Scrubber) [/bold yellow]",
            border_style="yellow",
        )


class VariablesTable(DataTable):
    """Table showing active local variables with mutation highlighting."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("Variable", "Type", "Value", "Delta")

    def update_variables(
        self,
        current_state: Dict[str, Any],
        prev_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Refresh table entries, highlighting mutated variables in green."""
        self.clear()
        prev = prev_state or {}

        for var_name, val in sorted(current_state.items()):
            val_type = type(val).__name__
            val_repr = repr(val)
            if len(val_repr) > 40:
                val_repr = val_repr[:37] + "..."

            # Determine delta mutation status
            if var_name not in prev:
                delta_tag = Text("+ NEW", style="bold green")
                row_style = "bold green"
            elif prev[var_name] != val:
                delta_tag = Text("Δ MODIFIED", style="bold yellow")
                row_style = "bold yellow"
            else:
                delta_tag = Text("─", style="dim")
                row_style = "white"

            self.add_row(
                Text(var_name, style=row_style),
                Text(val_type, style="dim cyan"),
                Text(val_repr, style=row_style),
                delta_tag,
            )


class WatchPanel(Static):
    """Panel displaying historical values of a watched variable across time."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.watched_var: Optional[str] = None
        self.history: List[Dict[str, Any]] = []

    def set_watch(self, var_name: str, history: List[Dict[str, Any]]) -> None:
        self.watched_var = var_name
        self.history = history
        self.refresh()

    def render(self) -> Panel:
        if not self.watched_var:
            return Panel(
                Text("Press 'w' or click below to enter a variable to watch.", style="dim italic"),
                title="[bold magenta] Watch Variable Timeline [/bold magenta]",
                border_style="magenta",
            )

        table = Table(box=None, expand=True, padding=(0, 1))
        table.add_column("Step", width=6, style="dim cyan")
        table.add_column("Line", width=6, style="cyan")
        table.add_column("Value", style="bold white")

        # Show latest 8 mutations
        display_items = self.history[-8:] if len(self.history) > 8 else self.history
        for h in display_items:
            v_repr = repr(h.get("value", ""))
            if len(v_repr) > 30:
                v_repr = v_repr[:27] + "..."
            table.add_row(
                f"#{h.get('sequence', 0)}",
                f"L{h.get('line_number', 0)}",
                v_repr,
            )

        if not self.history:
            table.add_row("─", "─", "[dim](No mutations recorded)[/dim]")

        return Panel(
            table,
            title=f"[bold magenta] Watch Timeline: '{self.watched_var}' ({len(self.history)} mutations) [/bold magenta]",
            border_style="magenta",
        )


class ExceptionBanner(Static):
    """Alert banner displayed when an execution terminated with an uncaught exception."""

    exc_info: reactive[str] = reactive("")

    def watch_exc_info(self, info: str) -> None:
        self.refresh()

    def render(self) -> Panel:
        if not self.exc_info:
            return Panel(Text(""))

        return Panel(
            Text(f"CRASH DETECTED: {self.exc_info}\n(Use [h] to step backward in time to inspect root cause)", style="bold white on red"),
            title="[bold red] UNHANDLED EXCEPTION [/bold red]",
            border_style="red",
        )
