"""Asynchronous UI tests for PyChronicle Terminal UI (Weeks 1 & 2).

Tests CodeViewer, TimelineControl, VariableViewer, modals,
and time-travel keyboard navigation.
"""

import os
import pytest
from rich.syntax import Syntax
from textual.widgets import Button, DataTable, Input, Label, Static

from pychronicle.storage.manager import StorageManager
from pychronicle.storage.mock_tracer import run_mock_trace_session
from pychronicle.ui.app import PyChronicleApp
from pychronicle.ui.code_viewer import CodeViewer
from pychronicle.ui.modals import HelpModal
from pychronicle.ui.timeline import TimelineControl
from pychronicle.ui.variable_viewer import VariableViewer


@pytest.mark.asyncio
async def test_app_mount_and_initialization():
    """Verify PyChronicleApp loads and renders all sub-widgets properly."""
    app = PyChronicleApp()
    async with app.run_test() as pilot:
        # Check presence of major widgets
        code_viewer = app.query_one("#code-viewer", CodeViewer)
        timeline = app.query_one("#timeline-control", TimelineControl)
        var_viewer = app.query_one("#var-viewer", VariableViewer)

        assert code_viewer is not None
        assert timeline is not None
        assert var_viewer is not None

        # Verify trace events are loaded
        assert len(app.events) > 0
        assert timeline.total_steps == len(app.events)
        assert timeline.current_step == 1


@pytest.mark.asyncio
async def test_code_viewer_highlight_and_scrolling():
    """Verify CodeViewer updates highlighted line and handles source files."""
    app = PyChronicleApp()
    async with app.run_test() as pilot:
        code_viewer = app.query_one("#code-viewer", CodeViewer)

        # Highlight line 12
        code_viewer.highlight_line(12)
        assert code_viewer.active_line == 12

        header_label = app.query_one("#code-header", Label)
        assert "Line 12" in str(header_label.render())

        # Test setting custom code
        sample_code = "x = 1\ny = 2\nz = 3\n"
        code_viewer.set_code(sample_code, "custom_script.py")
        assert code_viewer.total_lines == 3
        assert "custom_script.py" in code_viewer.file_path

        # Test graceful missing file loading
        loaded = code_viewer.load_file("/non/existent/path/script.py")
        assert loaded is False
        assert "not accessible on disk" in code_viewer.source_code


@pytest.mark.asyncio
async def test_timeline_stepping_and_clamping():
    """Verify timeline forward, backward, clamping, and jump methods."""
    app = PyChronicleApp()
    async with app.run_test() as pilot:
        timeline = app.query_one("#timeline-control", TimelineControl)

        assert timeline.current_step == 1

        # Step forward
        timeline.step_forward()
        await pilot.pause()
        assert timeline.current_step == 2

        # Step backward
        timeline.step_backward()
        await pilot.pause()
        assert timeline.current_step == 1

        # Backward clamping: should not go below 1
        timeline.step_backward()
        await pilot.pause()
        assert timeline.current_step == 1

        # Jump to end
        timeline.jump_to_end()
        await pilot.pause()
        assert timeline.current_step == timeline.total_steps

        # Forward clamping: should not exceed total_steps
        timeline.step_forward()
        await pilot.pause()
        assert timeline.current_step == timeline.total_steps

        # Jump to start
        timeline.jump_to_start()
        await pilot.pause()
        assert timeline.current_step == 1


@pytest.mark.asyncio
async def test_timeline_autoplay_and_speed():
    """Verify timeline autoplay state and speed toggling."""
    app = PyChronicleApp()
    async with app.run_test() as pilot:
        timeline = app.query_one("#timeline-control", TimelineControl)

        assert not timeline.is_playing

        # Start play
        timeline.play()
        assert timeline.is_playing

        # Pause
        timeline.pause()
        assert not timeline.is_playing

        # Toggle play
        timeline.toggle_play()
        assert timeline.is_playing
        timeline.toggle_play()
        assert not timeline.is_playing

        # Cycle playback speeds
        initial_speed_idx = timeline.speed_index
        timeline.cycle_speed()
        assert timeline.speed_index != initial_speed_idx


@pytest.mark.asyncio
async def test_variable_viewer_deltas_and_filtering():
    """Verify VariableViewer renders mutations, detects deltas, and filters variables."""
    app = PyChronicleApp()
    async with app.run_test() as pilot:
        var_viewer = app.query_one("#var-viewer", VariableViewer)
        table = app.query_one("#var-table", DataTable)

        # Initial state update (step 1)
        var_viewer.update_state({"total_sum": 0, "count": 1}, previous_state=None)
        await pilot.pause()
        assert table.row_count == 2

        # Mutate total_sum (step 2)
        var_viewer.update_state({"total_sum": 10, "count": 1, "new_var": True}, previous_state={"total_sum": 0, "count": 1})
        await pilot.pause()
        assert table.row_count == 3

        # Test search filter
        filter_input = app.query_one("#var-filter", Input)
        filter_input.value = "total"
        await pilot.pause()
        assert table.row_count == 1

        # Clear filter
        filter_input.value = ""
        await pilot.pause()
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_keyboard_navigation():
    """Verify keyboard shortcuts for stepping, jumping, and toggling."""
    app = PyChronicleApp()
    async with app.run_test() as pilot:
        timeline = app.query_one("#timeline-control", TimelineControl)
        assert timeline.current_step == 1

        # Press 'right' or 'l'
        await pilot.press("right")
        assert timeline.current_step == 2

        # Press 'left' or 'h'
        await pilot.press("left")
        assert timeline.current_step == 1

        # Press 'end'
        await pilot.press("end")
        assert timeline.current_step == timeline.total_steps

        # Press 'home'
        await pilot.press("home")
        assert timeline.current_step == 1


@pytest.mark.asyncio
async def test_time_travel_synchronization():
    """Verify moving timeline updates both CodeViewer line and VariableViewer."""
    app = PyChronicleApp()
    async with app.run_test() as pilot:
        timeline = app.query_one("#timeline-control", TimelineControl)
        code_viewer = app.query_one("#code-viewer", CodeViewer)
        var_viewer = app.query_one("#var-viewer", VariableViewer)

        # Jump to step 5
        timeline.set_step(5)
        await pilot.pause()

        event_5 = app.events[4]
        assert code_viewer.active_line == event_5.line_number
        assert "a" in var_viewer.current_state or "limit" in var_viewer.current_state


@pytest.mark.asyncio
async def test_help_modal():
    """Verify HelpModal displays and dismisses cleanly."""
    help_screen = HelpModal()
    app = PyChronicleApp()
    async with app.run_test() as pilot:
        app.push_screen(help_screen)
        await pilot.pause()
        assert app.screen is help_screen

        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is not help_screen


@pytest.mark.asyncio
async def test_empty_trace_handling():
    """Verify PyChronicle handles empty or 0-event trace sessions safely."""
    storage = StorageManager(":memory:")
    exec_id = storage.start_execution("empty_script.py")
    storage.finish_execution(exec_id)

    app = PyChronicleApp(storage=storage, execution_id=exec_id)
    async with app.run_test() as pilot:
        timeline = app.query_one("#timeline-control", TimelineControl)
        assert timeline.total_steps == 1
        assert timeline.current_step == 1
        # Stepping does not raise
        timeline.step_forward()
        timeline.step_backward()
import asyncio

from pychronicle.storage.database import SQLiteStore
from pychronicle.ui.app import HistoryApp


def test_textual_history_app_mounts_and_navigates(tmp_path) -> None:
    source = tmp_path / "viewed.py"
    source.write_text("first = 1\nsecond = 2\n", encoding="utf-8")
    database = tmp_path / "view.sqlite3"
    with SQLiteStore(database) as store:
        run_id = store.create_run(str(source))
        for sequence, line, name, value in ((1, 1, "first", 1), (2, 2, "second", 2)):
            store.record_event(
                run_id=run_id,
                sequence=sequence,
                filename=str(source),
                line_number=line,
                function_name="<module>",
                frame_id=1,
                changes={name: value},
            )

    async def exercise() -> None:
        app = HistoryApp(database)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert "Event 1/2" in str(app.query_one("#timeline").render())
            await pilot.press("right")
            await pilot.pause()
            assert "Event 2/2" in str(app.query_one("#timeline").render())

    asyncio.run(exercise())
