"""PyChronicle Terminal User Interface (TUI) Subsystem (Weeks 1 & 2).

Provides interactive time-travel debugging capabilities built on Textual:
- PyChronicleApp: The central dashboard application scaffolding.
- CodeViewer: Syntax-highlighted code display with execution pointer.
- TimelineControl: Time-scrubbing controls with playback and jump points.
- VariableViewer: Live state table displaying local variables.
- HelpModal: Interactive help and shortcuts modal dialog.
"""

from pychronicle.ui.app import PyChronicleApp
from pychronicle.ui.code_viewer import CodeViewer
from pychronicle.ui.modals import HelpModal
from pychronicle.ui.timeline import TimelineControl
from pychronicle.ui.variable_viewer import VariableViewer

__all__ = [
    "CodeViewer",
    "HelpModal",
    "PyChronicleApp",
    "TimelineControl",
    "VariableViewer",
]
