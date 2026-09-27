"""Mock Tracer for PyChronicle.

Generates realistic execution trace streams to test and validate the storage
engine independently of the AST rewriter and sys.settrace engine (Members 1 & 2).
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Tuple
from pychronicle.storage.manager import StorageManager


def generate_fake_events(num_steps: int = 4) -> Iterator[Tuple[int, Dict[str, Any]]]:
    """Generate a sequence of fake execution line hits with variable mutations.
    
    Simulates a loop:
        for x in range(1, num_steps + 1):
            ...
            
    Yields:
        (line_number, state_dictionary)
    """
    for i in range(1, num_steps + 1):
        line_num = 10 + (i % 3)  # alternates lines 11, 12, 10
        state = {
            "x": i,
            "running_sum": (i * (i + 1)) // 2,
            "status": "active" if i < num_steps else "completed",
        }
        yield (line_num, state)


def run_mock_trace_session(
    storage: StorageManager,
    script_name: str = "mock_script.py",
    steps: int = 4,
) -> int:
    """Execute a complete mock tracing session against the storage manager.
    
    Args:
        storage: StorageManager instance.
        script_name: Name of simulated target script.
        steps: Number of execution steps to generate.
        
    Returns:
        The execution ID of the recorded session.
    """
    exec_id = storage.start_execution(script_name, metadata={"mode": "mock_test"})

    for line_number, state in generate_fake_events(steps):
        storage.record_event(
            line_number=line_number,
            state=state,
            function_name="mock_worker",
        )

    storage.finish_execution(exec_id)
    return exec_id
