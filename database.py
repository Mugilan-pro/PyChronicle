"""SQLite Database management for PyChronicle.

Handles raw database connections, schema initialization, parameterized SQL
execution, and atomic transactions.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from pychronicle.storage.models import ExecutionRecord, TraceEvent, VariableState


class Database:
    """Manages the SQLite connection and schema for execution traces.
    
    Supports both file-based databases (for persistent debugging sessions)
    and in-memory databases (':memory:') for ephemeral tracing and fast unit tests.
    """

    SCHEMA = """
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        script_name TEXT NOT NULL,
        started_at REAL NOT NULL,
        completed_at REAL,
        metadata_json TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS trace_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        execution_id INTEGER NOT NULL,
        sequence INTEGER NOT NULL,
        line_number INTEGER NOT NULL,
        function_name TEXT NOT NULL DEFAULT '<module>',
        event_type TEXT NOT NULL DEFAULT 'line',
        timestamp REAL NOT NULL,
        is_delta INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE,
        UNIQUE(execution_id, sequence)
    );

    CREATE TABLE IF NOT EXISTS variable_states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        var_name TEXT NOT NULL,
        serialized_value TEXT NOT NULL,
        value_type TEXT NOT NULL DEFAULT 'unknown',
        FOREIGN KEY (event_id) REFERENCES trace_events(id) ON DELETE CASCADE
    );

    -- Indices for high-speed chronological navigation and variable queries
    CREATE INDEX IF NOT EXISTS idx_events_exec_seq 
        ON trace_events(execution_id, sequence);

    CREATE INDEX IF NOT EXISTS idx_var_states_event 
        ON variable_states(event_id);

    CREATE INDEX IF NOT EXISTS idx_var_states_name 
        ON variable_states(var_name);
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        """Initialize database connection.
        
        Args:
            db_path: Filepath to SQLite database or ':memory:' for in-memory.
        """
        self.db_path = db_path
        # check_same_thread=False allows sharing in-memory connections safely across tracer threads if needed
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return dict-like rows for readability
        self._configure_connection()
        self.create_tables()

    def _configure_connection(self) -> None:
        """Enable foreign keys and Write-Ahead Logging (WAL) for performance."""
        self.conn.execute("PRAGMA foreign_keys = ON;")
        if self.db_path != ":memory:":
            # WAL mode allows concurrent readers without blocking writers
            self.conn.execute("PRAGMA journal_mode = WAL;")
            self.conn.execute("PRAGMA synchronous = NORMAL;")

    def create_tables(self) -> None:
        """Execute schema DDL statements to create tables and indices."""
        with self.conn:
            self.conn.executescript(self.SCHEMA)

    def insert_execution(self, record: ExecutionRecord) -> int:
        """Insert a new execution session record.
        
        Args:
            record: ExecutionRecord to insert.
            
        Returns:
            The newly inserted execution row ID.
        """
        sql = """
        INSERT INTO executions (script_name, started_at, completed_at, metadata_json)
        VALUES (?, ?, ?, ?)
        """
        metadata_str = json.dumps(record.metadata)
        with self.conn:
            cursor = self.conn.execute(
                sql,
                (record.script_name, record.started_at, record.completed_at, metadata_str),
            )
            record.id = cursor.lastrowid
            return record.id

    def update_execution_completed(self, execution_id: int, completed_at: float) -> None:
        """Mark an execution as finished with its completion timestamp."""
        sql = "UPDATE executions SET completed_at = ? WHERE id = ?"
        with self.conn:
            self.conn.execute(sql, (completed_at, execution_id))

    def get_execution(self, execution_id: int) -> Optional[ExecutionRecord]:
        """Retrieve an execution record by its ID."""
        sql = "SELECT id, script_name, started_at, completed_at, metadata_json FROM executions WHERE id = ?"
        cursor = self.conn.execute(sql, (execution_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return ExecutionRecord(
            id=row["id"],
            script_name=row["script_name"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def list_executions(self) -> List[ExecutionRecord]:
        """List all executions ordered by start time descending."""
        sql = "SELECT id, script_name, started_at, completed_at, metadata_json FROM executions ORDER BY started_at DESC"
        cursor = self.conn.execute(sql)
        results = []
        for row in cursor.fetchall():
            results.append(
                ExecutionRecord(
                    id=row["id"],
                    script_name=row["script_name"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    metadata=json.loads(row["metadata_json"] or "{}"),
                )
            )
        return results

    def insert_event_with_variables(
        self,
        event: TraceEvent,
        variables: List[VariableState],
    ) -> int:
        """Atomically insert a trace event and all its associated variable states.
        
        Using a single transaction ensures that either the entire step is recorded
        or rolled back if an error occurs.
        
        Args:
            event: The TraceEvent instance to record.
            variables: List of VariableState objects captured at this event.
            
        Returns:
            The event's generated database primary key ID.
        """
        insert_event_sql = """
        INSERT INTO trace_events (
            execution_id, sequence, line_number, function_name, event_type, timestamp, is_delta
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        insert_var_sql = """
        INSERT INTO variable_states (
            event_id, var_name, serialized_value, value_type
        ) VALUES (?, ?, ?, ?)
        """
        with self.conn:
            cursor = self.conn.execute(
                insert_event_sql,
                (
                    event.execution_id,
                    event.sequence,
                    event.line_number,
                    event.function_name,
                    event.event_type,
                    event.timestamp,
                    1 if event.is_delta else 0,
                ),
            )
            event_id = cursor.lastrowid
            event.id = event_id

            if variables:
                var_rows = [
                    (event_id, v.var_name, v.serialized_value, v.value_type)
                    for v in variables
                ]
                self.conn.executemany(insert_var_sql, var_rows)

            return event_id

    def get_event_with_variables(
        self,
        event_id: int,
    ) -> Optional[Tuple[TraceEvent, List[VariableState]]]:
        """Fetch a specific event and all variable states recorded with it."""
        event_sql = """
        SELECT id, execution_id, sequence, line_number, function_name, event_type, timestamp, is_delta
        FROM trace_events WHERE id = ?
        """
        cursor = self.conn.execute(event_sql, (event_id,))
        row = cursor.fetchone()
        if not row:
            return None

        event = TraceEvent(
            id=row["id"],
            execution_id=row["execution_id"],
            sequence=row["sequence"],
            line_number=row["line_number"],
            function_name=row["function_name"],
            event_type=row["event_type"],
            timestamp=row["timestamp"],
            is_delta=bool(row["is_delta"]),
        )

        var_sql = """
        SELECT id, event_id, var_name, serialized_value, value_type
        FROM variable_states WHERE event_id = ?
        """
        var_cursor = self.conn.execute(var_sql, (event_id,))
        variables = [
            VariableState(
                id=v_row["id"],
                event_id=v_row["event_id"],
                var_name=v_row["var_name"],
                serialized_value=v_row["serialized_value"],
                value_type=v_row["value_type"],
            )
            for v_row in var_cursor.fetchall()
        ]
        return event, variables

    def get_events_for_execution(
        self,
        execution_id: int,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
    ) -> List[Tuple[TraceEvent, List[VariableState]]]:
        """Retrieve all events and variables for an execution in chronological sequence order.
        
        Args:
            execution_id: ID of the execution.
            start_sequence: Optional lower sequence boundary (inclusive).
            end_sequence: Optional upper sequence boundary (inclusive).
            
        Returns:
            List of (TraceEvent, List[VariableState]) tuples strictly sorted by sequence.
        """
        conditions = ["execution_id = ?"]
        params: List[Any] = [execution_id]

        if start_sequence is not None:
            conditions.append("sequence >= ?")
            params.append(start_sequence)
        if end_sequence is not None:
            conditions.append("sequence <= ?")
            params.append(end_sequence)

        where_clause = " AND ".join(conditions)
        events_sql = f"""
        SELECT id, execution_id, sequence, line_number, function_name, event_type, timestamp, is_delta
        FROM trace_events
        WHERE {where_clause}
        ORDER BY sequence ASC
        """

        cursor = self.conn.execute(events_sql, params)
        event_rows = cursor.fetchall()
        if not event_rows:
            return []

        # Optimization: Fetch all variables for these events in a single batch query
        # rather than querying variable_states N times (N+1 query problem).
        event_ids = [row["id"] for row in event_rows]
        placeholders = ",".join("?" for _ in event_ids)
        vars_sql = f"""
        SELECT id, event_id, var_name, serialized_value, value_type
        FROM variable_states
        WHERE event_id IN ({placeholders})
        """
        var_cursor = self.conn.execute(vars_sql, event_ids)
        vars_by_event: Dict[int, List[VariableState]] = {eid: [] for eid in event_ids}
        for v_row in var_cursor.fetchall():
            vars_by_event[v_row["event_id"]].append(
                VariableState(
                    id=v_row["id"],
                    event_id=v_row["event_id"],
                    var_name=v_row["var_name"],
                    serialized_value=v_row["serialized_value"],
                    value_type=v_row["value_type"],
                )
            )

        results: List[Tuple[TraceEvent, List[VariableState]]] = []
        for row in event_rows:
            ev = TraceEvent(
                id=row["id"],
                execution_id=row["execution_id"],
                sequence=row["sequence"],
                line_number=row["line_number"],
                function_name=row["function_name"],
                event_type=row["event_type"],
                timestamp=row["timestamp"],
                is_delta=bool(row["is_delta"]),
            )
            results.append((ev, vars_by_event[row["id"]]))

        return results

    def get_variable_history(
        self,
        execution_id: int,
        var_name: str,
    ) -> List[Dict[str, Any]]:
        """Query the timeline of values for a specific variable across an execution.
        
        Powers the TUI 'Watch Variable' feature.
        """
        sql = """
        SELECT e.sequence, e.line_number, e.timestamp, v.serialized_value, v.value_type
        FROM trace_events e
        JOIN variable_states v ON e.id = v.event_id
        WHERE e.execution_id = ? AND v.var_name = ?
        ORDER BY e.sequence ASC
        """
        cursor = self.conn.execute(sql, (execution_id, var_name))
        return [
            {
                "sequence": row["sequence"],
                "line_number": row["line_number"],
                "timestamp": row["timestamp"],
                "serialized_value": row["serialized_value"],
                "value_type": row["value_type"],
            }
            for row in cursor.fetchall()
        ]

    def close(self) -> None:
        """Close the SQLite database connection cleanly."""
        if self.conn:
            self.conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
