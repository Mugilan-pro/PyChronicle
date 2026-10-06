"""Mid-Project Review Validation Tests for PyChronicle.

Directly verifies the requirement from PROJECT.pdf:
"Trace Validation: Prove the tracer accurately records the execution of a
complex loop without dropping frames."
"""

import pytest
from pychronicle.runner import PyChronicleRunner
from pychronicle.storage import StorageManager
from pychronicle.tracer import ExecutionTracer, TraceFilter


def test_complex_nested_loop_zero_dropped_frames():
    """Validates that a complex nested loop records 100% of frames with 0 drops."""
    storage = StorageManager(":memory:")
    storage.start_execution("nested_loop.py")

    tracer = ExecutionTracer(
        storage=storage,
        trace_filter=TraceFilter(target_files=["nested_loop.py"]),
    )

    code = """
total = 0
for i in range(4):
    for j in range(3):
        if (i + j) % 2 == 0:
            total += (i * 10 + j)
        else:
            total -= 1
"""
    recorded = tracer.run_code(code, filename="nested_loop.py")
    assert tracer.dropped_frames == 0
    assert recorded > 0

    events = storage.get_events()
    assert len(events) == recorded

    # Verify monotonic sequence [1..N]
    seqs = [ev.sequence for ev in events]
    assert seqs == list(range(1, len(events) + 1))

    # Verify final state mathematically
    expected_total = 0
    for i in range(4):
        for j in range(3):
            if (i + j) % 2 == 0:
                expected_total += (i * 10 + j)
            else:
                expected_total -= 1

    final_state = events[-1].state
    assert final_state.get("total") == expected_total


def test_recursive_function_frames():
    """Validates that recursion depth and frames are fully recorded without corruption."""
    storage = StorageManager(":memory:")
    storage.start_execution("recursion.py")

    tracer = ExecutionTracer(
        storage=storage,
        trace_filter=TraceFilter(target_files=["recursion.py"]),
    )

    code = """
def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)

res = fact(5)
"""
    tracer.run_code(code, filename="recursion.py")
    assert tracer.dropped_frames == 0

    events = storage.get_events()
    final_event = events[-1]
    assert final_event.state.get("res") == 120

    # Ensure calls and returns match recursion depth
    calls = [e for e in events if e.event_type == "call" and e.function_name == "fact"]
    returns = [e for e in events if e.event_type == "return" and e.function_name == "fact"]
    assert len(calls) == 5
    assert len(returns) == 5


def test_runner_dual_modes():
    """Validates PyChronicleRunner in both tracer and rewriter modes."""
    code = """
x = 10
y = 20
z = x + y
"""
    # 1. Tracer mode
    with PyChronicleRunner(db_path=":memory:") as runner_t:
        exec_id = runner_t.run_code(code, filename="mode_test.py", mode="tracer")
        timeline = runner_t.get_timeline(exec_id)
        assert len(timeline) >= 3
        final_state = timeline[-1].state
        assert final_state.get("z") == 30

    # 2. Rewriter mode
    with PyChronicleRunner(db_path=":memory:") as runner_r:
        exec_id2 = runner_r.run_code(code, filename="mode_test.py", mode="rewriter")
        timeline2 = runner_r.get_timeline(exec_id2)
        assert len(timeline2) >= 3
        final_state2 = timeline2[-1].state
        assert final_state2.get("z") == 30


def test_variable_watchpoint_history():
    """Validates variable history querying for TUI scrubbers."""
    runner = PyChronicleRunner(db_path=":memory:")
    code = """
acc = 10
acc = 20
acc = 30
"""
    runner.run_code(code, filename="watch.py", mode="tracer")
    history = runner.watch_variable("acc")
    assert len(history) >= 3
    values = [h["value"] for h in history]
    assert 10 in values
    assert 20 in values
    assert 30 in values
    runner.close()
