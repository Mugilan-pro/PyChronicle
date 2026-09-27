"""Modal dialog screens for PyChronicle Terminal UI (Weeks 1 & 2)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class HelpModal(ModalScreen[None]):
    """Modal displaying keybindings and time-travel debugging instructions."""

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
[bold cyan]PyChronicle — Time-Travel Debugger (TUI Controls)[/bold cyan]

[bold yellow]Time Navigation:[/bold yellow]
  [green]Left / h[/green]        Step backward 1 event
  [green]Right / l[/green]       Step forward 1 event
  [green]Home / g[/green]        Jump to beginning of execution (Step 1)
  [green]End / G[/green]         Jump to end of execution (Last Step)
  [green]Space / p[/green]     Toggle Autoplay (continuous forward scrub)

[bold yellow]Inspection:[/bold yellow]
  [green]f[/green]               Focus variable search filter
  [green]?[/green]               Toggle this Help dialog
  [green]q / Ctrl+C[/green]      Quit PyChronicle

[bold yellow]Layout Overview:[/bold yellow]
  • [bold]Code Pane (Left):[/bold] Highlights current executing line with auto-scroll.
  • [bold]Variables (Right):[/bold] Displays local variable states and differential mutations.
  • [bold]Timeline (Bottom):[/bold] Scrubber bar showing current execution step and progress.
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
