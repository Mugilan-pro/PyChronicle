"""Unit and integration tests for StateReconstructor and Delta-enabled StorageManager."""

import pytest
from pychronicle.storage.manager import StorageManager


def test_delta_compression_storage_reduction():
    """Verify delta compression stores vastly fewer variable rows than full snapshots."""
    # Run 1: Full snapshots (enable_delta=False)
    storage_full = StorageManager(":memory:", enable_delta=False)
    exec_full = storage_full.start_execution("full.py")

    # 10 steps, each step has 5 static variables and 1 changing variable
    for i in range(1, 11):
        storage_full.record_event(
            line_number=i,
            state={"v1": 1, "v2": 2, "v3": 3, "v4": 4, "v5": 5, "changing": i},
        )
    storage_full.finish_execution(exec_full)

    cursor_full = storage_full.db.conn.execute("SELECT COUNT(*) FROM variable_states")
    count_full = cursor_full.fetchone()[0]
    # 10 steps * 6 variables = 60 rows
    assert count_full == 60
    storage_full.close()

    # Run 2: Delta compression (enable_delta=True, checkpoint_interval=50)
    storage_delta = StorageManager(":memory:", enable_delta=True, checkpoint_interval=50)
    exec_delta = storage_delta.start_execution("delta.py")

    for i in range(1, 11):
        storage_delta.record_event(
            line_number=i,
            state={"v1": 1, "v2": 2, "v3": 3, "v4": 4, "v5": 5, "changing": i},
        )
    storage_delta.finish_execution(exec_delta)

    cursor_delta = storage_delta.db.conn.execute("SELECT COUNT(*) FROM variable_states")
    count_delta = cursor_delta.fetchone()[0]
    # Step 1: full snapshot (6 vars)
    # Steps 2-10: only "changing" variable stored (9 vars)
    # Total: 6 + 9 = 15 rows instead of 60! (75% savings on just 10 steps, >90% on larger runs)
    assert count_delta == 15
    assert count_delta < count_full

    storage_delta.close()


def test_state_reconstruction_accuracy():
    """Verify that reconstructed states match the ground truth full state at every step."""
    storage = StorageManager(":memory:", enable_delta=True, checkpoint_interval=4)
    exec_id = storage.start_execution("calc.py")

    expected_states = [
        {"a": 10, "b": 20},              # step 1: initial (snapshot)
        {"a": 15, "b": 20},              # step 2: a modified
        {"a": 15, "b": 25, "c": 30},     # step 3: b modified, c added
        {"a": 15, "b": 25, "c": 30},     # step 4: no changes (checkpoint snapshot)
        {"a": 100, "b": 25, "c": 30},    # step 5: a modified
    ]

    for idx, expected in enumerate(expected_states, start=1):
        storage.record_event(line_number=10 + idx, state=expected)

    storage.finish_execution(exec_id)

    # 1. Test random-access reconstruction at each sequence step
    for seq, expected in enumerate(expected_states, start=1):
        reconstructed = storage.reconstruct_state(sequence=seq, execution_id=exec_id)
        assert reconstructed == expected, f"Mismatch at step {seq}"

    # 2. Test get_events() hydration
    events = storage.get_events(exec_id)
    assert len(events) == len(expected_states)
    for ev, expected in zip(events, expected_states):
        assert ev.state == expected

    storage.close()


def test_reconstruct_single_event():
    """Verify get_event() on a delta event reconstructs the full state."""
    storage = StorageManager(":memory:", enable_delta=True, checkpoint_interval=10)
    storage.start_execution("single.py")

    ev1 = storage.record_event(line_number=1, state={"x": 1, "y": 2})
    ev2 = storage.record_event(line_number=2, state={"x": 10, "y": 2})  # Delta step

    assert ev2.is_delta is True

    fetched_ev2 = storage.get_event(ev2.id)
    assert fetched_ev2 is not None
    assert fetched_ev2.state == {"x": 10, "y": 2}

    storage.close()
