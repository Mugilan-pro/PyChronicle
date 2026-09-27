"""Unit tests for storage data models."""

import pytest
from pychronicle.storage.models import ExecutionRecord, TraceEvent, VariableState


def test_execution_record_defaults():
    record = ExecutionRecord(script_name="sample.py")
    assert record.script_name == "sample.py"
    assert record.started_at > 0
    assert record.completed_at is None
    assert record.metadata == {}
    assert record.id is None


def test_trace_event_creation():
    event = TraceEvent(
        execution_id=1,
        sequence=1,
        line_number=42,
        state={"x": 100, "name": "alice"},
    )
    assert event.execution_id == 1
    assert event.sequence == 1
    assert event.line_number == 42
    assert event.state == {"x": 100, "name": "alice"}
    assert event.function_name == "<module>"
    assert event.event_type == "line"
    assert event.is_delta is False
    assert event.id is None


def test_variable_state_creation():
    var = VariableState(
        var_name="counter",
        serialized_value="10",
        value_type="int",
        event_id=1,
    )
    assert var.var_name == "counter"
    assert var.serialized_value == "10"
    assert var.value_type == "int"
    assert var.event_id == 1
