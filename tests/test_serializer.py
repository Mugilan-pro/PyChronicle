"""Unit tests for the safe ValueSerializer."""

import pytest
from pychronicle.storage.serializer import ValueSerializer, deserialize, serialize


def test_serialize_primitives():
    """Verify primitives serialize to JSON strings with accurate type names."""
    cases = [
        (42, "42", "int"),
        (3.14, "3.14", "float"),
        ("hello world", '"hello world"', "str"),
        (True, "true", "bool"),
        (None, "null", "NoneType"),
    ]
    for val, expected_json, expected_type in cases:
        payload, type_name = serialize(val)
        assert payload == expected_json
        assert type_name == expected_type
        assert deserialize(payload, type_name) == val


def test_serialize_nested_collections():
    """Verify lists, dicts, tuples, and sets serialize correctly."""
    data = {
        "numbers": [1, 2, 3],
        "coords": (10, 20),
        "tags": {"python", "debugger"},
        "nested": {"score": 99.5},
    }
    payload, type_name = serialize(data)
    assert type_name == "dict"
    restored = deserialize(payload, type_name)
    assert restored["numbers"] == [1, 2, 3]
    assert restored["coords"] == [10, 20]
    assert sorted(restored["tags"]) == ["debugger", "python"]
    assert restored["nested"]["score"] == 99.5


def test_circular_reference_handling():
    """Verify self-referencing data structures do not trigger infinite recursion."""
    a = [1, 2]
    a.append(a)  # Circular list: [1, 2, [...]]

    # Must NOT raise RecursionError
    payload, type_name = serialize(a)
    assert type_name == "list"
    assert "CircularReference" in payload

    # Self-referencing dict
    d = {"key": "val"}
    d["self"] = d
    payload_d, type_name_d = serialize(d)
    assert type_name_d == "dict"
    assert "CircularReference" in payload_d


def test_custom_user_object():
    """Verify custom class instances serialize their public attributes."""
    class User:
        def __init__(self, name: str, age: int):
            self.name = name
            self.age = age
            self._secret = "hidden"

    u = User("Alice", 30)
    payload, type_name = serialize(u)
    assert type_name == "User"
    restored = deserialize(payload, type_name)
    assert restored["__class__"] == "User"
    assert restored["attributes"]["name"] == "Alice"
    assert restored["attributes"]["age"] == 30
    assert "_secret" not in restored["attributes"]


def test_unserializable_objects_fallback():
    """Verify functions, modules, and open file handles don't crash."""
    def sample_func(x):
        return x + 1

    payload, type_name = serialize(sample_func)
    assert type_name == "function"
    assert "sample_func" in payload

    # Test open file object
    import tempfile
    with tempfile.TemporaryFile("w+") as f:
        payload_f, type_name_f = serialize(f)
        assert "Unrepresentable" not in payload_f or "File" in payload_f


def test_string_truncation():
    """Verify overly large strings are truncated cleanly."""
    serializer = ValueSerializer(max_str_length=50)
    huge_string = "A" * 200
    payload, type_name = serializer.serialize(huge_string)
    assert len(payload) <= 70  # 50 chars + truncation note
    assert "...[truncated]" in payload
