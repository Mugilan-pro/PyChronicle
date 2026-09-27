"""Interactive Demonstration of PyChronicle Weeks 1 & 2 (AST Rewriter & Tracer).

Showcases:
1. Week 1: AST Parsing & Identification of Variable Assignments
2. Week 1 & 2: Dynamic AST Rewriting (Hook Injection)
3. Week 2: Runtime sys.settrace Execution Engine & SQLite Recording
4. Mid-Project Review: Time-Travel Playback & Historical State Scrubbing
5. Variable Watchpoint Querying (Historical Timeline)

Usage:
    python demo_week1_week2_ast.py
"""

from __future__ import annotations

import time

from pychronicle.rewriter import (
    analyze_code,
    rewrite_code,
)
from pychronicle.runner import PyChronicleRunner


SAMPLE_SCRIPT = '''def compute_collatz(n):
    sequence = [n]
    steps = 0
    current = n
    while current > 1:
        if current % 2 == 0:
            current = current // 2
        else:
            current = 3 * current + 1
        sequence.append(current)
        steps += 1
    return steps, sequence

start_val = 6
total_steps, full_seq = compute_collatz(start_val)
'''


def run_interactive_demo():
    print("=" * 80)
    print("   PYCHRONICLE  AST REWRITER & EXECUTION TRACER (WEEKS 1 & 2 DEMO)")
    print("=" * 80)

    # -------------------------------------------------------------
    # STEP 1 (WEEK 1): AST Parsing & Variable Assignment Identification
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 1 (WEEK 1): AST Parsing & Variable Assignment Identification")
    print("-" * 80)
    print("Target Script: Collatz Conjecture Algorithm\n")

    analysis = analyze_code(SAMPLE_SCRIPT, filename="collatz.py")

    print(f"[+] AST Parsing Complete: {len(analysis.assignments)} assignments cataloged.")
    print(f"[+] Variables Identified: {sorted(list(analysis.all_variables))}")
    print(f"[+] Scopes Detected     : {list(analysis.scopes.keys())}\n")

    print(f"{'Line':<6} | {'Target Name':<16} | {'Kind':<14} | {'Scope':<20} | {'Def?'}")
    print("-" * 70)
    for rec in analysis.assignments:
        def_mark = "YES" if rec.is_definition else "NO"
        print(f"L{rec.line_number:<5} | {rec.target_name:<16} | {rec.kind.value:<14} | {rec.scope_name:<20} | {def_mark}")

    # -------------------------------------------------------------
    # STEP 2: Dynamic AST Rewriting (Hook Injection)
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 2: Dynamic AST Rewriting & Metaprogramming Instrumentation")
    print("-" * 80)
    unparsed, _ = rewrite_code(SAMPLE_SCRIPT, filename="collatz.py")

    print("[+] In-Memory AST Rewritten without touching disk source code.")
    print("[+] State-capturing hooks injected at statement boundaries:")
    print("-" * 40)
    for line in unparsed.splitlines()[:16]:
        print(f"    {line}")
    print("    ...")

    # -------------------------------------------------------------
    # STEP 3 (WEEK 2): Execution Tracing with sys.settrace & SQLite Recording
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 3 (WEEK 2): Execution Engine Tracing & SQLite Recording")
    print("-" * 80)

    runner = PyChronicleRunner(db_path=":memory:")
    t0 = time.perf_counter()
    exec_id = runner.run_code(SAMPLE_SCRIPT, filename="collatz.py", mode="tracer")
    t1 = time.perf_counter()

    timeline = runner.get_timeline()
    print(f"[+] Script executed in {(t1 - t0)*1000:.2f} ms")
    print(f"[+] Total execution steps recorded into SQLite: {len(timeline)}")

    # -------------------------------------------------------------
    # STEP 4: Time-Travel Playback & Historical State Scrubbing
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 4: Time-Travel Playback (Chronological Historical States)")
    print("-" * 80)
    print(f"{'Step':<6} | {'Line':<6} | {'Function':<18} | {'Variable State Snapshot'}")
    print("-" * 80)

    # Display first 8 steps
    for step in timeline[:8]:
        state_str = ", ".join(f"{k}={v}" for k, v in step.state.items())
        print(f"#{step.sequence:<5} | L{step.line_number:<5} | {step.function_name:<18} | {state_str}")

    print("  ... [time-traveling through loop execution] ...")

    # Display last 5 steps
    for step in timeline[-5:]:
        state_str = ", ".join(f"{k}={v}" for k, v in step.state.items())
        print(f"#{step.sequence:<5} | L{step.line_number:<5} | {step.function_name:<18} | {state_str}")

    # -------------------------------------------------------------
    # STEP 5: TUI Feature  Variable Watchpoint Scrubbing
    # -------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 5: Variable Watchpoint  Tracking 'current' Over Time")
    print("-" * 80)
    watch_history = runner.watch_variable("current")
    print(f"{'Sequence':<10} | {'Line':<8} | {'Value':<12} | {'Type'}")
    print("-" * 45)
    for entry in watch_history:
        print(f"Step #{entry['sequence']:<6} | Line {entry['line_number']:<4} | {str(entry['value']):<12} | {entry['value_type']}")

    runner.close()

    print("\n" + "=" * 80)
    print("  DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    run_interactive_demo()
