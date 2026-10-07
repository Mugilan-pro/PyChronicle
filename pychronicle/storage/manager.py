"""High-level Storage Manager for PyChronicle.

Coordinates execution sessions, serialization, and database persistence.
Provides a clean, friendly Python API for the execution tracer and TUI,
abstracting away all SQL operations.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from pychronicle.storage.database import Database
from pychronicle.storage.models import ExecutionRecord, TraceEvent, VariableState
from pychronicle.storage.serializer import ValueSerializer, deserialize, serialize


class StorageManager:
    """Public interface for execution tracers and user interfaces.
    
    The tracer interacts exclusively with this class, never writing SQL directly.
    
    Example usage:
        storage = StorageManager(":memory:")
        storage.start_execution("script.py")
        storage.record_event(line_number=1, state={"total": 0})
        storage.record_event(line_number=2, state={"total": 10})
        storage.finish_execution()
        events = storage.get_events()
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        serializer: Optional[ValueSerializer] = None,
    ) -> None:
        """Initialize the storage manager with a database and serializer.
        
        Args:
            db_path: Path to SQLite DB file or ':memory:'.
            serializer: Optional custom ValueSerializer instance.
        """
        self.db = Database(db_path)
        self.serializer = serializer or ValueSerializer()
        self.active_execution_id: Optional[int] = None
        self._sequence_counter: int = 0

    def start_execution(
        self,
        script_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Begin a new debugging/tracing session.
        
        Accepts:
            script_name: The filename or path of the script being debugged.
            metadata: Optional dictionary with environment info (Python version, CLI args).
            
        Returns:
            The unique execution ID assigned to this session.
            
        DB Operation:
            Inserts a row into 'executions'.
        """
        record = ExecutionRecord(
            script_name=script_name,
            started_at=time.time(),
            metadata=metadata or {},
        )
        self.active_execution_id = self.db.insert_execution(record)
        self._sequence_counter = 0
        return self.active_execution_id

    def record_event(
        self,
        line_number: int,
        state: Optional[Dict[str, Any]] = None,
        function_name: str = "<module>",
        event_type: str = "line",
        is_delta: bool = False,
        sequence: Optional[int] = None,
    ) -> TraceEvent:
        """Record an execution step (e.g. line hit) and its variable states.
        
        Accepts:
            line_number: Source code line currently being executed.
            state: Dictionary mapping variable names to their current Python values.
            function_name: Name of the enclosing function (default: '<module>').
            event_type: 'line', 'call', 'return', or 'exception'.
            is_delta: Set to True when delta compression is enabled.
            sequence: Optional explicit sequence number. If omitted, auto-increments.
            
        Returns:
            The saved TraceEvent instance with its database ID and sequence assigned.
            
        DB Operation:
            Atomically inserts one 'trace_events' row and N 'variable_states' rows.
            
        Raises:
            RuntimeError: If called before start_execution().
        """
        if self.active_execution_id is None:
            raise RuntimeError("No active execution session. Call start_execution() first.")

        if sequence is None:
            self._sequence_counter += 1
            seq = self._sequence_counter
        else:
            seq = sequence
            self._sequence_counter = max(self._sequence_counter, seq)

        var_states: List[VariableState] = []
        state_dict = state or {}

        for var_name, var_value in state_dict.items():
            payload, val_type = self.serializer.serialize(var_value)
            var_states.append(
                VariableState(
                    var_name=var_name,
                    serialized_value=payload,
                    value_type=val_type,
                )
            )

        event = TraceEvent(
            execution_id=self.active_execution_id,
            sequence=seq,
            line_number=line_number,
            function_name=function_name,
            event_type=event_type,
            state=state_dict,
            is_delta=is_delta,
        )

        event_id = self.db.insert_event_with_variables(event, var_states)
        event.id = event_id
        return event

    def get_event(self, event_id: int) -> Optional[TraceEvent]:
        """Fetch a specific event by ID, deserializing its variables into .state.
        
        Accepts:
            event_id: Database primary key ID of the event.
            
        Returns:
            TraceEvent with deserialized .state dictionary, or None if not found.
        """
        result = self.db.get_event_with_variables(event_id)
        if not result:
            return None

        event, var_states = result
        restored_state: Dict[str, Any] = {}
        for v in var_states:
            restored_state[v.var_name] = self.serializer.deserialize(
                v.serialized_value, v.value_type
            )
        event.state = restored_state
        return event

    def get_events(
        self,
        execution_id: Optional[int] = None,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
    ) -> List[TraceEvent]:
        """Retrieve execution history in strict chronological sequence order.
        
        Accepts:
            execution_id: Session ID to query (defaults to current active execution).
            start_sequence: Optional starting sequence number (inclusive).
            end_sequence: Optional ending sequence number (inclusive).
            
        Returns:
            List of TraceEvents, each populated with its deserialized .state dictionary.
            
        DB Operation:
            Indexed batch SELECT from trace_events and variable_states.
        """
        exec_id = execution_id or self.active_execution_id
        if exec_id is None:
            return []

        raw_events = self.db.get_events_for_execution(
            execution_id=exec_id,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
        )

        hydrated_events: List[TraceEvent] = []
        for ev, var_states in raw_events:
            restored_state: Dict[str, Any] = {}
            for v in var_states:
                restored_state[v.var_name] = self.serializer.deserialize(
                    v.serialized_value, v.value_type
                )
            ev.state = restored_state
            hydrated_events.append(ev)

        return hydrated_events

    def get_execution(self, execution_id: Optional[int] = None) -> Optional[ExecutionRecord]:
        """Retrieve execution metadata."""
        exec_id = execution_id or self.active_execution_id
        if exec_id is None:
            return None
        return self.db.get_execution(exec_id)

    def finish_execution(self, execution_id: Optional[int] = None) -> None:
        """Mark an execution as completed and flush active state."""
        exec_id = execution_id or self.active_execution_id
        if exec_id is not None:
            self.db.update_execution_completed(exec_id, completed_at=time.time())
        if exec_id == self.active_execution_id:
            self.active_execution_id = None
            self._sequence_counter = 0

    def get_variable_history(
        self,
        var_name: str,
        execution_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get the timeline of values for a single variable (powers TUI Watchpoints).
        
        Returns:
            List of dicts: [{'sequence': 1, 'line_number': 5, 'value': 10, ...}, ...]
        """
        exec_id = execution_id or self.active_execution_id
        if exec_id is None:
            return []

        raw_history = self.db.get_variable_history(exec_id, var_name)
        deserialized_history = []
        for h in raw_history:
            deserialized_history.append(
                {
                    "sequence": h["sequence"],
                    "line_number": h["line_number"],
                    "timestamp": h["timestamp"],
                    "value": self.serializer.deserialize(h["serialized_value"], h["value_type"]),
                    "value_type": h["value_type"],
                }
            )
        return deserialized_history

    def close(self) -> None:
        """Close underlying database connection."""
        self.db.close()

    def __enter__(self) -> StorageManager:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
