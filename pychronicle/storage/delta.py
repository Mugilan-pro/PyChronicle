"""Delta Compression Engine for PyChronicle.

Computes state diffs between consecutive execution steps and applies deltas
to reconstruct full historical runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from pychronicle.storage.serializer import ValueSerializer


@dataclass
class StateDelta:
    """Represents the mutation delta between two execution states.
    
    Attributes:
        mutations: Dictionary of variables added or modified (var_name -> new_value).
        deletions: List of variable names deleted or dropped out of scope.
    """
    mutations: Dict[str, Any] = field(default_factory=dict)
    deletions: List[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True if there are no variable mutations or deletions."""
        return len(self.mutations) == 0 and len(self.deletions) == 0

    def apply_to(self, base_state: Dict[str, Any]) -> Dict[str, Any]:
        """Apply this delta on top of a base state to produce the updated state.
        
        Args:
            base_state: Dictionary of variables before this delta.
            
        Returns:
            A new dictionary representing the updated state.
        """
        updated = dict(base_state)
        # 1. Remove deleted variables
        for var_name in self.deletions:
            updated.pop(var_name, None)
        # 2. Apply additions and modifications
        for var_name, new_val in self.mutations.items():
            updated[var_name] = new_val
        return updated


class DeltaCalculator:
    """Calculates state-diffs between execution steps.
    
    Uses serialized representations to ensure safe equality checks,
    preventing bugs from in-place list/dict mutations or custom __eq__ errors.
    """

    def __init__(self, serializer: Optional[ValueSerializer] = None) -> None:
        self.serializer = serializer or ValueSerializer()

    def compute_diff(
        self,
        prev_serialized: Dict[str, Tuple[str, str]],
        curr_state: Dict[str, Any],
    ) -> Tuple[StateDelta, Dict[str, Tuple[str, str]]]:
        """Compute the state-diff between the previous serialized state and current state.
        
        Args:
            prev_serialized: Dictionary mapping var_name -> (serialized_str, type_str).
            curr_state: Current raw variable dictionary from tracer (e.g. frame.f_locals).
            
        Returns:
            Tuple of:
            - StateDelta: Object containing only mutated/added variables and deletions.
            - Dict[str, Tuple[str, str]]: The new serialized state mapping for future comparisons.
        """
        mutations: Dict[str, Any] = {}
        deletions: List[str] = []
        new_serialized: Dict[str, Tuple[str, str]] = {}

        # 1. Detect additions and modifications in current state
        for var_name, curr_val in curr_state.items():
            payload, val_type = self.serializer.serialize(curr_val)
            new_serialized[var_name] = (payload, val_type)

            if var_name not in prev_serialized:
                # Newly created variable
                mutations[var_name] = curr_val
            elif prev_serialized[var_name] != (payload, val_type):
                # Existing variable modified
                mutations[var_name] = curr_val

        # 2. Detect deletions (variables present previously but absent now)
        for var_name in prev_serialized:
            if var_name not in curr_state:
                deletions.append(var_name)

        return StateDelta(mutations=mutations, deletions=deletions), new_serialized
