"""Watch Variables viewer widget for PyChronicle (Week 4).

Allows developers to track specific variables across the execution timeline,
view mutation logs, and jump directly to the exact point in time a variable changed.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Label, Static


class WatchViewer(Widget):
    """Panel managing and displaying tracked variables and their mutation timeline."""

    DEFAULT_CSS = """
    WatchViewer {
        height: 100%;
        background: #181825;
        border: solid #45475a;
    }

    #watch-top-bar {
        dock: top;
        height: 3;
        background: #1e1e2e;
        border-bottom: solid #313244;
        align-vertical: middle;
        padding: 0 1;
    }

    #watch-title {
        color: #cba6f7;
        text-style: bold;
        width: 1fr;
    }

    #btn-add-watch {
        background: #cba6f7;
        color: #11111b;
        height: 1;
        min-width: 12;
        border: none;
        text-style: bold;
    }

    #watch-list-scroll {
        height: 1fr;
        background: #11111b;
        padding: 1;
    }

    #watch-empty-placeholder {
        color: #6c7086;
        text-style: italic;
        padding: 1;
        text-align: center;
    }

    .watch-card {
        background: #1e1e2e;
        border: solid #313244;
        margin-bottom: 1;
        padding: 0 1;
        height: auto;
    }

    .watch-card-header {
        height: 1;
        margin-bottom: 0;
    }

    .watch-var-name {
        color: #89dceb;
        text-style: bold;
        width: 1fr;
    }

    .watch-var-curr-val {
        color: #f9e2af;
        text-style: bold;
        margin-right: 1;
    }

    .btn-remove-watch {
        background: #f38ba8;
        color: #11111b;
        height: 1;
        min-width: 3;
        border: none;
    }

    .watch-history-row {
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
    }

    .history-badge {
        background: #313244;
        color: #a6e3a1;
        height: 1;
        min-width: 8;
        margin-right: 1;
        margin-bottom: 1;
        border: none;
    }

    .history-badge:hover {
        background: #89b4fa;
        color: #11111b;
    }
    """

    class RequestAddWatch(Message):
        """Emitted when user clicks Add Watch button."""
        pass

    class JumpToStep(Message):
        """Emitted when user clicks a historical mutation point to travel back in time."""

        def __init__(self, step_index: int) -> None:
            super().__init__()
            self.step_index = step_index

    class WatchListChanged(Message):
        """Emitted when watched variables are added or removed."""

        def __init__(self, watched_vars: List[str]) -> None:
            super().__init__()
            self.watched_vars = watched_vars

    def __init__(
        self,
        initial_watches: Optional[List[str]] = None,
        history_provider: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.watched_variables: List[str] = list(initial_watches or [])
        self.history_provider = history_provider
        self.current_state: Dict[str, Any] = {}
        self.current_step: int = 1
        self._history_cache: Dict[str, List[Dict[str, Any]]] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="watch-top-bar"):
            yield Label(self._format_title(), id="watch-title")
            yield Button("+ Add Watch", id="btn-add-watch")

        with VerticalScroll(id="watch-list-scroll"):
            yield Static(
                "No variables watched yet.\nClick '+ Add Watch' or press 'w' to track a variable across execution time.",
                id="watch-empty-placeholder",
            )

    def _format_title(self) -> str:
        count = len(self.watched_variables)
        return f"🔭 Watch Variables ({count} tracked)"

    def set_history_provider(self, provider: Callable[[str], List[Dict[str, Any]]]) -> None:
        """Set or update the variable history fetcher."""
        self.history_provider = provider
        self._history_cache.clear()
        self.refresh_watches()

    def add_watch(self, var_name: str) -> bool:
        """Add a variable to watch list if not already present."""
        clean_name = var_name.strip()
        if not clean_name or clean_name in self.watched_variables:
            return False

        self.watched_variables.append(clean_name)
        self.refresh_watches()
        self.post_message(self.WatchListChanged(self.watched_variables))
        return True

    def remove_watch(self, var_name: str) -> bool:
        """Remove a variable from watch list."""
        if var_name in self.watched_variables:
            self.watched_variables.remove(var_name)
            self._history_cache.pop(var_name, None)
            self.refresh_watches()
            self.post_message(self.WatchListChanged(self.watched_variables))
            return True
        return False

    def update_step(self, current_step: int, current_state: Dict[str, Any]) -> None:
        """Update current step and active variables snapshot."""
        self.current_step = current_step
        self.current_state = current_state or {}
        self.refresh_watches()

    def _get_history(self, var_name: str) -> List[Dict[str, Any]]:
        """Fetch and cache chronological mutation history for a variable."""
        if var_name not in self._history_cache and self.history_provider is not None:
            try:
                self._history_cache[var_name] = self.history_provider(var_name)
            except Exception:
                self._history_cache[var_name] = []
        return self._history_cache.get(var_name, [])

    def refresh_watches(self) -> None:
        """Re-render watched variable cards."""
        try:
            title = self.query_one("#watch-title", Label)
            title.update(self._format_title())
        except Exception:
            pass

        try:
            container = self.query_one("#watch-list-scroll", VerticalScroll)
        except Exception:
            return

        self.call_after_refresh(self._mount_cards)

    async def _mount_cards(self) -> None:
        container = self.query_one("#watch-list-scroll", VerticalScroll)
        await container.remove_children()

        if not self.watched_variables:
            await container.mount(
                Static(
                    "No variables watched yet.\nClick '+ Add Watch' or press 'w' to track a variable across execution time.",
                    id="watch-empty-placeholder",
                )
            )
            return

        for var_name in self.watched_variables:
            curr_val_str = (
                str(self.current_state[var_name])
                if var_name in self.current_state
                else "(out of scope)"
            )
            history = self._get_history(var_name)

            name_lbl = Label(f"🔍 {var_name}", classes="watch-var-name")
            val_lbl = Label(f"Now: {curr_val_str}", classes="watch-var-curr-val")
            del_btn = Button("✕", id=f"del-{var_name}", classes="btn-remove-watch")
            header_row = Horizontal(name_lbl, val_lbl, del_btn, classes="watch-card-header")

            history_items = []
            if history:
                # Add up to 8 historical mutation points
                for mutation in history[:8]:
                    seq = mutation.get("sequence", 1)
                    val = mutation.get("value", "")
                    val_repr = str(val)[:10]
                    btn = Button(
                        f"#{seq}: {val_repr}",
                        id=f"jump-{seq}",
                        classes="history-badge",
                    )
                    history_items.append(btn)
            else:
                history_items.append(Label("No mutation events recorded.", classes="watch-empty-history"))

            history_row = Horizontal(*history_items, classes="watch-history-row")
            card = Vertical(header_row, history_row, classes="watch-card", id=f"card-{var_name}")
            await container.mount(card)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-add-watch":
            self.post_message(self.RequestAddWatch())
        elif button_id.startswith("del-"):
            var_name = button_id.replace("del-", "", 1)
            self.remove_watch(var_name)
        elif button_id.startswith("jump-"):
            step_str = button_id.replace("jump-", "", 1)
            try:
                step_num = int(step_str)
                self.post_message(self.JumpToStep(step_num))
            except ValueError:
                pass
