"""Code viewer widget for PyChronicle.

Renders syntax-highlighted Python source code with dynamic execution line
highlighting, line numbers, and automatic scrolling to track the program counter.
"""

from __future__ import annotations

import os
from typing import Optional

from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Label, Static


class CodeViewer(Widget):
    """Interactive syntax-highlighted Python code view pane with line tracking."""

    DEFAULT_CSS = """
    CodeViewer {
        height: 100%;
        background: #181825;
        border: solid #45475a;
    }

    #code-header {
        dock: top;
        height: 1;
        background: #1e1e2e;
        color: #89b4fa;
        text-style: bold;
        padding-left: 1;
        padding-right: 1;
        border-bottom: solid #313244;
    }

    #code-scroll {
        height: 1fr;
        background: #11111b;
        scrollbar-gutter: stable;
    }

    #code-content {
        padding: 0 1;
        width: 100%;
        height: auto;
    }
    """

    def __init__(
        self,
        source_code: Optional[str] = None,
        file_path: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path or "script.py"
        self.source_code = source_code or ""
        self.active_line: int = 1
        self.total_lines: int = 1

        if not self.source_code and file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.source_code = f.read()
            except Exception:
                self.source_code = ""

        if not self.source_code:
            self.source_code = f"# PyChronicle Time-Travel Debugger\n# Script: {self.file_path}\n"

        self._refresh_line_count()

    def _refresh_line_count(self) -> None:
        lines = self.source_code.splitlines()
        self.total_lines = max(1, len(lines))

    def compose(self) -> ComposeResult:
        basename = os.path.basename(self.file_path) if self.file_path else "script.py"
        yield Label(f"📄 {basename} | Line {self.active_line} of {self.total_lines}", id="code-header")
        with VerticalScroll(id="code-scroll"):
            yield Static(id="code-content")

    def on_mount(self) -> None:
        self.render_code()

    def set_code(self, source_code: str, file_path: Optional[str] = None) -> None:
        """Update source code and reload view."""
        self.source_code = source_code or "# (Empty script)\n"
        if file_path:
            self.file_path = file_path
        self._refresh_line_count()
        self.render_code()

    def load_file(self, file_path: str) -> bool:
        """Attempt to load source code from disk path."""
        self.file_path = file_path
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.source_code = f.read()
                self._refresh_line_count()
                self.render_code()
                return True
            except Exception:
                pass

        # Fallback if file not on disk
        self.source_code = (
            f"# Source file: {file_path} (not accessible on disk)\n"
            f"# PyChronicle is tracking execution events by line number.\n"
        )
        self._refresh_line_count()
        self.render_code()
        return False

    def highlight_line(self, line_number: int) -> None:
        """Set the active execution line and auto-scroll to it."""
        self.active_line = max(1, line_number)
        self.render_code()
        self._scroll_to_active_line()

    def render_code(self) -> None:
        """Render syntax highlighting with current active line highlighted."""
        try:
            header = self.query_one("#code-header", Label)
            basename = os.path.basename(self.file_path) if self.file_path else "script.py"
            header.update(f"📄 {basename} | Line {self.active_line} of {self.total_lines}")
        except Exception:
            pass

        try:
            content_static = self.query_one("#code-content", Static)
            syntax = Syntax(
                self.source_code,
                "python",
                line_numbers=True,
                highlight_lines={self.active_line},
                theme="monokai",
                word_wrap=False,
            )
            content_static.update(syntax)
        except Exception:
            pass

    def _scroll_to_active_line(self) -> None:
        """Auto-scroll the viewport to keep the active line in view."""
        try:
            scroll_container = self.query_one("#code-scroll", VerticalScroll)
            # Center the line in the view or scroll so it is clearly visible
            target_y = max(0, self.active_line - 5)
            scroll_container.scroll_to(y=target_y, animate=False)
        except Exception:
            pass
