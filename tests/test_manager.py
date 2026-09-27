"""Unit tests for the high-level StorageManager API."""

import pytest
from pychronicle.storage.manager import StorageManager


@pytest.fixture
def storage():
    """Provides a fresh StorageManager instance backed by in-memory SQLite."""
    mgr = StorageManager(":memory:")
    yield mgr
    mgr.close()


def test_start_and_finish_execution(storage):
    """Verify execution lifecycle management."""
    exec_id = storage.start_execution("test_script.py", metadata={"env": "pytest"})
    assert exec_id == 1
    assert storage.active_execution_id == 1

    exec_record = storage.get_execution()
    assert exec_record.script_name == "test_script.py"
    assert exec_record.metadata == {"env": "pytest"}
    assert exec_record.completed_at is None

    storage.finish_execution()
    assert storage.active_execution_id is None

    # Fetch finished record
    finished_record = storage.get_execution(exec_id)
    assert finished_record.completed_at is not None


def test_record_without_active_execution_raises_error(storage):
    """Verify calling record_event before start_execution raises RuntimeError."""
    with pytest.raises(RuntimeError, match="No active execution session"):
        storage.record_event(line_number=10, state={"x": 1})


def test_record_and_retrieve_single_event(storage):
    """Verify recording an event with state restores identical Python objects."""
    storage.start_execution("app.py")
    ev = storage.record_event(
        line_number=15,
        state={"counter": 42, "user": {"name": "Bob", "active": True}},
        function_name="process_user",
    )
    assert ev.id is not None
    assert ev.sequence == 1
    assert ev.line_number == 15

    fetched = storage.get_event(ev.id)
    assert fetched is not None
    assert fetched.sequence == 1
    assert fetched.line_number == 15
    assert fetched.function_name == "process_user"
    assert fetched.state["counter"] == 42
    assert fetched.state["user"]["name"] == "Bob"
    assert fetched.state["user"]["active"] is True


def test_auto_incrementing_sequence_order(storage):
    """Verify sequence auto-increments and get_events returns strict chronological order."""
    storage.start_execution("order.py")
    storage.record_event(line_number=1, state={"a": 10})
    storage.record_event(line_number=2, state={"a": 20})
    storage.record_event(line_number=3, state={"a": 30})

    events = storage.get_events()
    assert len(events) == 3
    assert [e.sequence for e in events] == [1, 2, 3]
    assert [e.state["a"] for e in events] == [10, 20, 30]


def test_sequence_window_slicing(storage):
    """Verify fetching a subset of events by sequence range."""
    storage.start_execution("slice.py")
    for i in range(1, 11):
        storage.record_event(line_number=i, state={"val": i})

    window = storage.get_events(start_sequence=4, end_sequence=7)
    assert len(window) == 4
    assert [e.sequence for e in window] == [4, 5, 6, 7]
    assert [e.state["val"] for e in window] == [4, 5, 6, 7]


def test_variable_history_watchpoints(storage):
    """Verify tracking a variable across execution time."""
    storage.start_execution("watch.py")
    storage.record_event(line_number=10, state={"score": 0})
    storage.record_event(line_number=11, state={"score": 50, "other": "ignore"})
    storage.record_event(line_number=12, state={"score": 100})

    history = storage.get_variable_history("score")
    assert len(history) == 3
    assert [h["value"] for h in history] == [0, 50, 100]
    assert [h["line_number"] for h in history] == [10, 11, 12]


def test_empty_and_complex_states(storage):
    """Verify handling of empty dict states and circular objects."""
    storage.start_execution("edge_cases.py")

    # Empty state
    ev_empty = storage.record_event(line_number=1, state={})
    assert ev_empty.state == {}

    fetched_empty = storage.get_event(ev_empty.id)
    assert fetched_empty.state == {}

    # Circular reference in state
    lst = [1]
    lst.append(lst)
    ev_circ = storage.record_event(line_number=2, state={"self_ref": lst})
    fetched_circ = storage.get_event(ev_circ.id)
    assert "CircularReference" in str(fetched_circ.state["self_ref"])
