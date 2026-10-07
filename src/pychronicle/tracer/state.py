"""Helpers for comparing locals between trace callbacks."""

from __future__ import annotations

from typing import Any

from pychronicle.storage.database import serialize_value


def local_changes(
    previous: dict[str, str], current: dict[str, Any]
) -> tuple[dict[str, Any], set[str], dict[str, str]]:
    fingerprints = {name: serialize_value(value) for name, value in current.items()}
    changes = {
        name: value
        for name, value in current.items()
        if name not in previous or previous[name] != fingerprints[name]
    }
    removed = previous.keys() - current.keys()
    return changes, set(removed), fingerprints