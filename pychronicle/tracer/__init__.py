"""PyChronicle Execution Tracer Subsystem.

Provides runtime execution tracing using sys.settrace, frame filtering,
and zero-dropped-frame event capture into SQLite.
"""

from pychronicle.tracer.engine import ExecutionTracer
from pychronicle.tracer.filter import TraceFilter

__all__ = [
    "ExecutionTracer",
    "TraceFilter",
]
