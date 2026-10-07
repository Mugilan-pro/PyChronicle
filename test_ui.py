"""Automated tests for PyChronicle Textual TUI Application."""

import pytest
from pychronicle.storage.models import TraceEvent
from pychronicle.storage.manager import StorageManager
from pychronicle.ui.app import PyChronicleApp
from pychronicle.ui.widgets import CodePane, TimelineScrubber, VariablesTable, WatchPanel


@pytest.fixture
def sample_events():
    return [
        TraceEvent(
            id=1,
            execution_id=1,
            sequence=1,
            line_number=1,
            function_name="<module>",
            event_type="line",
            state={"x": 10},
        ),
        TraceEvent(
            id=2,
            execution_id=1,
            sequence=2,
            line_number=2,
            function_name="<module>",
            event_type="line",
            state={"x": 10, "y": 20},
        ),
        TraceEvent(
            id=3,
            execution_id=1,
            sequence=3,
            line_number=3,
            function_name="<module>",
            event_type="line",
            state={"x": 10, "y": 20, "z": 30},
        ),
    ]


@pytest.mark.anyio
async def test_ui_mount_and_initial_render(sample_events):
    source = "x = 10\ny = 20\nz = 30\n"
    app = PyChronicleApp(
        events=sample_events,
        source_code=source,
        script_name="sample.py",
    )

    async with app.run_test() as pilot:
        assert app.current_idx == 0
        code_pane = app.query_one(CodePane)
        assert code_pane.active_line == 1

        scrubber = app.query_one(TimelineScrubber)
        assert scrubber.current_step == 1
        assert scrubber.total_steps == 3

        var_table = app.query_one(VariablesTable)
        assert var_table.row_count >= 1


@pytest.mark.anyio
async def test_ui_stepping_forward_and_backward(sample_events):
    source = "x = 10\ny = 20\nz = 30\n"
    app = PyChronicleApp(
        events=sample_events,
        source_code=source,
        script_name="sample.py",
    )

    async with app.run_test() as pilot:
        # Step forward
        app.action_step_forward()
        assert app.current_idx == 1
        code_pane = app.query_one(CodePane)
        assert code_pane.active_line == 2

        # Step forward again
        app.action_step_forward()
        assert app.current_idx == 2
        assert code_pane.active_line == 3

        # Step backward (Time-Travel!)
        app.action_step_backward()
        assert app.current_idx == 1
        assert code_pane.active_line == 2


@pytest.mark.anyio
async def test_ui_jump_start_and_end(sample_events):
    app = PyChronicleApp(events=sample_events, source_code="a\nb\nc\n")

    async with app.run_test() as pilot:
        app.action_jump_end()
        assert app.current_idx == 2

        app.action_jump_start()
        assert app.current_idx == 0


@pytest.mark.anyio
async def test_ui_watch_variable_interaction(sample_events):
    app = PyChronicleApp(events=sample_events, source_code="a\nb\nc\n")

    async with app.run_test() as pilot:
        app._apply_watch("z")
        assert app.current_watched_var == "z"
        watch_panel = app.query_one(WatchPanel)
        assert watch_panel.watched_var == "z"
        assert len(watch_panel.history) >= 1
