"""End-to-End Integration tests for PyChronicle Storage Subsystem."""

import os
import pytest
from pychronicle.storage.manager import StorageManager
from pychronicle.storage.mock_tracer import generate_fake_events, run_mock_trace_session


def test_fake_tracer_integration_pipeline():
    """Verify fake tracer producing x = 1, 2, 3, 4 across 4 events is correctly stored and retrieved."""
    storage = StorageManager(":memory:")

    exec_id = storage.start_execution("counter_pipeline.py")

    # Simulate tracer producing x = 1, 2, 3, 4 across 4 lines
    for step in range(1, 5):
        storage.record_event(
            line_number=20 + step,
            state={"x": step},
            function_name="increment_test",
        )

    storage.finish_execution(exec_id)

    # 1. Retrieve all events
    events = storage.get_events(exec_id)
    assert len(events) == 4
    assert [ev.sequence for ev in events] == [1, 2, 3, 4]
    assert [ev.line_number for ev in events] == [21, 22, 23, 24]
    assert [ev.state["x"] for ev in events] == [1, 2, 3, 4]

    # 2. Check variable history
    history = storage.get_variable_history("x", execution_id=exec_id)
    assert len(history) == 4
    assert [h["value"] for h in history] == [1, 2, 3, 4]
    assert [h["sequence"] for h in history] == [1, 2, 3, 4]

    storage.close()


def test_disk_file_persistence_across_connections(tmp_path):
    """Verify that an execution recorded to an SQLite file on disk persists and reloads cleanly."""
    db_file = str(tmp_path / "test_trace.db")

    # Session 1: Write trace data to disk
    with StorageManager(db_file) as storage1:
        exec_id = run_mock_trace_session(storage1, script_name="persisted.py", steps=5)

    assert os.path.exists(db_file)

    # Session 2: Fresh connection reading from disk (simulating TUI reader)
    with StorageManager(db_file) as storage2:
        exec_record = storage2.get_execution(exec_id)
        assert exec_record is not None
        assert exec_record.script_name == "persisted.py"
        assert exec_record.completed_at is not None

        events = storage2.get_events(exec_id)
        assert len(events) == 5
        assert [e.sequence for e in events] == [1, 2, 3, 4, 5]
        assert [e.state["x"] for e in events] == [1, 2, 3, 4, 5]
