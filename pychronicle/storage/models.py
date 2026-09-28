"""Data models for PyChronicle's storage engine.

These models define the in-memory representation of executions, trace events,
and variable states. They provide type safety and clear contracts between
the tracer and the storage backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Dict, Optional


@dataclass
class ExecutionRecord:
    """Represents a single debugged script run or session."""
    script_name: str
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None


@dataclass
class VariableState:
    """Represents a single variable captured at a specific trace event.
    
    Attributes:
        var_name: The identifier of the variable (e.g., 'total_sum').
        serialized_value: The string/JSON payload representing the value.
        value_type: The Python type name (e.g., 'int', 'list', 'UserObject').
        event_id: The foreign key ID of the associated TraceEvent.
        id: Optional primary key in database.
    """
    var_name: str
    serialized_value: str
    value_type: str
    event_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class TraceEvent:
    """Represents a single point in execution history (e.g., a line hit).
    
    This is the core contract between the execution tracer and storage.
    
    Attributes:
        execution_id: The ID of the execution session this event belongs to.
        sequence: Monotonically increasing counter (1, 2, 3...) per execution.
                  Guarantees deterministic chronological ordering.
        line_number: Line in the source code currently being executed.
        state: Dictionary of variable names mapped to their Python values.
        function_name: Name of the active function/scope (defaults to '<module>').
        event_type: 'line', 'call', 'return', or 'exception'.
        timestamp: System time when the event occurred.
        is_delta: Flag indicating whether 'state' is a full snapshot (False)
                  Flag for delta compression optimization.
        id: Primary key assigned by SQLite upon persistence.
    """
    execution_id: int
    sequence: int
    line_number: int
    state: Dict[str, Any] = field(default_factory=dict)
    function_name: str = "<module>"
    event_type: str = "line"
    timestamp: float = field(default_factory=time.time)
    is_delta: bool = False
    id: Optional[int] = None
