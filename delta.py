"""Delta Compression Engine for PyChronicle.

Fulfills Week 3 Core Engineering specification:
"Delta Compression: Optimize the tracer to only save 'deltas' (what changed)
rather than the entire state tree at every line, reducing memory usage by 90%."
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class VariableDelta:
    """Represents the mutation of a single variable between two execution steps."""
    var_name: str
    action: str  # 'added', 'modified', 'deleted'
    new_value: Any = None
    old_value: Any = None
    serialized_value: str = ""
    value_type: str = "unknown"


@dataclass
class FrameDelta:
    """Represents all variable mutations between consecutive execution frames."""
    sequence: int
    line_number: int
    is_checkpoint: bool = False
    added: Dict[str, Any] = field(default_factory=dict)
    modified: Dict[str, Any] = field(default_factory=dict)
    deleted: List[str] = field(default_factory=list)
    deltas: List[VariableDelta] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Returns True if any variable was added, modified, or deleted."""
        return bool(self.added or self.modified or self.deleted)

    @property
    def mutation_count(self) -> int:
        """Total count of variable mutations in this frame."""
        return len(self.added) + len(self.modified) + len(self.deleted)


class DeltaCompressor:
    """Computes, stores, and reconstructs variable deltas across execution timelines.

    Provides up to 90%+ storage and memory reduction compared to recording
    full local scope dictionaries on every line hit.
    """

    DELETED_SENTINEL = "__PYCHRONICLE_DELETED__"

    def __init__(self, checkpoint_interval: int = 50) -> None:
        """Initialize the delta compressor.

        Args:
            checkpoint_interval: Number of frames between full-state snapshots (keyframes).
                                 Guarantees O(1) bounded state reconstruction latency.
        """
        self.checkpoint_interval = max(1, checkpoint_interval)

    def is_checkpoint(self, sequence: int, event_type: str = "line") -> bool:
        """Determine if a given frame must be stored as a full-state keyframe.

        Checkpoints are placed at sequence 1, periodically every checkpoint_interval,
        and upon function call scope entry.
        """
        if sequence <= 1:
            return True
        if event_type == "call":
            return True
        return (sequence % self.checkpoint_interval) == 0

    def compute_frame_delta(
        self,
        prev_state: Dict[str, Any],
        current_state: Dict[str, Any],
        sequence: int = 0,
        line_number: int = 0,
        is_checkpoint: bool = False,
    ) -> FrameDelta:
        """Compute the difference between two state snapshots.

        Args:
            prev_state: State dictionary from the preceding execution frame.
            current_state: State dictionary from the current execution frame.
            sequence: Monotonic sequence index.
            line_number: Source code line number.
            is_checkpoint: Whether this frame is marked as a full checkpoint.

        Returns:
            A FrameDelta containing added, modified, and deleted variables.
        """
        frame_delta = FrameDelta(
            sequence=sequence,
            line_number=line_number,
            is_checkpoint=is_checkpoint,
        )

        prev_keys: Set[str] = set(prev_state.keys())
        curr_keys: Set[str] = set(current_state.keys())

        # 1. Added variables: present in current but not in previous
        for k in curr_keys - prev_keys:
            val = current_state[k]
            frame_delta.added[k] = val
            frame_delta.deltas.append(
                VariableDelta(var_name=k, action="added", new_value=val)
            )

        # 2. Deleted variables: present in previous but no longer in current
        for k in prev_keys - curr_keys:
            old_val = prev_state[k]
            frame_delta.deleted.append(k)
            frame_delta.deltas.append(
                VariableDelta(var_name=k, action="deleted", old_value=old_val)
            )

        # 3. Modified variables: present in both but value changed
        for k in curr_keys & prev_keys:
            old_val = prev_state[k]
            new_val = current_state[k]
            if not self._values_equal(old_val, new_val):
                frame_delta.modified[k] = new_val
                frame_delta.deltas.append(
                    VariableDelta(
                        var_name=k,
                        action="modified",
                        new_value=new_val,
                        old_value=old_val,
                    )
                )

        return frame_delta

    def _values_equal(self, a: Any, b: Any) -> bool:
        """Safe comparison of two values that handles unhashable or custom types."""
        if a is b:
            return True
        try:
            # Direct equality check
            eq = (a == b)
            # In case eq is a numpy array or non-boolean
            if isinstance(eq, bool):
                return eq
            return bool(eq)
        except Exception:
            # Fall back to representation comparison
            return repr(a) == repr(b)

    def apply_delta(
        self,
        base_state: Dict[str, Any],
        delta: FrameDelta,
    ) -> Dict[str, Any]:
        """Apply a forward delta to a base state to obtain the updated state.

        Args:
            base_state: Base dictionary of variables.
            delta: FrameDelta to apply.

        Returns:
            A new state dictionary reflecting the mutations.
        """
        new_state = dict(base_state)
        # Add new variables
        new_state.update(delta.added)
        # Update modified variables
        new_state.update(delta.modified)
        # Remove deleted variables
        for k in delta.deleted:
            new_state.pop(k, None)
        return new_state

    def reconstruct_timeline(
        self,
        events: List[Any],
    ) -> List[Dict[str, Any]]:
        """Reconstruct the complete variable state for every event in a timeline.

        Linear O(N) reconstruction pass supporting mixed checkpoints and deltas.

        Args:
            events: List of TraceEvent objects sorted by sequence.

        Returns:
            List of fully hydrated state dictionaries matching the event order.
        """
        reconstructed_states: List[Dict[str, Any]] = []
        current_state: Dict[str, Any] = {}

        for event in events:
            # If the event is a full checkpoint (is_delta == False) and has state
            if not getattr(event, "is_delta", False):
                # Full state snapshot
                current_state = dict(getattr(event, "state", {}) or {})
            else:
                # Delta event: mutate current running state
                delta_state = getattr(event, "state", {}) or {}
                for k, v in delta_state.items():
                    if v == self.DELETED_SENTINEL:
                        current_state.pop(k, None)
                    else:
                        current_state[k] = v

            reconstructed_states.append(dict(current_state))

        return reconstructed_states

    def get_state_at_sequence(
        self,
        events: List[Any],
        target_sequence: int,
    ) -> Dict[str, Any]:
        """Reconstruct the exact local variables state at a specific sequence number.

        Finds the nearest checkpoint before or at target_sequence and rolls forward.
        """
        if not events:
            return {}

        # Find index of target sequence
        target_idx = -1
        for i, ev in enumerate(events):
            if ev.sequence == target_sequence:
                target_idx = i
                break
            elif ev.sequence > target_sequence:
                target_idx = i - 1
                break

        if target_idx < 0:
            target_idx = len(events) - 1

        # Seek backwards to find the nearest keyframe checkpoint
        checkpoint_idx = 0
        for i in range(target_idx, -1, -1):
            if not getattr(events[i], "is_delta", False):
                checkpoint_idx = i
                break

        # Start from checkpoint state
        state = dict(getattr(events[checkpoint_idx], "state", {}) or {})

        # Roll forward to target
        for i in range(checkpoint_idx + 1, target_idx + 1):
            ev = events[i]
            if not getattr(ev, "is_delta", False):
                state = dict(getattr(ev, "state", {}) or {})
            else:
                delta_dict = getattr(ev, "state", {}) or {}
                for k, v in delta_dict.items():
                    if v == self.DELETED_SENTINEL:
                        state.pop(k, None)
                    else:
                        state[k] = v

        return state
