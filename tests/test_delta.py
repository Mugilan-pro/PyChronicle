"""Unit tests for DeltaCalculator and StateDelta."""

import pytest
from pychronicle.storage.delta import DeltaCalculator, StateDelta
from pychronicle.storage.serializer import ValueSerializer


def test_delta_detects_additions_and_modifications():
    """Verify DeltaCalculator detects new variables and changed values."""
    calc = DeltaCalculator()
    serializer = ValueSerializer()

    # Previous state: x=10, y="hello"
    prev_serialized = {
        "x": serializer.serialize(10),
        "y": serializer.serialize("hello"),
    }

    # Current state: x=10 (unchanged), y="world" (modified), z=[1, 2] (added)
    curr_state = {
        "x": 10,
        "y": "world",
        "z": [1, 2],
    }

    delta, new_serialized = calc.compute_diff(prev_serialized, curr_state)

    # x should NOT be in mutations because it did not change
    assert "x" not in delta.mutations
    # y and z should be in mutations
    assert delta.mutations["y"] == "world"
    assert delta.mutations["z"] == [1, 2]
    assert delta.deletions == []
    assert not delta.is_empty


def test_delta_detects_deletions():
    """Verify variables dropped from scope are captured in deletions."""
    calc = DeltaCalculator()
    serializer = ValueSerializer()

    prev_serialized = {
        "temp_var": serializer.serialize(999),
        "persistent_var": serializer.serialize(100),
    }

    curr_state = {
        "persistent_var": 100,
    }

    delta, _ = calc.compute_diff(prev_serialized, curr_state)
    assert delta.mutations == {}
    assert delta.deletions == ["temp_var"]
    assert not delta.is_empty


def test_delta_is_empty_when_no_changes():
    """Verify delta.is_empty is True when state is completely identical."""
    calc = DeltaCalculator()
    serializer = ValueSerializer()

    prev_serialized = {"a": serializer.serialize(1)}
    curr_state = {"a": 1}

    delta, _ = calc.compute_diff(prev_serialized, curr_state)
    assert delta.is_empty


def test_state_delta_apply_to():
    """Verify StateDelta.apply_to correctly mutates and deletes keys."""
    base_state = {"a": 1, "b": 2, "c": 3}
    delta = StateDelta(
        mutations={"b": 20, "d": 4},
        deletions=["a"],
    )

    updated = delta.apply_to(base_state)
    assert updated == {"b": 20, "c": 3, "d": 4}
    # Verify original base_state was not modified in-place
    assert base_state == {"a": 1, "b": 2, "c": 3}
