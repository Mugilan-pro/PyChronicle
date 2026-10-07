"""Tests specifically verifying Week 1 & Week 2 TUI deliverables for Member 4.

Project Spec Week 2 Deliverable:
- 'TUI Scaffolding: Initialize a Textual App. Create the layout with a code-view
  pane and a timeline slider.'
- Mid-Project Review: UI scaffolding validation, layout responsiveness, and
  integration readiness with Member 3's SQLite storage schema.
"""

import pytest
from rich.syntax import Syntax
from textual.widgets import DataTable, Footer, Header, Label, Static

from pychronicle.storage.manager import StorageManager
from pychronicle.ui.app import PyChronicleApp
from pychronicle.ui.code_viewer import CodeViewer
from pychronicle.ui.timeline import TimelineControl
from pychronicle.ui.variable_viewer import VariableViewer


@pytest.mark.asyncio
async def test_week2_textual_app_scaffolding_initialization():
    """Week 2 Requirement: Initialize a Textual App with complete layout."""
    app = PyChronicleApp()
    async with app.run_test() as pilot:
        assert app is not None
        assert app.title == "PyChronicle — Time-Travel Debugger"

        # Verify Header and Footer scaffolding
        assert app.query_one(Header) is not None
        assert app.query_one(Footer) is not None

        # Verify workspace container structure
        assert app.query_one("#workspace-container") is not None
        assert app.query_one("#left-column") is not None
        assert app.query_one("#right-column") is not None
        assert app.query_one("#timeline-container") is not None


@pytest.mark.asyncio
async def test_week2_code_view_pane_layout_and_syntax():
    """Week 2 Requirement: Create the layout with a code-view pane."""
    app = PyChronicleApp()
    async with app.run_test() as pilot:
        code_viewer = app.query_one("#code-viewer", CodeViewer)
        assert code_viewer is not None

        # Verify header presence and script metadata
        code_header = app.query_one("#code-header", Label)
        assert code_header is not None
        assert "Line" in str(code_header.render())

        # Verify scroll container and code content static
        code_content = app.query_one("#code-content", Static)
        assert code_content is not None
        assert isinstance(code_content.render()._renderable, Syntax)

        # Verify setting code and updating highlighted line
        sample_code = "a = 10\nb = 20\nc = a + b\n"
        code_viewer.set_code(sample_code, "test_math.py")
        code_viewer.highlight_line(2)
        assert code_viewer.active_line == 2
        assert code_viewer.total_lines == 3


@pytest.mark.asyncio
async def test_week2_timeline_slider_scaffolding():
    """Week 2 Requirement: Create the layout with a timeline slider."""
    app = PyChronicleApp()
    async with app.run_test() as pilot:
        timeline = app.query_one("#timeline-control", TimelineControl)
        assert timeline is not None

        # Verify scrubber track bar and step progress badge
        step_badge = app.query_one("#step-badge", Label)
        assert step_badge is not None
        assert "Step 1" in str(step_badge.render())

        track_bar = app.query_one("#track-bar", Static)
        assert track_bar is not None
        # Track bar contains visual position indicator ●
        assert "●" in str(track_bar.render())

        # Verify controls are present and functional
        assert app.query_one("#btn-first") is not None
        assert app.query_one("#btn-prev") is not None
        assert app.query_one("#btn-play") is not None
        assert app.query_one("#btn-next") is not None
        assert app.query_one("#btn-last") is not None


@pytest.mark.asyncio
async def test_week1_week2_storage_schema_contract_integration():
    """Verify UI consumes Member 3's Week 1 & 2 SQLite schema contract.

    Schema: (timestamp, line_number, variable_name, serialized_value)
    """
    storage = StorageManager(":memory:")
    exec_id = storage.start_execution("contract_test.py")

    # Record 3 events conforming to Week 1 & 2 storage schema
    storage.record_event(line_number=1, state={"x": 100})
    storage.record_event(line_number=2, state={"x": 100, "y": 200})
    storage.record_event(line_number=3, state={"x": 100, "y": 200, "z": 300})
    storage.finish_execution(exec_id)

    app = PyChronicleApp(storage=storage, execution_id=exec_id)
    async with app.run_test() as pilot:
        timeline = app.query_one("#timeline-control", TimelineControl)
        var_viewer = app.query_one("#var-viewer", VariableViewer)
        table = app.query_one("#var-table", DataTable)

        # Scaffolding verified 3 steps loaded
        assert len(app.events) == 3
        assert timeline.total_steps == 3
        assert timeline.current_step == 1

        # Check that variables from step 1 are parsed into the table
        assert "x" in var_viewer.current_state
        assert var_viewer.current_state["x"] == 100

        # Step forward to step 2
        timeline.step_forward()
        await pilot.pause()
        assert timeline.current_step == 2
        assert "y" in var_viewer.current_state
        assert var_viewer.current_state["y"] == 200


@pytest.mark.asyncio
async def test_week2_graceful_missing_source_fallback():
    """Verify TUI handles absent source files without crashing."""
    storage = StorageManager(":memory:")
    exec_id = storage.start_execution("non_existent_on_disk.py")
    storage.record_event(line_number=42, state={"status": "running"})
    storage.finish_execution(exec_id)

    app = PyChronicleApp(storage=storage, execution_id=exec_id)
    async with app.run_test() as pilot:
        code_viewer = app.query_one("#code-viewer", CodeViewer)
        assert code_viewer is not None
        assert code_viewer.active_line == 42
        assert "not accessible on disk" in code_viewer.source_code
