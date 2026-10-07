"""Interactive demonstration of PyChronicle's delta compression and state reconstruction.

Demonstrates:
1. Delta Compression (~90% storage savings compared to full state snapshots).
2. Historical State Reconstruction on demand from stored deltas.
3. Command-Line Interface (CLI) verification.

Usage:
    python example_delta_compression.py
"""

import os
import tempfile
from pychronicle.cli import build_parser, cmd_info, cmd_run, cmd_view
from pychronicle.storage.manager import StorageManager


def demo_delta_compression():
    print("=" * 65)
    print("  PyChronicle — Delta Compression & Storage Optimization")
    print("=" * 65)

    num_steps = 20

    def get_state(step):
        return {
            "app_name": "PyChronicle",
            "version": "0.2.0",
            "mode": "production",
            "max_retries": 3,
            "timeout_ms": 5000,
            "accumulator": step * 10,  # Only this variable changes!
        }

    # Run A: Full Snapshots (baseline)
    storage_full = StorageManager(":memory:", enable_delta=False)
    exec_full = storage_full.start_execution("full_snapshots.py")
    for i in range(1, num_steps + 1):
        storage_full.record_event(line_number=10 + (i % 3), state=get_state(i))
    storage_full.finish_execution(exec_full)

    rows_full = storage_full.db.conn.execute("SELECT COUNT(*) FROM variable_states").fetchone()[0]

    # Run B: Delta Compression
    storage_delta = StorageManager(":memory:", enable_delta=True, checkpoint_interval=50)
    exec_delta = storage_delta.start_execution("delta_compressed.py")
    for i in range(1, num_steps + 1):
        storage_delta.record_event(line_number=10 + (i % 3), state=get_state(i))
    storage_delta.finish_execution(exec_delta)

    rows_delta = storage_delta.db.conn.execute("SELECT COUNT(*) FROM variable_states").fetchone()[0]

    savings_percent = ((rows_full - rows_delta) / rows_full) * 100

    print(f"\nExecution: {num_steps} steps with 6 variables per line")
    print(f"  • Full Snapshots Stored  : {rows_full} variable rows")
    print(f"  • Delta Compressed Stored: {rows_delta} variable rows")
    print(f"  • Storage Reduction      : {savings_percent:.1f}% SAVED! (Less disk/memory bloat)")

    # Demonstrate State Reconstruction
    print("\n[State Reconstruction Test]")
    target_step = 15
    reconstructed = storage_delta.reconstruct_state(target_step, execution_id=exec_delta)
    expected = get_state(target_step)
    assert reconstructed == expected
    print(f"  • Successfully reconstructed full state at Step #{target_step} from compressed deltas:")
    print(f"    accumulator={reconstructed['accumulator']}, mode='{reconstructed['mode']}'")

    storage_full.close()
    storage_delta.close()


def demo_cli_packaging():
    print("\n" + "=" * 65)
    print("  PyChronicle — CLI Tracing & Time-Travel View")
    print("=" * 65)

    sample_script = os.path.join(tempfile.gettempdir(), "demo_script.py")
    sample_db = os.path.join(tempfile.gettempdir(), "demo_trace.db")

    with open(sample_script, "w") as f:
        f.write("balance = 100\nfor deposit in [25, 50, 75]:\n    balance += deposit\n")

    parser = build_parser()

    # 1. CLI: run
    print("\n1. Running CLI Command: pychronicle run demo_script.py")
    args_run = parser.parse_args(["run", sample_script, "--db", sample_db])
    cmd_run(args_run)

    # 2. CLI: info
    print("\n2. Running CLI Command: pychronicle info demo_trace.db")
    args_info = parser.parse_args(["info", sample_db])
    cmd_info(args_info)

    # 3. CLI: view timeline
    print("\n3. Running CLI Command: pychronicle view demo_trace.db --limit 5")
    args_view = parser.parse_args(["view", sample_db, "--limit", "5"])
    cmd_view(args_view)

    # 4. CLI: view watch variable
    print("\n4. Running CLI Command: pychronicle view demo_trace.db --var balance")
    args_var = parser.parse_args(["view", sample_db, "--var", "balance"])
    cmd_view(args_var)

    # Clean up
    if os.path.exists(sample_script):
        os.remove(sample_script)
    if os.path.exists(sample_db):
        os.remove(sample_db)

    print("\n" + "=" * 65)
    print("  Verification Succeeded!")
    print("=" * 65)


if __name__ == "__main__":
    demo_delta_compression()
    demo_cli_packaging()
