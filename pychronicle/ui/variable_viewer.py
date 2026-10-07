"""Variable viewer widget for PyChronicle.

Displays a live inspection table of local variables at the active execution step,
highlighting mutated variables and calculating state differentials.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Input, Label


class VariableViewer(Widget):
    """Interactive variable inspection table with differential mutation highlighting."""

    DEFAULT_CSS = """
    VariableViewer {
        height: 100%;
        background: #181825;
        border: solid #45475a;
    }

    #var-header {
        dock: top;
        height: 1;
        background: #1e1e2e;
        color: #89b4fa;
        text-style: bold;
        padding-left: 1;
        padding-right: 1;
        border-bottom: solid #313244;
    }

    #var-filter {
        dock: top;
        height: 3;
        margin: 0;
        border: none;
        background: #11111b;
        color: #cdd6f4;
    }

    #var-table {
        height: 1fr;
        background: #181825;
    }
    """

    class VariableSelected(Message):
        """Emitted when user selects a variable row (can be used to watch it)."""

        def __init__(self, var_name: str) -> None:
            super().__init__()
            self.var_name = var_name

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_state: Dict[str, Any] = {}
        self.previous_state: Dict[str, Any] = {}
        self.filter_query: str = ""
        self._columns_added: bool = False

    def compose(self) -> ComposeResult:
        yield Label("📊 Variables (0 in scope)", id="var-header")
        yield Input(placeholder="🔍 Filter variables...", id="var-filter")
        yield DataTable(id="var-table", cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one("#var-table", DataTable)
        table.zebra_stripes = True
        if not self._columns_added:
            table.add_columns("Δ", "Variable", "Type", "Current Value", "Mutation Delta")
            self._columns_added = True
        self.render_variables()

    def update_state(
        self,
        current_state: Dict[str, Any],
        previous_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update active variable state and compute deltas against previous step."""
        self.current_state = current_state or {}
        self.previous_state = previous_state or {}
        self.render_variables()

    def _format_value(self, val: Any) -> str:
        """Format Python value safely into a compact string."""
        if isinstance(val, (int, float, bool, type(None))):
            return str(val)
        if isinstance(val, str):
            if len(val) > 40:
                return f'"{val[:37]}..."'
            return f'"{val}"'
        try:
            val_str = json.dumps(val, default=str)
            if len(val_str) > 45:
                return val_str[:42] + "..."
            return val_str
        except Exception:
            s = str(val)
            return s[:42] + "..." if len(s) > 45 else s

    def render_variables(self) -> None:
        """Populate the DataTable with diff badges and sorted mutations."""
        try:
            table = self.query_one("#var-table", DataTable)
            header = self.query_one("#var-header", Label)
        except Exception:
            return

        header.update(f"📊 Variables ({len(self.current_state)} in scope)")
        table.clear()

        if not self.current_state:
            return

        # Partition entries into mutated, new, and unchanged
        rows = []
        q = self.filter_query.lower()

        for var_name, current_val in sorted(self.current_state.items()):
            # Filter check
            type_name = type(current_val).__name__
            if q and (q not in var_name.lower() and q not in type_name.lower()):
                continue

            val_str = self._format_value(current_val)

            if var_name not in self.previous_state:
                # Newly appeared variable
                status = Text("🆕 NEW", style="bold green")
                var_cell = Text(var_name, style="bold green")
                type_cell = Text(type_name, style="green")
                val_cell = Text(val_str, style="bold green")
                delta_cell = Text("Variable initialized", style="green")
                priority = 0
            else:
                prev_val = self.previous_state[var_name]
                if prev_val != current_val:
                    # Mutated variable
                    prev_str = self._format_value(prev_val)
                    status = Text("✨ MOD", style="bold yellow")
                    var_cell = Text(var_name, style="bold yellow")
                    type_cell = Text(type_name, style="yellow")
                    val_cell = Text(val_str, style="bold yellow")
                    delta_cell = Text(f"was {prev_str} ➔ {val_str}", style="bold yellow")
                    priority = 1
                else:
                    # Unchanged
                    status = Text("·", style="dim")
                    var_cell = Text(var_name, style="cdd6f4")
                    type_cell = Text(type_name, style="dim")
                    val_cell = Text(val_str, style="cdd6f4")
                    delta_cell = Text("—", style="dim")
                    priority = 2

            rows.append((priority, status, var_cell, type_cell, val_cell, delta_cell, var_name))

        # Sort so mutated and new variables appear prominently at top
        rows.sort(key=lambda r: r[0])

        for _, status, var_cell, type_cell, val_cell, delta_cell, var_name in rows:
            table.add_row(status, var_cell, type_cell, val_cell, delta_cell, key=var_name)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "var-filter":
            self.filter_query = event.value.strip()
            self.render_variables()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key.value:
            self.post_message(self.VariableSelected(str(event.row_key.value)))
