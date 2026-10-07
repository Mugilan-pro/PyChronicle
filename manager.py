"""High-level Storage Manager for PyChronicle.

Coordinates execution sessions, serialization, delta compression, and database persistence.
Provides a clean, friendly Python API for the execution tracer, TUI, and CLI,
abstracting away all SQL operations.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Optional

from pychronicle.storage.database import Database
from pychronicle.storage.delta import DeltaCompressor, FrameDelta, VariableDelta
from pychronicle.storage.models import ExecutionRecord, TraceEvent, VariableState
from pychronicle.storage.serializer import ValueSerializer, deserialize, serialize


class StorageManager:
    """Public interface for execution tracers and user interfaces.
    
    The tracer interacts exclusively with this class, never writing SQL directly.
    Supports both full-state recording and high-efficiency Delta Compression (Week 3).
    
    Example usage:
        storage = StorageManager(":memory:", delta_mode=True)
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
        delta_mode: bool = False,
        checkpoint_interval: int = 50,
    ) -> None:
        """Initialize the storage manager with a database, serializer, and delta compression.
        
        Args:
            db_path: Path to SQLite DB file or ':memory:'.
            serializer: Optional custom ValueSerializer instance.
            delta_mode: If True, enables Week 3 delta compression (90%+ storage savings).
            checkpoint_interval: Keyframe frequency for delta reconstruction.
        """
        self.db = Database(db_path)
        self.serializer = serializer or ValueSerializer()
        self.delta_mode = delta_mode
        self.compressor = DeltaCompressor(checkpoint_interval=checkpoint_interval)
        self.active_execution_id: Optional[int] = None
        self.last_execution_id: Optional[int] = None
        self._sequence_counter: int = 0
        self._last_state: Dict[str, Any] = {}

    def _resolve_execution_id(self, execution_id: Optional[int] = None) -> Optional[int]:
        """Resolve target execution ID, falling back to active, last, or most recent."""
        if execution_id is not None:
            return execution_id
        if self.active_execution_id is not None:
            return self.active_execution_id
        if self.last_execution_id is not None:
            return self.last_execution_id
        execs = self.db.list_executions()
        if execs:
            self.last_execution_id = execs[0].id
            return self.last_execution_id
        return None

    def _snapshot_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Deepcopy state dictionary safely to detect in-place container mutations."""
        try:
            return copy.deepcopy(state)
        except Exception:
            snapshot = {}
            for k, v in state.items():
                try:
                    snapshot[k] = copy.deepcopy(v)
                except Exception:
                    snapshot[k] = v
            return snapshot

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
        """
        meta = dict(metadata or {})
        record = ExecutionRecord(
            script_name=script_name,
            started_at=time.time(),
            metadata=meta,
        )
        self.active_execution_id = self.db.insert_execution(record)
        self.last_execution_id = self.active_execution_id
        self._sequence_counter = 0
        self._last_state = {}
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
        
        If delta_mode is enabled, automatically computes variable differences
        and writes only mutated variables, saving 90%+ storage space.
        """
        if self.active_execution_id is None:
            raise RuntimeError("No active execution session. Call start_execution() first.")

        if sequence is None:
            self._sequence_counter += 1
            seq = self._sequence_counter
        else:
            seq = sequence
            self._sequence_counter = max(self._sequence_counter, seq)

        state_dict = state or {}
        var_states: List[VariableState] = []
        actual_is_delta = is_delta

        if self.delta_mode:
            # Check if this frame is a full keyframe snapshot
            is_cp = self.compressor.is_checkpoint(seq, event_type)
            if is_cp:
                # Keyframe checkpoint: store all variables
                actual_is_delta = False
                for var_name, var_value in state_dict.items():
                    payload, val_type = self.serializer.serialize(var_value)
                    var_states.append(
                        VariableState(
                            var_name=var_name,
                            serialized_value=payload,
                            value_type=val_type,
                        )
                    )
            else:
                # Delta frame: compute differences from preceding frame
                actual_is_delta = True
                frame_delta = self.compressor.compute_frame_delta(
                    prev_state=self._last_state,
                    current_state=state_dict,
                    sequence=seq,
                    line_number=line_number,
                )

                # Store added and modified variables
                for var_name, var_value in {**frame_delta.added, **frame_delta.modified}.items():
                    payload, val_type = self.serializer.serialize(var_value)
                    var_states.append(
                        VariableState(
                            var_name=var_name,
                            serialized_value=payload,
                            value_type=val_type,
                        )
                    )

                # Store deleted variables with deletion sentinel
                for var_name in frame_delta.deleted:
                    var_states.append(
                        VariableState(
                            var_name=var_name,
                            serialized_value=DeltaCompressor.DELETED_SENTINEL,
                            value_type="deleted",
                        )
                    )

            self._last_state = self._snapshot_state(state_dict)

        else:
            # Full-state recording mode (default / Weeks 1 & 2)
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
            is_delta=actual_is_delta,
        )

        event_id = self.db.insert_event_with_variables(event, var_states)
        event.id = event_id
        return event

    def get_event(self, event_id: int) -> Optional[TraceEvent]:
        """Fetch a specific event by ID, deserializing its variables into .state."""
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
        
        If delta compression was used, transparently reconstructs the complete
        historical state tree for every frame so consumers always receive full state.
        """
        exec_id = self._resolve_execution_id(execution_id)
        if exec_id is None:
            return []

        raw_events = self.db.get_events_for_execution(
            execution_id=exec_id,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
        )

        hydrated_events: List[TraceEvent] = []
        has_delta = False

        for ev, var_states in raw_events:
            restored_state: Dict[str, Any] = {}
            for v in var_states:
                if v.serialized_value == DeltaCompressor.DELETED_SENTINEL:
                    restored_state[v.var_name] = DeltaCompressor.DELETED_SENTINEL
                else:
                    restored_state[v.var_name] = self.serializer.deserialize(
                        v.serialized_value, v.value_type
                    )
            ev.state = restored_state
            if ev.is_delta:
                has_delta = True
            hydrated_events.append(ev)

        # Transparent delta reconstruction for consumers
        if has_delta and hydrated_events:
            reconstructed_states = self.compressor.reconstruct_timeline(hydrated_events)
            for ev, full_st in zip(hydrated_events, reconstructed_states):
                ev.state = full_st

        return hydrated_events

    def get_state_at(self, sequence: int, execution_id: Optional[int] = None) -> Dict[str, Any]:
        """Reconstruct the exact local variables state at any sequence step."""
        exec_id = self._resolve_execution_id(execution_id)
        if exec_id is None:
            return {}
        events = self.get_events(execution_id=exec_id)
        return self.compressor.get_state_at_sequence(events, sequence)

    def get_execution(self, execution_id: Optional[int] = None) -> Optional[ExecutionRecord]:
        """Retrieve execution metadata."""
        exec_id = self._resolve_execution_id(execution_id)
        if exec_id is None:
            return None
        return self.db.get_execution(exec_id)

    def finish_execution(self, execution_id: Optional[int] = None) -> None:
        """Mark an execution as completed and flush active state."""
        exec_id = execution_id or self.active_execution_id
        if exec_id is not None:
            self.db.update_execution_completed(exec_id, completed_at=time.time())
            self.last_execution_id = exec_id
        if exec_id == self.active_execution_id:
            self.active_execution_id = None
            self._sequence_counter = 0
            self._last_state = {}

    def get_variable_history(
        self,
        var_name: str,
        execution_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get the timeline of values for a single variable (powers Watch Variables).
        
        Returns:
            List of dicts: [{'sequence': 1, 'line_number': 5, 'value': 10, ...}, ...]
        """
        exec_id = self._resolve_execution_id(execution_id)
        if exec_id is None:
            return []

        raw_history = self.db.get_variable_history(exec_id, var_name)
        deserialized_history = []
        for h in raw_history:
            if h["serialized_value"] == DeltaCompressor.DELETED_SENTINEL:
                val = "<DELETED>"
            else:
                val = self.serializer.deserialize(h["serialized_value"], h["value_type"])

            deserialized_history.append(
                {
                    "sequence": h["sequence"],
                    "line_number": h["line_number"],
                    "timestamp": h["timestamp"],
                    "value": val,
                    "value_type": h["value_type"],
                }
            )
        return deserialized_history

    def get_storage_stats(self, execution_id: Optional[int] = None) -> Dict[str, Any]:
        """Compute metrics regarding trace events, delta compression, and storage efficiency."""
        exec_id = self._resolve_execution_id(execution_id)
        if exec_id is None:
            return {}

        events_cursor = self.db.conn.execute(
            "SELECT count(*), sum(case when is_delta = 1 then 1 else 0 end) FROM trace_events WHERE execution_id = ?",
            (exec_id,)
        )
        row = events_cursor.fetchone()
        total_events = row[0] or 0
        delta_events = row[1] or 0
        keyframe_events = total_events - delta_events

        vars_cursor = self.db.conn.execute(
            """
            SELECT count(v.id) 
            FROM variable_states v 
            JOIN trace_events e ON v.event_id = e.id 
            WHERE e.execution_id = ?
            """,
            (exec_id,)
        )
        total_var_rows = vars_cursor.fetchone()[0] or 0

        return {
            "execution_id": exec_id,
            "total_events": total_events,
            "delta_events": delta_events,
            "keyframe_events": keyframe_events,
            "total_variable_rows": total_var_rows,
            "delta_ratio": (delta_events / total_events) if total_events else 0.0,
        }

    def close(self) -> None:
        """Close underlying database connection."""
        self.db.close()

    def __enter__(self) -> StorageManager:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
