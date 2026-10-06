from pathlib import Path

import pytest

from pychronicle.storage.database import SQLiteStore
from pychronicle.tracer.engine import run_script


def test_tracer_records_loop_iterations_and_mutable_container_changes(tmp_path) -> None:
    script = tmp_path / "loop_target.py"
    database = tmp_path / "trace.sqlite3"
    script.write_text(
        "values = []\n"
        "for number in range(3):\n"
        "    values.append(number)\n"
        "total = sum(values)\n",
        encoding="utf-8",
    )

    store = run_script(script, database=database)
    try:
        events = store.events()
        value_changes = [event for event in events if "values" in event.changes]
        assert len(events) >= 10
        assert [event.changes["values"] for event in value_changes] == [
            [],
            [0],
            [0, 1],
            [0, 1, 2],
        ]
        assert value_changes[1].line_number == 3
        assert any(event.changes.get("total") == 3 for event in events)
    finally:
        store.close()


def test_tracer_scopes_locals_to_call_frames_and_forwards_argv(tmp_path) -> None:
    script = tmp_path / "nested_target.py"
    script.write_text(
        "import sys\n"
        "def twice(value):\n"
        "    result = value * 2\n"
        "    return result\n"
        "answer = twice(int(sys.argv[1]))\n",
        encoding="utf-8",
    )
    store = run_script(script, ["21"])
    try:
        events = store.events()
        function_events = [event for event in events if event.function_name == "twice"]
        module_events = [event for event in events if event.function_name == "<module>"]
        assert function_events and module_events
        assert function_events[0].frame_id != module_events[0].frame_id
        assert any(event.changes.get("answer") == 42 for event in module_events)
    finally:
        store.close()


def test_tracer_records_global_mutations_from_function_frames(tmp_path) -> None:
    script = tmp_path / "global_target.py"
    script.write_text(
        "counter = 0\n"
        "def increment():\n"
        "    global counter\n"
        "    counter += 1\n"
        "increment()\n",
        encoding="utf-8",
    )

    store = run_script(script)
    try:
        function_events = [event for event in store.events() if event.function_name == "increment"]
        assert any(event.changes.get("global:counter") == 1 for event in function_events)
        changed = next(
            event
            for event in function_events
            if event.changes.get("global:counter") == 1
        )
        assert store.state_at(changed.id, changed.frame_id)["global:counter"] == 1
    finally:
        store.close()


def test_failed_run_is_persisted_and_exception_is_not_hidden(tmp_path) -> None:
    script = tmp_path / "failure_target.py"
    database = tmp_path / "failed.sqlite3"
    script.write_text("before_error = 1\nraise RuntimeError('expected')\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="expected"):
        run_script(script, database=database)

    with SQLiteStore(database) as store:
        run_id = store.run_ids()[0]
        assert store.run_info(run_id)["status"] == "failed"
        assert "RuntimeError: expected" in store.run_info(run_id)["error"]
        assert store.events(run_id)