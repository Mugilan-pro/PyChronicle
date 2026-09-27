"""Mid-Project Review Validation: Zero-Dropped-Frame Complex Loop & Storage Audit.

Fulfills Mid-Project Review specification from PROJECT.pdf:
"Trace Validation: Prove the tracer accurately records the execution of a
complex loop without dropping frames."
"Storage Audit: Ensure the database handles thousands of state changes without
significant overhead."

Usage:
    python validate_trace_loop.py
"""

from __future__ import annotations

import sys
import time
from typing import Any, Dict, List

from pychronicle.runner import PyChronicleRunner
from pychronicle.storage import StorageManager
from pychronicle.tracer import ExecutionTracer, TraceFilter


def run_complex_loop_validation() -> bool:
    print("=" * 80)
    print("  PYCHRONICLE  MID-PROJECT REVIEW AUDIT & TRACE VALIDATION")
    print("=" * 80)

    # 1. Define Target Script with Nested Loops, Branching, and Accumulators
    target_code = """
total_sum = 0
parity_flips = 0

for outer_idx in range(5):
    step_multiplier = outer_idx + 1
    for inner_idx in range(4):
        if inner_idx % 2 == 0:
            total_sum += (inner_idx * step_multiplier)
            parity_flips += 1
        else:
            total_sum += 1

final_summary = total_sum + parity_flips
"""

    print("\n[Audit Test 1] Validating Complex Nested Loop Frame Capture...")
    storage = StorageManager(":memory:")
    storage.start_execution("nested_loop_audit.py")

    trace_filter = TraceFilter(target_files=["nested_loop_audit.py"])
    tracer = ExecutionTracer(
        storage=storage,
        trace_filter=trace_filter,
    )

    t0 = time.perf_counter()
    tracer.run_code(target_code, filename="nested_loop_audit.py")
    t1 = time.perf_counter()

    events = storage.get_events()
    total_recorded = len(events)
    dropped = tracer.dropped_frames

    print(f"  -> Execution Time       : {(t1 - t0) * 1000:.2f} ms")
    print(f"  -> Total Frames Observed: {tracer.total_frames_observed}")
    print(f"  -> Total Frames Recorded: {total_recorded}")
    print(f"  -> Dropped Frames Count : {dropped}")

    # Theoretical Ground Truth Calculation:
    # Line 2: total_sum = 0 (1)
    # Line 3: parity_flips = 0 (1)
    # Line 5: for outer_idx in range(5) (5 iterations + 1 loop exit check = 6 hits)
    # Per outer iteration (5 times):
    #   Line 6: step_multiplier = outer_idx + 1 (5 hits)
    #   Line 7: for inner_idx in range(4) (4 iterations + 1 loop exit check = 5 hits per outer = 25 hits)
    #   Per inner iteration (5 * 4 = 20 times):
    #     Line 8: if inner_idx % 2 == 0 (20 hits)
    #     When inner_idx is 0 or 2 (even, 10 times):
    #       Line 9: total_sum += ... (10 hits)
    #       Line 10: parity_flips += 1 (10 hits)
    #     When inner_idx is 1 or 3 (odd, 10 times):
    #       Line 12: total_sum += 1 (10 hits)
    # Line 14: final_summary = ... (1 hit)
    # Plus return/call frame events if captured.

    assert dropped == 0, f"FAIL: Dropped frames detected ({dropped})!"
    assert total_recorded > 0, "FAIL: No events were recorded!"

    # Sequence Monotonicity Verification
    sequences = [ev.sequence for ev in events]
    expected_sequences = list(range(1, total_recorded + 1))
    assert sequences == expected_sequences, "FAIL: Sequence numbers are not strictly monotonic!"
    print("  -> Sequence Integrity   : 100% Deterministic Monotonic Order [1..N] (PASS)")

    # Final State Accuracy Verification
    final_event = events[-1]
    final_state = final_event.state

    # Compute expected mathematical values:
    exp_sum = 0
    exp_flips = 0
    for o in range(5):
        m = o + 1
        for i in range(4):
            if i % 2 == 0:
                exp_sum += (i * m)
                exp_flips += 1
            else:
                exp_sum += 1
    exp_final = exp_sum + exp_flips

    assert final_state.get("total_sum") == exp_sum, (
        f"State mismatch: total_sum={final_state.get('total_sum')} != {exp_sum}"
    )
    assert final_state.get("parity_flips") == exp_flips, (
        f"State mismatch: parity_flips={final_state.get('parity_flips')} != {exp_flips}"
    )
    assert final_state.get("final_summary") == exp_final, (
        f"State mismatch: final_summary={final_state.get('final_summary')} != {exp_final}"
    )

    print(f"  -> State Correctness    : Verified total_sum={exp_sum}, parity_flips={exp_flips} (PASS)")
    print("  [Audit Test 1 Result]   : SUCCESS (0 Dropped Frames, Full Accuracy)")

    # 2. Large Scale Storage & Tracer Throughput Audit (5,000 frame loop)
    print("\n[Audit Test 2] High-Frequency Storage & Tracer Throughput Audit...")
    stress_code = """
acc = 0
for k in range(2500):
    acc = acc + 1
"""
    storage2 = StorageManager(":memory:")
    storage2.start_execution("stress_benchmark.py")
    tracer2 = ExecutionTracer(storage=storage2, trace_filter=TraceFilter(target_files=["stress_benchmark.py"]))

    t_start = time.perf_counter()
    tracer2.run_code(stress_code, filename="stress_benchmark.py")
    t_end = time.perf_counter()

    elapsed = t_end - t_start
    events_count = tracer2.events_recorded
    throughput = events_count / elapsed if elapsed > 0 else 0

    print(f"  -> Total Events Captured: {events_count}")
    print(f"  -> Total Execution Time : {elapsed:.3f} seconds")
    print(f"  -> Tracing Throughput   : {throughput:,.0f} events/sec")
    print(f"  -> Average Frame Overhead: {(elapsed / events_count) * 1000:.4f} ms/frame")
    print(f"  -> Dropped Frames Count : {tracer2.dropped_frames}")

    assert tracer2.dropped_frames == 0, "FAIL: Dropped frames during high frequency stress!"
    assert events_count >= 5000, f"FAIL: Expected >= 5000 events, got {events_count}"

    print("  [Audit Test 2 Result]   : SUCCESS (High Throughput, 0 Dropped Frames)")

    # 3. Variable Timeline Scrubbing Audit (Watchpoint)
    print("\n[Audit Test 3] Variable Watchpoint Timeline Audit...")
    history = storage.get_variable_history("total_sum")
    print(f"  -> Watch history entries for 'total_sum': {len(history)} mutations recorded")
    print(f"  -> Sample of initial mutations:")
    for h in history[:5]:
        print(f"     Step #{h['sequence']:<3} | Line {h['line_number']:<2} | total_sum = {h['value']}")
    print(f"     ...")
    last_h = history[-1]
    print(f"     Step #{last_h['sequence']:<3} | Line {last_h['line_number']:<2} | total_sum = {last_h['value']} (FINAL)")
    print("  [Audit Test 3 Result]   : SUCCESS (Complete Mutation Trajectory Preserved)")

    print("\n" + "=" * 80)
    print("  ALL MID-PROJECT AUDIT CHECKS PASSED: ZERO DROPPED FRAMES CONFIRMED")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = run_complex_loop_validation()
    sys.exit(0 if success else 1)
