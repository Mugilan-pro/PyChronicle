"""SQLite schema and low-level persistence operations."""

from __future__ import annotations

import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

from pychronicle.storage.models import TraceEvent


def serialize_value(value: Any) -> str:
    """Serialize built-in containers and values without calling user repr methods."""
    def safe_value(item: Any, active: set[int]) -> Any:
        item_type = type(item)
        if item is None or item_type in (bool, int, str):
            return item
        if item_type is float:
            return item if math.isfinite(item) else {"__type__": "float", "__value__": str(item)}
        if item_type in (list, tuple, dict, set, frozenset):
            identity = id(item)
            if identity in active:
                return {"__type__": "cycle", "container": item_type.__name__}
            active.add(identity)
            try:
                if item_type in (list, tuple):
                    return [safe_value(value, active) for value in item]
                if item_type is dict and all(type(key) is str for key in item):
                    return {key: safe_value(value, active) for key, value in item.items()}
                if item_type is dict:
                    return {
                        "__type__": "dict",
                        "__items__": [
                            [safe_value(key, active), safe_value(value, active)]
                            for key, value in item.items()
                        ],
                    }
                values = [safe_value(value, active) for value in item]
                values.sort(key=lambda value: json.dumps(value, sort_keys=True, default=str))
                return {"__type__": item_type.__name__, "__items__": values}
            finally:
                active.remove(identity)
        try:
            representation = object.__repr__(item)
        except Exception as error:
            representation = f"<representation unavailable: {type(error).__name__}>"
        return {"__type__": item_type.__name__, "__repr__": representation}

    try:
        return json.dumps(
            safe_value(value, set()),
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError):
        return json.dumps({"__type__": type(value).__name__, "__repr__": object.__repr__(value)})


def deserialize_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


class SQLiteStore:
    """Persist ordered trace events and only the variable deltas per line."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY,
                target TEXT NOT NULL,
                started_at REAL NOT NULL,
                finished_at REAL,
                status TEXT NOT NULL DEFAULT 'running',
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                sequence INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                filename TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                function_name TEXT NOT NULL,
                frame_id INTEGER NOT NULL,
                UNIQUE(run_id, sequence)
            );
            CREATE INDEX IF NOT EXISTS events_run_sequence ON events(run_id, sequence);
            CREATE TABLE IF NOT EXISTS deltas (
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                variable_name TEXT NOT NULL,
                serialized_value TEXT,
                deleted INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(event_id, variable_name)
            );
            """
        )
        self.connection.commit()

    def create_run(self, target: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO runs(target, started_at) VALUES (?, ?)", (target, time.time())
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def finish_run(self, run_id: int, status: str, error: str | None = None) -> None:
        if status not in {"completed", "failed", "interrupted"}:
            raise ValueError(f"Unsupported run status: {status}")
        self.connection.execute(
            "UPDATE runs SET finished_at = ?, status = ?, error = ? WHERE id = ?",
            (time.time(), status, error, run_id),
        )
        self.connection.commit()

    def record_event(
        self,
        *,
        run_id: int,
        sequence: int,
        filename: str,
        line_number: int,
        function_name: str,
        frame_id: int,
        changes: dict[str, Any],
        deleted: set[str] | None = None,
        timestamp: float | None = None,
    ) -> int:
        removed = deleted or set()
        with self.connection:
            cursor = self.connection.execute(
                """INSERT INTO events
                   (run_id, sequence, timestamp, filename, line_number, function_name, frame_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    sequence,
                    time.time() if timestamp is None else timestamp,
                    filename,
                    line_number,
                    function_name,
                    frame_id,
                ),
            )
            event_id = int(cursor.lastrowid)
            self.connection.executemany(
                """INSERT INTO deltas(event_id, variable_name, serialized_value, deleted)
                   VALUES (?, ?, ?, 0)""",
                [
                    (event_id, name, serialize_value(value))
                    for name, value in changes.items()
                    if name not in removed
                ],
            )
            self.connection.executemany(
                """INSERT INTO deltas(event_id, variable_name, serialized_value, deleted)
                   VALUES (?, ?, NULL, 1)""",
                [(event_id, name) for name in removed],
            )
        return event_id

    def run_ids(self) -> list[int]:
        rows = self.connection.execute("SELECT id FROM runs ORDER BY id").fetchall()
        return [int(row["id"]) for row in rows]

    def events(self, run_id: int | None = None) -> list[TraceEvent]:
        if run_id is None:
            row = self.connection.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1").fetchone()
            if row is None:
                return []
            run_id = int(row["id"])
        rows = self.connection.execute(
            """SELECT id, run_id, sequence, timestamp, filename, line_number,
                      function_name, frame_id
               FROM events WHERE run_id = ? ORDER BY sequence""",
            (run_id,),
        ).fetchall()
        result: list[TraceEvent] = []
        for row in rows:
            delta_rows = self.connection.execute(
                "SELECT variable_name, serialized_value, deleted FROM deltas WHERE event_id = ?",
                (row["id"],),
            ).fetchall()
            changes = {
                str(delta["variable_name"]): (
                    {"__deleted__": True}
                    if delta["deleted"]
                    else deserialize_value(str(delta["serialized_value"]))
                )
                for delta in delta_rows
            }
            result.append(
                TraceEvent(
                    id=int(row["id"]),
                    run_id=int(row["run_id"]),
                    sequence=int(row["sequence"]),
                    timestamp=float(row["timestamp"]),
                    filename=str(row["filename"]),
                    line_number=int(row["line_number"]),
                    function_name=str(row["function_name"]),
                    frame_id=int(row["frame_id"]),
                    changes=changes,
                )
            )
        return result

    def state_at(self, event_id: int, frame_id: int | None = None) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT run_id, sequence, frame_id FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown trace event: {event_id}")
        selected_frame = int(row["frame_id"]) if frame_id is None else frame_id
        state: dict[str, Any] = {}
        deltas = self.connection.execute(
            """SELECT d.variable_name, d.serialized_value, d.deleted
               FROM events e JOIN deltas d ON d.event_id = e.id
               WHERE e.run_id = ? AND e.frame_id = ? AND e.sequence <= ?
               ORDER BY e.sequence""",
            (row["run_id"], selected_frame, row["sequence"]),
        )
        for delta in deltas:
            name = str(delta["variable_name"])
            if delta["deleted"]:
                state.pop(name, None)
            else:
                state[name] = deserialize_value(str(delta["serialized_value"]))
        return state

    def run_info(self, run_id: int) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown trace run: {run_id}")
        return dict(row)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> SQLiteStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()