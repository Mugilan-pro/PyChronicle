"""Code-pane helpers for timeline viewers."""

from rich.syntax import Syntax


def highlighted_source(source: str, line_number: int) -> Syntax:
    return Syntax(
        source,
        "python",
        line_numbers=True,
        highlight_lines={line_number},
        word_wrap=True,
    )