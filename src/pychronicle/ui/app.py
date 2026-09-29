"""Interactive Textual history browser."""

from __future__ import annotations

from pathlib import Path

from rich.syntax import Syntax
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Static

from pychronicle.storage.database import SQLiteStore
from pychronicle.timeline.history import Timeline


class HistoryApp(App[None]):
    """Browse line events using the left/right arrow keys."""

    CSS = """
    Screen { layout: vertical; }
    #timeline { height: 3; padding: 1 2; color: cyan; }
    #workspace { height: 1fr; }
    #code { width: 2fr; border: round #5f87ff; padding: 1; overflow-y: auto; }
    #state { width: 1fr; border: round #5f87ff; padding: 1; overflow-y: auto; }
    #watch-input { height: 3; }
    """
    BINDINGS = [
        Binding("left", "previous", "Previous event", priority=True),
        Binding("right", "next", "Next event", priority=True),
        Binding("home", "first", "First event", priority=True),
        Binding("end", "last", "Last event", priority=True),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, database: str | Path) -> None:
        super().__init__()
        self.database = Path(database)
        self.store: SQLiteStore | None = None
        self.timeline: Timeline | None = None
        self.position = 0
        self.watches: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Loading trace...", id="timeline")
        with Horizontal(id="workspace"):
            yield Static(id="code")
            with Vertical(id="state"):
                yield Static(id="variables")
                yield Input(placeholder="Watch variable (press Enter)", id="watch-input")
                yield Static("", id="watches")
        yield Footer()

    def on_mount(self) -> None:
        self.store = SQLiteStore(self.database)
        self.timeline = Timeline(self.store)
        self._render_event()

    def on_unmount(self) -> None:
        if self.store is not None:
            self.store.close()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        name = event.value.strip()
        if name:
            self.watches.add(name)
        event.input.value = ""
        self._render_event()

    def action_previous(self) -> None:
        self.position = max(0, self.position - 1)
        self._render_event()

    def action_next(self) -> None:
        if self.timeline:
            self.position = min(max(0, len(self.timeline) - 1), self.position + 1)
        self._render_event()

    def action_first(self) -> None:
        self.position = 0
        self._render_event()

    def action_last(self) -> None:
        if self.timeline:
            self.position = max(0, len(self.timeline) - 1)
        self._render_event()

    def _render_event(self) -> None:
        if self.timeline is None or self.store is None:
            return
        total = len(self.timeline)
        if total == 0:
            self.query_one("#timeline", Static).update("This database contains no trace events.")
            self.query_one("#code", Static).update("No code history available.")
            self.query_one("#variables", Static).update("No variables recorded.")
            return
        snapshot = self.timeline.at(self.position)
        event = snapshot.event
        filled = round((self.position / max(total - 1, 1)) * 30)
        bar = "[" + "=" * filled + ">" + "." * (30 - filled) + "]"
        self.query_one("#timeline", Static).update(
            f"{bar}  Event {self.position + 1}/{total}  "
            f"{Path(event.filename).name}:{event.line_number}  "
            f"{event.function_name}  (use ←/→ to scrub)"
        )
        try:
            source = Path(event.filename).read_text(encoding="utf-8")
            code = Syntax(
                source,
                "python",
                line_numbers=True,
                highlight_lines={event.line_number},
                word_wrap=True,
            )
            self.query_one("#code", Static).update(code)
        except OSError as error:
            self.query_one("#code", Static).update(f"Cannot read source: {error}")
        variables = snapshot.variables
        if self.watches:
            variables = {key: value for key, value in variables.items() if key in self.watches}
        display = "\n".join(f"{name} = {value!r}" for name, value in sorted(variables.items()))
        self.query_one("#variables", Static).update(display or "No variables in this frame.")
        self.query_one("#watches", Static).update(
            "Watching: " + (", ".join(sorted(self.watches)) if self.watches else "(all variables)")
        )