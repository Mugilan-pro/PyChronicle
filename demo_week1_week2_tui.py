"""PyChronicle — Weeks 1 & 2 Interactive TUI Demo.

Demonstrates the UI scaffolding built for Weeks 1 and 2:
- Code viewer pane with syntax highlighting and active line indicator
- Timeline slider scrubber with step navigation
- Variable viewer showing local variables from SQLite storage

Run from terminal:
    python demo_week1_week2_tui.py
"""

import sys
from pychronicle.storage.manager import StorageManager
from pychronicle.ui.app import PyChronicleApp


def run_week1_week2_demo():
    print("=" * 64)
    print("  PyChronicle — Terminal UI (Weeks 1 & 2)")
    print("=" * 64)
    print("Features demonstrated:")
    print("  1. Code viewer pane with syntax highlighting and line pointer")
    print("  2. Timeline slider scrubber with step navigation and playback")
    print("  3. Variable viewer showing local variables from SQLite storage")
    print("-" * 64)

    # 1. Connect to in-memory storage matching Member 3's schema
    print("\n[1/3] Initializing storage session...")
    storage = StorageManager(":memory:")
    exec_id = storage.start_execution(
        script_name="sample_scripts/demo_algorithm.py",
        metadata={"phase": "Weeks 1 & 2 Demo"},
    )

    # 2. Record sample execution trace events
    print("[2/3] Loading sample trace events into SQLite...")
    events_data = [
        (6, {"limit": 6}),
        (7, {"limit": 6, "total_sum": 0}),
        (8, {"limit": 6, "total_sum": 0, "fib_sequence": []}),
        (9, {"limit": 6, "total_sum": 0, "fib_sequence": [], "a": 0, "b": 1}),
        (11, {"limit": 6, "total_sum": 0, "fib_sequence": [], "a": 0, "b": 1, "step": 0}),
        (12, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 0, "b": 1, "step": 0}),
        (13, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 0, "b": 1, "step": 0}),
        (14, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 0, "b": 1, "step": 0, "next_val": 1}),
        (15, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 1, "b": 1, "step": 0, "next_val": 1}),
        (16, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 1, "b": 1, "step": 0, "next_val": 1}),
        (11, {"limit": 6, "total_sum": 0, "fib_sequence": [0], "a": 1, "b": 1, "step": 1, "next_val": 1}),
        (12, {"limit": 6, "total_sum": 0, "fib_sequence": [0, 1], "a": 1, "b": 1, "step": 1, "next_val": 1}),
        (13, {"limit": 6, "total_sum": 1, "fib_sequence": [0, 1], "a": 1, "b": 1, "step": 1, "next_val": 1}),
    ]

    for line_num, state in events_data:
        storage.record_event(
            line_number=line_num,
            state=state,
            function_name="compute_fibonacci_stats",
        )
    storage.finish_execution(exec_id)
    print(f"      Recorded {len(events_data)} trace steps.")

    # 3. Launch Textual App
    print("[3/3] Launching Terminal UI...")
    print("\nPress Enter to open the dashboard (press 'q' inside TUI to exit)...")

    if sys.stdin.isatty():
        try:
            input()
        except EOFError:
            pass

    app = PyChronicleApp(
        storage=storage,
        execution_id=exec_id,
        script_path="sample_scripts/demo_algorithm.py",
    )
    app.run()


if __name__ == "__main__":
    run_week1_week2_demo()
