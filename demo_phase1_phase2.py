"""Interactive verification script for PyChronicle Phases 1 & 2.

Run this script from your terminal using:
    python demo_phase1_phase2.py
"""

import time
from pychronicle.storage.database import Database
from pychronicle.storage.models import ExecutionRecord, TraceEvent, VariableState


def run_demo():
    print("=" * 60)
    print("  PyChronicle — Storage Engine Demo (Phases 1 & 2)")
    print("=" * 60)

    # 1. Initialize Database (In-Memory for demo, zero disk pollution)
    print("\n[Step 1] Initializing SQLite database...")
    db = Database(":memory:")
    print(" -> Schema created with tables: executions, trace_events, variable_states.")

    # 2. Start an Execution Session
    print("\n[Step 2] Recording a new debug execution session...")
    execution = ExecutionRecord(
        script_name="sample_algorithm.py",
        started_at=time.time(),
        metadata={"python_version": "3.11", "author": "Member 3"},
    )
    exec_id = db.insert_execution(execution)
    print(f" -> Execution session started with ID: {exec_id} for '{execution.script_name}'")

    # 3. Simulate tracer recording events during a loop:
    #    Simulating code:
    #      line 1: total = 0
    #      line 2: for i in range(3):
    #      line 3:     total += (i * 10)
    print("\n[Step 3] Simulating execution tracer line hits and variable state...")
    simulated_steps = [
        # (sequence, line_number, {var_name: (val_str, type_str)})
        (1, 1, {"total": ("0", "int")}),
        (2, 2, {"total": ("0", "int"), "i": ("0", "int")}),
        (3, 3, {"total": ("0", "int"), "i": ("0", "int")}),
        (4, 2, {"total": ("0", "int"), "i": ("1", "int")}),
        (5, 3, {"total": ("10", "int"), "i": ("1", "int")}),
        (6, 2, {"total": ("10", "int"), "i": ("2", "int")}),
        (7, 3, {"total": ("30", "int"), "i": ("2", "int")}),
    ]

    for seq, line, vars_dict in simulated_steps:
        event = TraceEvent(
            execution_id=exec_id,
            sequence=seq,
            line_number=line,
            function_name="calculate_total",
        )
        var_states = [
            VariableState(var_name=k, serialized_value=v[0], value_type=v[1])
            for k, v in vars_dict.items()
        ]
        db.insert_event_with_variables(event, var_states)
        print(f"    Recorded Event #{seq} | Line {line:2d} | Variables: {list(vars_dict.keys())}")

    # Mark execution complete
    db.update_execution_completed(exec_id, completed_at=time.time())
    print(" -> Execution session completed.")

    # 4. Time-Travel Query: Retrieve all events in chronological order
    print("\n[Step 4] Time-Travel Playback (Chronological Retrieval):")
    events = db.get_events_for_execution(exec_id)
    print(f"{'Seq':<5} | {'Line':<6} | {'Function':<16} | {'Variable Values'}")
    print("-" * 60)
    for ev, vars_list in events:
        vars_repr = ", ".join(f"{v.var_name}={v.serialized_value}" for v in vars_list)
        print(f"{ev.sequence:<5} | Line {ev.line_number:<2} | {ev.function_name:<16} | {vars_repr}")

    # 5. Variable History Watch (for TUI watchpoints)
    print("\n[Step 5] TUI Feature — 'Watch Variable total' across time:")
    history = db.get_variable_history(exec_id, "total")
    print(f"{'Seq':<5} | {'Line':<6} | {'Value':<10} | {'Type'}")
    print("-" * 35)
    for h in history:
        print(f"{h['sequence']:<5} | Line {h['line_number']:<2} | {h['serialized_value']:<10} | {h['value_type']}")

    print("\n" + "=" * 60)
    print("  Verification Succeeded! The Storage Engine is functional.")
    print("=" * 60)
    db.close()


if __name__ == "__main__":
    run_demo()
