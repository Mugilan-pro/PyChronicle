"""Unit and integration tests for Week 3 Delta Compression Engine."""

import pytest
from pychronicle.storage.delta import DeltaCompressor, FrameDelta, VariableDelta
from pychronicle.storage.manager import StorageManager


def test_delta_computation_added_modified_deleted():
    compressor = DeltaCompressor(checkpoint_interval=10)

    state_0 = {"a": 1, "b": "hello", "c": [1, 2, 3]}
    state_1 = {"a": 2, "b": "hello", "d": True}  # 'a' modified, 'c' deleted, 'd' added

    delta = compressor.compute_frame_delta(state_0, state_1, sequence=2, line_number=10)

    assert delta.sequence == 2
    assert delta.line_number == 10
    assert delta.added == {"d": True}
    assert delta.modified == {"a": 2}
    assert delta.deleted == ["c"]
    assert delta.has_changes is True
    assert delta.mutation_count == 3


def test_delta_application_forward():
    compressor = DeltaCompressor()

    base_state = {"x": 10, "y": 20, "z": 30}
    delta = FrameDelta(
        sequence=3,
        line_number=15,
        added={"new_var": 99},
        modified={"x": 11},
        deleted=["z"],
    )

    reconstructed = compressor.apply_delta(base_state, delta)
    assert reconstructed == {
        "x": 11,
        "y": 20,
        "new_var": 99,
    }
    assert "z" not in reconstructed


def test_delta_timeline_reconstruction():
    compressor = DeltaCompressor(checkpoint_interval=5)

    # Simulated ground truth states across 7 steps
    ground_truth = [
        {"i": 0, "total": 0, "config": "A"},       # Step 1: Checkpoint
        {"i": 1, "total": 10, "config": "A"},      # Step 2: Delta
        {"i": 2, "total": 30, "config": "A"},      # Step 3: Delta
        {"i": 3, "total": 60, "config": "B"},      # Step 4: Delta
        {"i": 4, "total": 100, "config": "B"},     # Step 5: Checkpoint
        {"i": 5, "total": 150, "config": "B"},     # Step 6: Delta
        {"i": 6, "total": 210, "config": "B", "done": True},  # Step 7: Delta
    ]

    storage = StorageManager(":memory:", delta_mode=True, checkpoint_interval=5)
    storage.start_execution("test_delta_loop.py")

    for idx, state in enumerate(ground_truth, start=1):
        storage.record_event(line_number=idx * 2, state=state)

    storage.finish_execution()

    events = storage.get_events()
    assert len(events) == 7

    # Validate that every single event has its full, accurate state reconstructed
    for idx, (ev, expected) in enumerate(zip(events, ground_truth)):
        assert ev.state == expected, f"State mismatch at step {idx + 1}"

    # Verify that sequence 1 and sequence 5 are checkpoints (is_delta == False)
    assert events[0].is_delta is False
    assert events[4].is_delta is False
    # Verify that sequence 2, 3, 4, 6, 7 are deltas (is_delta == True)
    assert events[1].is_delta is True
    assert events[2].is_delta is True
    assert events[3].is_delta is True
    assert events[5].is_delta is True
    assert events[6].is_delta is True


def test_delta_compression_storage_reduction():
    """Verify that delta compression achieves massive reduction on wide scopes."""
    wide_scope = {f"var_{k}": k * 100 for k in range(20)}

    # Run 1: Full-state mode
    full_storage = StorageManager(":memory:", delta_mode=False)
    full_storage.start_execution("wide_loop.py")
    current = dict(wide_scope)
    for i in range(1, 101):
        current["counter"] = i
        full_storage.record_event(line_number=5, state=current)
    full_storage.finish_execution()
    full_stats = full_storage.get_storage_stats()

    # Run 2: Delta-compressed mode (checkpoint every 50 frames)
    delta_storage = StorageManager(":memory:", delta_mode=True, checkpoint_interval=50)
    delta_storage.start_execution("wide_loop.py")
    current = dict(wide_scope)
    for i in range(1, 101):
        current["counter"] = i
        delta_storage.record_event(line_number=5, state=current)
    delta_storage.finish_execution()
    delta_stats = delta_storage.get_storage_stats()

    # In full mode: 100 events * 21 vars = ~2,100 variable rows
    # In delta mode: 2 checkpoints (2 * 21 = 42) + 98 deltas (98 * 1 = 98) = 140 variable rows
    full_rows = full_stats["total_variable_rows"]
    delta_rows = delta_stats["total_variable_rows"]

    reduction = (full_rows - delta_rows) / full_rows
    assert reduction > 0.85, f"Expected >85% storage reduction, achieved {reduction:.2%}"


def test_get_state_at_arbitrary_sequence():
    storage = StorageManager(":memory:", delta_mode=True, checkpoint_interval=10)
    storage.start_execution("seek_test.py")

    for i in range(1, 31):
        storage.record_event(line_number=i, state={"step": i, "acc": i * 10})

    storage.finish_execution()

    # Seek directly to sequence 17 without linear iteration
    state_17 = storage.get_state_at(17)
    assert state_17 == {"step": 17, "acc": 170}

    state_5 = storage.get_state_at(5)
    assert state_5 == {"step": 5, "acc": 50}

    state_29 = storage.get_state_at(29)
    assert state_29 == {"step": 29, "acc": 290}


def test_delta_variable_history():
    storage = StorageManager(":memory:", delta_mode=True, checkpoint_interval=50)
    storage.start_execution("history_test.py")

    storage.record_event(line_number=1, state={"x": 10, "y": 100})
    storage.record_event(line_number=2, state={"x": 20, "y": 100})
    storage.record_event(line_number=3, state={"x": 20, "y": 200})
    storage.record_event(line_number=4, state={"x": 30, "y": 200})
    storage.finish_execution()

    x_history = storage.get_variable_history("x")
    # x was mutated at line 1 (10), line 2 (20), and line 4 (30)
    values = [h["value"] for h in x_history]
    assert values == [10, 20, 30]
