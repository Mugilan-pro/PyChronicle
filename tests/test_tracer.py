"""Unit tests for PyChronicle ExecutionTracer (Week 2 Core Engineering)."""

import pytest
from pychronicle.storage import StorageManager
from pychronicle.tracer.engine import ExecutionTracer
from pychronicle.tracer.filter import TraceFilter


def test_tracer_records_simple_script():
    storage = StorageManager(":memory:")
    storage.start_execution("test_simple.py")

    tracer = ExecutionTracer(
        storage=storage,
        trace_filter=TraceFilter(target_files=["test_simple.py"]),
    )

    code = """
a = 10
b = 20
c = a + b
"""
    recorded = tracer.run_code(code, filename="test_simple.py")
    assert recorded >= 3
    assert tracer.dropped_frames == 0

    events = storage.get_events()
    assert len(events) >= 3

    # Check last state
    final_event = events[-1]
    assert final_event.state.get("a") == 10
    assert final_event.state.get("b") == 20
    assert final_event.state.get("c") == 30


def test_tracer_captures_function_calls_and_returns():
    storage = StorageManager(":memory:")
    storage.start_execution("test_func.py")

    tracer = ExecutionTracer(
        storage=storage,
        trace_filter=TraceFilter(target_files=["test_func.py"]),
    )

    code = """
def add(x, y):
    return x + y

val = add(3, 7)
"""
    tracer.run_code(code, filename="test_func.py")
    events = storage.get_events()

    event_types = [ev.event_type for ev in events]
    assert "call" in event_types
    assert "return" in event_types
    assert "line" in event_types

    # Find the return event
    ret_events = [ev for ev in events if ev.event_type == "return" and ev.function_name == "add"]
    assert len(ret_events) == 1
    assert ret_events[0].state.get("__return__") == 10


def test_tracer_captures_exceptions():
    storage = StorageManager(":memory:")
    storage.start_execution("test_exc.py")

    tracer = ExecutionTracer(
        storage=storage,
        trace_filter=TraceFilter(target_files=["test_exc.py"]),
    )

    code = """
try:
    x = 1 / 0
except ZeroDivisionError:
    handled = True
"""
    tracer.run_code(code, filename="test_exc.py")
    events = storage.get_events()

    exc_events = [ev for ev in events if ev.event_type == "exception"]
    assert len(exc_events) >= 1
    assert "ZeroDivisionError" in exc_events[0].state.get("__exception__", "")


def test_tracer_filters_dunders():
    storage = StorageManager(":memory:")
    storage.start_execution("test_dunder.py")

    tracer = ExecutionTracer(
        storage=storage,
        trace_filter=TraceFilter(target_files=["test_dunder.py"]),
        filter_dunders=True,
    )

    code = """
my_var = "clean"
"""
    tracer.run_code(code, filename="test_dunder.py")
    events = storage.get_events()
    for ev in events:
        for k in ev.state.keys():
            assert not k.startswith("__builtins__")
            assert not k.startswith("__doc__")
