"""Modal dialog screens for PyChronicle Terminal UI."""

from __future__ import annotations

from typing import List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class AddWatchModal(ModalScreen[Optional[str]]):
    """Modal dialog allowing the user to add a variable to the watch list."""

    DEFAULT_CSS = """
    AddWatchModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #add-watch-dialog {
        padding: 1 2;
        width: 60;
        height: auto;
        border: thick $accent;
        background: #1e1e2e;
    }

    #dialog-title {
        text-style: bold;
        color: #89b4fa;
        margin-bottom: 1;
        text-align: center;
    }

    #dialog-instructions {
        color: #a6adc8;
        margin-bottom: 1;
    }

    #watch-input {
        margin-bottom: 1;
        border: tall #89b4fa;
    }

    #suggestions-container {
        height: auto;
        margin-bottom: 1;
    }

    .suggestion-btn {
        margin-right: 1;
        margin-bottom: 1;
        min-width: 8;
        height: 1;
        background: #313244;
        color: #89dceb;
        border: none;
    }

    .suggestion-btn:hover {
        background: #45475a;
        color: #a6e3a1;
    }

    #button-bar {
        align-horizontal: right;
        height: auto;
    }

    #btn-confirm {
        background: #a6e3a1;
        color: #11111b;
        margin-right: 1;
    }

    #btn-cancel {
        background: #f38ba8;
        color: #11111b;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, available_variables: Optional[List[str]] = None) -> None:
        super().__init__()
        self.available_variables = available_variables or []

    def compose(self) -> ComposeResult:
        with Vertical(id="add-watch-dialog"):
            yield Label("🔭 Add Watch Variable", id="dialog-title")
            yield Label(
                "Enter variable name to track across execution time:",
                id="dialog-instructions",
            )
            yield Input(
                placeholder="e.g., total_sum, a, fib_sequence...",
                id="watch-input",
            )

            if self.available_variables:
                yield Label("Variables in current scope:", id="dialog-suggestions-label")
                with Horizontal(id="suggestions-container"):
                    for var_name in self.available_variables[:6]:
                        yield Button(
                            var_name,
                            classes="suggestion-btn",
                            id=f"sug-{var_name}",
                        )

            with Horizontal(id="button-bar"):
                yield Button("Cancel", id="btn-cancel", variant="error")
                yield Button("Add Watch", id="btn-confirm", variant="success")

    def on_mount(self) -> None:
        self.query_one("#watch-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-confirm":
            self._submit()
        elif button_id == "btn-cancel":
            self.action_cancel()
        elif button_id.startswith("sug-"):
            var_name = button_id.replace("sug-", "", 1)
            inp = self.query_one("#watch-input", Input)
            inp.value = var_name
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        val = self.query_one("#watch-input", Input).value.strip()
        if val:
            self.dismiss(val)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class HelpModal(ModalScreen[None]):
    """Modal displaying keybindings and navigation shortcuts."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }

    #help-dialog {
        padding: 1 2;
        width: 72;
        height: auto;
        border: thick #cba6f7;
        background: #1e1e2e;
    }

    #help-title {
        text-style: bold;
        color: #cba6f7;
        margin-bottom: 1;
        text-align: center;
    }

    #help-body {
        color: #cdd6f4;
        margin-bottom: 1;
    }

    #help-btn-close {
        width: 100%;
        background: #cba6f7;
        color: #11111b;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("enter", "dismiss", "Close"),
    ]

    HELP_TEXT = """
[bold cyan]PyChronicle — Time-Travel Debugger Keyboard Controls[/bold cyan]

[bold yellow]Time Navigation:[/bold yellow]
  [green]Left / h[/green]        Step backward 1 event
  [green]Right / l[/green]       Step forward 1 event
  [green]Home / g[/green]        Jump to beginning of execution (Step 1)
  [green]End / G[/green]         Jump to end of execution (Last Step)
  [green]Space / p[/green]     Toggle Autoplay (continuous forward scrub)

[bold yellow]Inspection & Watching:[/bold yellow]
  [green]w[/green]               Add variable to Watch Panel
  [green]f[/green]               Focus variable search filter
  [green]?[/green]               Toggle this Help dialog
  [green]q / Ctrl+C[/green]      Quit PyChronicle

[bold yellow]Time-Travel Tip:[/bold yellow]
In the [bold]Watch Panel[/bold], click on any historical step badge to
jump directly to the moment that variable changed value!
"""

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Label("⚡ PyChronicle Help & Shortcuts", id="help-title")
            yield Static(self.HELP_TEXT, id="help-body")
            yield Button("Close (Esc)", id="help-btn-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-btn-close":
            self.dismiss(None)

    def action_dismiss(self) -> None:
        self.dismiss(None)
