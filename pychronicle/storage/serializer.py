"""Safe Value Serializer for PyChronicle.

Converts arbitrary runtime Python variables into database-safe string
representations and vice versa, with cycle detection and un-serializable
object fallbacks.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Set, Tuple


class SerializationError(Exception):
    """Raised when an object fails serialization unexpectedly."""
    pass


class ValueSerializer:
    """Serializes Python runtime values into storage-safe string formats.
    
    Guarantees:
    - Never crashes the traced program on difficult or unpicklable objects.
    - Detects and handles circular references (e.g., self-referential lists/dicts).
    - Preserves type metadata for display in the TUI.
    - Limits string length to prevent memory exhaustion from huge objects.
    """

    PRIMITIVE_TYPES = (int, float, str, bool, type(None))

    def __init__(self, max_depth: int = 5, max_str_length: int = 1000) -> None:
        """Initialize serializer settings.
        
        Args:
            max_depth: Maximum recursion depth for nested collections.
            max_str_length: Maximum length for serialized strings before truncation.
        """
        self.max_depth = max_depth
        self.max_str_length = max_str_length

    def serialize(self, value: Any) -> Tuple[str, str]:
        """Serialize a Python value into a safe string and its type name.
        
        Args:
            value: Any Python object from local/global scope.
            
        Returns:
            A tuple of (serialized_string, type_name).
        """
        type_name = type(value).__name__

        # Fast path for primitives
        if isinstance(value, self.PRIMITIVE_TYPES):
            payload = json.dumps(value)
            return self._truncate(payload), type_name

        # For collections and complex objects, traverse safely with cycle detection
        seen_ids: Set[int] = set()
        sanitized = self._sanitize(value, depth=0, seen=seen_ids)
        try:
            payload = json.dumps(sanitized, ensure_ascii=False)
        except Exception:
            # Absolute fallback: safe repr
            payload = json.dumps(self._safe_repr(value))

        return self._truncate(payload), type_name

    def deserialize(self, serialized_value: str, value_type: str) -> Any:
        """Deserialize a stored string back into a Python object or representation.
        
        Args:
            serialized_value: The JSON or string representation from the database.
            value_type: The stored type name.
            
        Returns:
            The parsed Python value or string representation.
        """
        try:
            return json.loads(serialized_value)
        except (json.JSONDecodeError, TypeError):
            return serialized_value

    def _sanitize(self, obj: Any, depth: int, seen: Set[int]) -> Any:
        """Recursively sanitize an object into JSON-compatible primitives."""
        # 1. Depth limit guard
        if depth >= self.max_depth:
            return f"<MaxDepthReached: {type(obj).__name__}>"

        # 2. Primitives pass through directly
        if isinstance(obj, self.PRIMITIVE_TYPES):
            return obj

        # 3. Cycle detection for containers
        obj_id = id(obj)
        if obj_id in seen:
            return f"<CircularReference: {type(obj).__name__} id={obj_id}>"

        seen.add(obj_id)

        try:
            # 4. Lists & Tuples
            if isinstance(obj, (list, tuple)):
                result = [self._sanitize(item, depth + 1, seen) for item in obj]
                return result

            # 5. Sets
            if isinstance(obj, set):
                return sorted([self._sanitize(item, depth + 1, seen) for item in obj], key=str)

            # 6. Dictionaries
            if isinstance(obj, dict):
                clean_dict = {}
                for k, v in obj.items():
                    key_str = str(k) if not isinstance(k, str) else k
                    clean_dict[key_str] = self._sanitize(v, depth + 1, seen)
                return clean_dict

            # 7. Functions, methods, modules, types (callables should use safe_repr, not attribute inspection)
            if callable(obj) or isinstance(obj, type) or hasattr(obj, "__file__"):
                return self._safe_repr(obj)

            # 8. Objects with __dict__ (custom user classes/dataclasses)
            if hasattr(obj, "__dict__"):
                clean_attrs = {}
                for k, v in obj.__dict__.items():
                    if not k.startswith("_"):  # Exclude private internals
                        clean_attrs[k] = self._sanitize(v, depth + 1, seen)
                return {"__class__": type(obj).__name__, "attributes": clean_attrs}

            # 9. Un-serializable objects (sockets, open files, locks)
            return self._safe_repr(obj)

        finally:
            seen.remove(obj_id)

    def _safe_repr(self, obj: Any) -> str:
        """Generate a guaranteed safe repr without triggering custom user errors."""
        try:
            r = repr(obj)
            return self._truncate(r)
        except Exception as e:
            return f"<UnrepresentableObject: {type(obj).__name__}>"

    def _truncate(self, text: str) -> str:
        """Truncate overly large strings to prevent database bloat."""
        if len(text) > self.max_str_length:
            return text[: self.max_str_length] + "...[truncated]"
        return text


# Module-level convenience functions
_default_serializer = ValueSerializer()


def serialize(value: Any) -> Tuple[str, str]:
    """Serialize a value using the default ValueSerializer."""
    return _default_serializer.serialize(value)


def deserialize(serialized_value: str, value_type: str) -> Any:
    """Deserialize a value using the default ValueSerializer."""
    return _default_serializer.deserialize(serialized_value, value_type)
