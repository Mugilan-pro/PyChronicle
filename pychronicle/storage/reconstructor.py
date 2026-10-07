"""Historical State Reconstructor for PyChronicle.

Reconstructs complete runtime variable dictionaries from stored deltas and keyframe snapshots.
Enables instant time-travel scrubbing in the Textual TUI without storing redundant full states.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pychronicle.storage.database import Database
from pychronicle.storage.models import TraceEvent
from pychronicle.storage.serializer import ValueSerializer


class StateReconstructor:
    """Reconstructs full historical variable states from delta events."""

    def __init__(self, db: Database, serializer: Optional[ValueSerializer] = None) -> None:
        self.db = db
        self.serializer = serializer or ValueSerializer()

    def reconstruct_state_at_sequence(
        self,
        execution_id: int,
        target_sequence: int,
    ) -> Dict[str, Any]:
        """Reconstruct the complete variable dictionary at a specific execution sequence.
        
        Algorithm:
        1. Query the most recent keyframe snapshot (is_delta == 0) with sequence <= target_sequence.
        2. Load the base state from that snapshot.
        3. Fetch all intermediate delta events from that snapshot up to target_sequence.
        4. Sequentially apply the deltas on top of the base state.
        
        Args:
            execution_id: ID of the execution session.
            target_sequence: Target chronological step to reconstruct.
            
        Returns:
            The reconstructed variable dictionary at that exact point in time.
        """
        # Step 1: Find latest snapshot before or at target_sequence
        find_snapshot_sql = """
        SELECT id, sequence
        FROM trace_events
        WHERE execution_id = ? AND sequence <= ? AND is_delta = 0
        ORDER BY sequence DESC
        LIMIT 1
        """
        cursor = self.db.conn.execute(find_snapshot_sql, (execution_id, target_sequence))
        snapshot_row = cursor.fetchone()

        start_seq = 1
        current_state: Dict[str, Any] = {}

        if snapshot_row:
            snap_id = snapshot_row["id"]
            start_seq = snapshot_row["sequence"]
            # Load snapshot variables
            snap_ev, snap_vars = self.db.get_event_with_variables(snap_id)
            for v in snap_vars:
                current_state[v.var_name] = self.serializer.deserialize(
                    v.serialized_value, v.value_type
                )

        # Step 2: Fetch all events between start_seq and target_sequence
        events_with_vars = self.db.get_events_for_execution(
            execution_id=execution_id,
            start_sequence=start_seq + (1 if snapshot_row else 0),
            end_sequence=target_sequence,
        )

        # Step 3: Replay deltas in chronological order
        for ev, var_states in events_with_vars:
            if not ev.is_delta:
                # Encountered another full snapshot
                current_state = {}
            for v in var_states:
                current_state[v.var_name] = self.serializer.deserialize(
                    v.serialized_value, v.value_type
                )

        return current_state

    def hydrate_all_events(
        self,
        execution_id: int,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
    ) -> List[TraceEvent]:
        """Fetch execution events and hydrate each event with its fully reconstructed state.
        
        Walks through events in sequence order, accumulating deltas in memory so the TUI
        gets a list of events where each event.state contains the complete variable dictionary.
        
        Returns:
            List of TraceEvents with hydrated .state dictionaries.
        """
        raw_events = self.db.get_events_for_execution(
            execution_id=execution_id,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
        )

        hydrated: List[TraceEvent] = []
        running_state: Dict[str, Any] = {}

        for ev, var_states in raw_events:
            if not ev.is_delta:
                # Full snapshot reset
                running_state = {}

            for v in var_states:
                running_state[v.var_name] = self.serializer.deserialize(
                    v.serialized_value, v.value_type
                )

            # Assign a shallow copy of the accumulated state to this event
            ev.state = dict(running_state)
            hydrated.append(ev)

        return hydrated
