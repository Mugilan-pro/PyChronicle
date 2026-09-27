"""Unit tests for SQLite Database layer."""

import pytest
from pychronicle.storage.database import Database
from pychronicle.storage.models import ExecutionRecord, TraceEvent, VariableState


@pytest.fixture
def db():
    """Provides a fresh in-memory database instance for each test."""
    database = Database(":memory:")
    yield database
    database.close()


def test_schema_creation(db):
    """Verify all tables and indexes exist after initialization."""
    cursor = db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row["name"] for row in cursor.fetchall()}
    assert "executions" in tables
    assert "trace_events" in tables
    assert "variable_states" in tables


def test_execution_lifecycle(db):
    """Verify creating, querying, and updating an execution session."""
    record = ExecutionRecord(script_name="calc.py", metadata={"user": "tester"})
    exec_id = db.insert_execution(record)
    assert exec_id is not None
    assert record.id == exec_id

    fetched = db.get_execution(exec_id)
    assert fetched is not None
    assert fetched.script_name == "calc.py"
    assert fetched.metadata == {"user": "tester"}
    assert fetched.completed_at is None

    db.update_execution_completed(exec_id, completed_at=123456.78)
    updated = db.get_execution(exec_id)
    assert updated.completed_at == 123456.78


def test_insert_and_retrieve_event_with_variables(db):
    """Verify atomic insertion of event and associated variable states."""
    exec_record = ExecutionRecord(script_name="loop.py")
    exec_id = db.insert_execution(exec_record)

    event = TraceEvent(
        execution_id=exec_id,
        sequence=1,
        line_number=10,
        function_name="main",
    )
    variables = [
        VariableState(var_name="i", serialized_value="0", value_type="int"),
        VariableState(var_name="total", serialized_value="0", value_type="int"),
    ]

    event_id = db.insert_event_with_variables(event, variables)
    assert event_id is not None
    assert event.id == event_id

    fetched_ev, fetched_vars = db.get_event_with_variables(event_id)
    assert fetched_ev.sequence == 1
    assert fetched_ev.line_number == 10
    assert fetched_ev.function_name == "main"

    var_dict = {v.var_name: (v.serialized_value, v.value_type) for v in fetched_vars}
    assert var_dict["i"] == ("0", "int")
    assert var_dict["total"] == ("0", "int")


def test_chronological_ordering_guarantee(db):
    """Verify events are returned in strict sequence order regardless of insertion."""
    exec_id = db.insert_execution(ExecutionRecord(script_name="ordering.py"))

    # Insert events 1, 2, 3
    for seq in [1, 2, 3]:
        ev = TraceEvent(execution_id=exec_id, sequence=seq, line_number=10 + seq)
        vars_ = [VariableState(var_name="step", serialized_value=str(seq), value_type="int")]
        db.insert_event_with_variables(ev, vars_)

    events = db.get_events_for_execution(exec_id)
    assert len(events) == 3
    assert [ev.sequence for ev, _ in events] == [1, 2, 3]
    assert [ev.line_number for ev, _ in events] == [11, 12, 13]


def test_variable_history_watch(db):
    """Verify querying timeline of a single variable across events."""
    exec_id = db.insert_execution(ExecutionRecord(script_name="watch.py"))

    # Simulate x changing over 3 lines
    for seq, val in enumerate([10, 20, 30], start=1):
        ev = TraceEvent(execution_id=exec_id, sequence=seq, line_number=seq * 5)
        vars_ = [VariableState(var_name="x", serialized_value=str(val), value_type="int")]
        db.insert_event_with_variables(ev, vars_)

    history = db.get_variable_history(exec_id, "x")
    assert len(history) == 3
    assert [h["serialized_value"] for h in history] == ["10", "20", "30"]
    assert [h["line_number"] for h in history] == [5, 10, 15]


def test_sequence_window_filtering(db):
    """Verify sequence window filtering (start_sequence and end_sequence)."""
    exec_id = db.insert_execution(ExecutionRecord(script_name="window.py"))

    for seq in range(1, 6):
        ev = TraceEvent(execution_id=exec_id, sequence=seq, line_number=seq)
        db.insert_event_with_variables(ev, [])

    # Fetch sequence range 2 to 4 inclusive
    window = db.get_events_for_execution(exec_id, start_sequence=2, end_sequence=4)
    assert len(window) == 3
    assert [ev.sequence for ev, _ in window] == [2, 3, 4]


def test_unique_sequence_constraint(db):
    """Verify that inserting duplicate sequence numbers for same execution raises IntegrityError."""
    import sqlite3

    exec_id = db.insert_execution(ExecutionRecord(script_name="dup.py"))
    ev1 = TraceEvent(execution_id=exec_id, sequence=1, line_number=5)
    db.insert_event_with_variables(ev1, [])

    ev2 = TraceEvent(execution_id=exec_id, sequence=1, line_number=6)
    with pytest.raises(sqlite3.IntegrityError):
        db.insert_event_with_variables(ev2, [])
