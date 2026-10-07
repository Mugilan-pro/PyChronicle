"""PyChronicle Terminal User Interface (TUI) Subsystem.

Provides interactive time-travel debugging capabilities built on Textual:
- PyChronicleApp: The central dashboard application.
- CodeViewer: Syntax-highlighted code display with execution pointer.
- TimelineControl: Time-scrubbing controls with playback and jump points.
- VariableViewer: Live state table displaying local variables with diff indicators.
- WatchViewer: Variable tracker with mutation timeline and jump-to-step points.
- AddWatchModal & HelpModal: Interactive modal dialogs.
"""

from pychronicle.ui.app import PyChronicleApp
from pychronicle.ui.code_viewer import CodeViewer
from pychronicle.ui.modals import AddWatchModal, HelpModal
from pychronicle.ui.timeline import TimelineControl
from pychronicle.ui.variable_viewer import VariableViewer
from pychronicle.ui.watch_viewer import WatchViewer

__all__ = [
    "AddWatchModal",
    "CodeViewer",
    "HelpModal",
    "PyChronicleApp",
    "TimelineControl",
    "VariableViewer",
    "WatchViewer",
]
