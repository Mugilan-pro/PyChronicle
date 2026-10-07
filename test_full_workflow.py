"""End-to-End integration tests for complete 4-week workflow."""

import pytest
from pychronicle.runner import PyChronicleRunner
from pychronicle.storage.delta import DeltaCompressor


def test_end_to_end_full_workflow_with_delta_compression():
    """Verify complete Weeks 1-4 pipeline: AST parsing, tracing, delta compression, and watchpoint."""
    code = """
def compute_factorials(limit):
    results = {}
    current = 1
    for i in range(1, limit + 1):
        current *= i
        results[i] = current
    return results

data = compute_factorials(4)
total = sum(data.values())
"""
    runner = PyChronicleRunner(":memory:", delta_mode=True, checkpoint_interval=5)
    exec_id = runner.run_code(code, filename="factorial_pipeline.py")

    assert exec_id is not None
    assert runner.last_exception is None

    # Week 1: AST Analysis verified
    assert "current" in runner.last_analysis.all_variables
    assert "results" in runner.last_analysis.all_variables
    assert "total" in runner.last_analysis.all_variables

    # Week 2 & 3: Execution timeline & delta compression verified
    timeline = runner.get_timeline()
    assert len(timeline) > 10

    stats = runner.get_storage_stats()
    assert stats["delta_events"] > 0
    assert stats["keyframe_events"] > 0

    # Verify that final frame accurately holds total = 1 + 2 + 6 + 24 = 33
    final_event = timeline[-1]
    assert final_event.state.get("total") == 33

    # Week 4: Watch Variable verified
    current_history = runner.watch_variable("current")
    distinct_values = []
    for h in current_history:
        v = h["value"]
        if not distinct_values or distinct_values[-1] != v:
            distinct_values.append(v)
    numerical_values = [v for v in distinct_values if v != "<DELETED>"]
    assert numerical_values == [1, 2, 6, 24]


def test_post_mortem_crash_time_travel():
    """Verify that when a target script crashes, PyChronicle captures execution history

    allowing developers to time-travel backward to observe the variable state prior to the crash.
    """
    faulty_code = """
def divide_items(numerator, denominator):
    return numerator // denominator

items = [100, 50, 0]
results = []
for val in items:
    res = divide_items(1000, val)
    results.append(res)
"""
    runner = PyChronicleRunner(":memory:", delta_mode=True)
    exec_id = runner.run_code(faulty_code, filename="crash_app.py")

    # Verify that crash was caught and stored
    assert runner.last_exception is not None
    assert isinstance(runner.last_exception, ZeroDivisionError)

    # Timeline captured all pre-crash steps
    timeline = runner.get_timeline()
    assert len(timeline) > 5

    # Find the crash event
    crash_event = timeline[-1]
    assert crash_event.event_type == "exception"
    assert "ZeroDivisionError" in crash_event.state.get("__exception__", "")

    # Time-travel backward to the frame just before the crash:
    # Notice that val was 0 right before the crash!
    pre_crash_event = timeline[-2]
    val_history = runner.watch_variable("val")
    assert any(h["value"] == 0 for h in val_history)
