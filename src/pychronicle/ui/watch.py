"""Watch-list filtering for recorded frame variables."""

from typing import Any


def filter_watches(variables: dict[str, Any], watches: set[str]) -> dict[str, Any]:
    if not watches:
        return variables
    return {name: value for name, value in variables.items() if name in watches}