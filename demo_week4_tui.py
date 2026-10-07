"""Week 4 Interactive Demo: Textual Time-Travel Debugger UI.

Runs an interactive demonstration algorithm (e.g. dynamic state mutations in a loop),
records the execution with Delta Compression into SQLite, and launches the
Textual Terminal User Interface.
"""

from __future__ import annotations

import sys
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
from pychronicle.runner import PyChronicleRunner
from pychronicle.ui.app import PyChronicleApp

SAMPLE_ALGORITHM = """# PyChronicle Interactive Time-Travel Debugger Demo
# Algorithm: Prime Sieve and Running Statistics

def sieve_primes(max_val):
    primes = []
    is_prime = [True] * (max_val + 1)
    is_prime[0] = is_prime[1] = False
    
    for p in range(2, max_val + 1):
        if is_prime[p]:
            primes.append(p)
            for multiple in range(p * p, max_val + 1, p):
                is_prime[multiple] = False
                
    return primes

limit = 15
found_primes = sieve_primes(limit)
total_count = len(found_primes)
sum_primes = sum(found_primes)
print(f"Primes up to {limit}: {found_primes}")
"""


def main():
    script_path = "sample_algorithm.py"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(SAMPLE_ALGORITHM)

    print("================================================================================")
    print("        PYCHRONICLE — WEEK 4 TIME-TRAVEL DEBUGGER TUI DEMO                     ")
    print("================================================================================")
    print("Recording execution with Week 3 Delta Compression into 'trace.db'...")

    runner = PyChronicleRunner("trace.db", delta_mode=True, checkpoint_interval=25)
    exec_id = runner.run_file(script_path)
    events = runner.get_timeline(exec_id)
    stats = runner.get_storage_stats(exec_id)

    print(f"Captured {len(events)} execution steps.")
    print(f"Storage: {stats['keyframe_events']} keyframes, {stats['delta_events']} delta frames.")
    print(f"Total variable rows: {stats['total_variable_rows']}")
    print("\nControls inside the Textual TUI:")
    print("  [h] / [Left]   : Step Backward in time")
    print("  [l] / [Right]  : Step Forward in time")
    print("  [j] / [k]      : Jump -10 / +10 steps")
    print("  [g] / [G]      : Jump to Start / End")
    print("  [Space]        : Toggle auto-play animation")
    print("  [w]            : Focus Watch Variable input box")
    print("  [q]            : Quit TUI")
    print("================================================================================\n")

    if "--no-tui" not in sys.argv:
        app = PyChronicleApp(
            events=events,
            source_code=SAMPLE_ALGORITHM,
            script_name="sample_algorithm.py",
            storage=runner.storage,
        )
        app.run()


if __name__ == "__main__":
    main()
