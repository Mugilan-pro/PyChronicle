"""Tests for PyChronicle ExecutionTracer."""

from pathlib import Path
import sys
import pytest

from pychronicle import ExecutionTracer, TraceEvent


def test_simple_assignment(tmp_path: Path):
    target = tmp_path / "test_assign.py"
    target.write_text("x = 10\nx = 20\n", encoding="utf-8")

    tracer = ExecutionTracer(target)
    events = tracer.run()

    line_events = [e for e in events if e.event == "line"]
    assert len(line_events) >= 2

    # Before line 2 runs, x has its initial value 10
    assert line_events[0].line_number == 1
    assert "x" not in line_events[0].locals
    assert line_events[1].line_number == 2
    assert line_events[1].locals.get("x") == 10

    # At module return, x has been updated to 20
    return_event = [e for e in events if e.event == "return"][-1]
    assert return_event.locals.get("x") == 20


def test_loop_execution(tmp_path: Path):
    code = (
        "total = 0\n"
        "for i in range(5):\n"
        "    total += i\n"
        "print(total)\n"
    )
    target = tmp_path / "test_loop.py"
    target.write_text(code, encoding="utf-8")

    tracer = ExecutionTracer(target)
    events = tracer.run()

    # Line 3 (total += i) must be traced across all 5 iterations
    loop_events = [e for e in events if e.event == "line" and e.line_number == 3]
    assert len(loop_events) == 5

    expected_states = [
        {"i": 0, "total": 0},
        {"i": 1, "total": 0},
        {"i": 2, "total": 1},
        {"i": 3, "total": 3},
        {"i": 4, "total": 6},
    ]
    for event, expected in zip(loop_events, expected_states):
        assert event.locals.get("i") == expected["i"]
        assert event.locals.get("total") == expected["total"]

    # Line 4 (print) sees loop completion state
    print_event = next(e for e in events if e.event == "line" and e.line_number == 4)
    assert print_event.locals.get("total") == 10
    assert print_event.locals.get("i") == 4


def test_function_execution(tmp_path: Path):
    code = (
        "def add(a, b):\n"
        "    result = a + b\n"
        "    return result\n"
        "x = add(10, 20)\n"
    )
    target = tmp_path / "test_func.py"
    target.write_text(code, encoding="utf-8")

    tracer = ExecutionTracer(target)
    events = tracer.run()

    call_event = next(e for e in events if e.event == "call" and e.function == "add")
    assert call_event.locals == {"a": 10, "b": 20}

    body_event = next(e for e in events if e.event == "line" and e.function == "add" and e.line_number == 3)
    assert body_event.locals == {"a": 10, "b": 20, "result": 30}

    return_event = next(e for e in events if e.event == "return" and e.function == "add")
    assert return_event.arg == 30

    mod_return = next(e for e in events if e.event == "return" and e.function == "<module>")
    assert mod_return.locals.get("x") == 30


def test_conditional_branching(tmp_path: Path):
    code = (
        "x = 10\n"
        "if x > 5:\n"
        "    y = 100\n"
        "else:\n"
        "    y = 200\n"
    )
    target = tmp_path / "test_cond.py"
    target.write_text(code, encoding="utf-8")

    tracer = ExecutionTracer(target)
    events = tracer.run()

    executed_lines = [e.line_number for e in events if e.event == "line"]
    assert 3 in executed_lines  # y = 100 executed
    assert 5 not in executed_lines  # y = 200 skipped


def test_nested_functions(tmp_path: Path):
    code = (
        "def outer():\n"
        "    x = 10\n"
        "    def inner():\n"
        "        y = 20\n"
        "        return y\n"
        "    return inner()\n"
        "result = outer()\n"
    )
    target = tmp_path / "test_nested.py"
    target.write_text(code, encoding="utf-8")

    tracer = ExecutionTracer(target)
    events = tracer.run()

    inner_return = next(e for e in events if e.event == "return" and e.function == "inner")
    outer_return = next(e for e in events if e.event == "return" and e.function == "outer")
    assert inner_return.arg == 20
    assert outer_return.arg == 20

    mod_return = next(e for e in events if e.event == "return" and e.function == "<module>")
    assert mod_return.locals.get("result") == 20


def test_exception_handling_and_cleanup(tmp_path: Path):
    code = (
        "x = 10\n"
        "raise ValueError('test error')\n"
    )
    target = tmp_path / "test_exc.py"
    target.write_text(code, encoding="utf-8")

    tracer = ExecutionTracer(target)

    # Exception must propagate to caller
    with pytest.raises(ValueError, match="test error"):
        tracer.run()

    # Tracing must be cleanly disabled
    assert sys.gettrace() is None

    # Exception event must be recorded
    exc_event = next(e for e in tracer.events if e.event == "exception")
    assert exc_event.line_number == 2
    assert exc_event.locals.get("x") == 10
    assert exc_event.arg["type"] == "ValueError"


def test_file_filtering(tmp_path: Path):
    code = (
        "import math\n"
        "import json\n"
        "r = math.sqrt(16)\n"
        "data = json.dumps({'a': 1})\n"
    )
    target = tmp_path / "test_filter.py"
    target.write_text(code, encoding="utf-8")

    tracer = ExecutionTracer(target)
    events = tracer.run()

    assert len(events) > 0
    for event in events:
        assert event.filename == target.name


def test_chronological_order(tmp_path: Path):
    code = "a = 1\nb = 2\nc = 3\n"
    target = tmp_path / "test_order.py"
    target.write_text(code, encoding="utf-8")

    tracer = ExecutionTracer(target)
    events = tracer.run()

    line_numbers = [e.line_number for e in events if e.event == "line"]
    assert line_numbers == [1, 2, 3]


def test_mutable_state_snapshots(tmp_path: Path):
    code = (
        "items = []\n"
        "items.append(1)\n"
        "items.append(2)\n"
    )
    target = tmp_path / "test_mutation.py"
    target.write_text(code, encoding="utf-8")

    tracer = ExecutionTracer(target)
    events = tracer.run()

    line_events = [e for e in events if e.event == "line"]
    line2_event = next(e for e in line_events if e.line_number == 2)
    line3_event = next(e for e in line_events if e.line_number == 3)
    mod_return = next(e for e in events if e.event == "return" and e.function == "<module>")

    # Snapshots must reflect state at that exact moment
    assert line2_event.locals.get("items") == []
    assert line3_event.locals.get("items") == [1]
    assert mod_return.locals.get("items") == [1, 2]

    # Past snapshots must not mutate when items is later modified
    assert line2_event.locals["items"] is not line3_event.locals["items"]


def test_target_file_not_found():
    with pytest.raises(FileNotFoundError):
        ExecutionTracer("missing_target.py")


def test_trace_event_to_dict():
    event = TraceEvent(
        event="line",
        line_number=5,
        function="foo",
        filename="bar.py",
        locals={"x": 42},
    )
    data = event.to_dict()
    assert data["event"] == "line"
    assert data["line_number"] == 5
    assert data["locals"] == {"x": 42}
    assert data["arg"] is None
