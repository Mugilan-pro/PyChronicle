"""Command-Line Interface (CLI) for PyChronicle.

Allows users to trace Python scripts, inspect recorded databases,
and view variable timelines directly from the terminal.

Usage:
    pychronicle run myscript.py [--db trace.db] [--delta]
    pychronicle info [trace.db]
    pychronicle view [trace.db] [--var VAR_NAME] [--limit 20]
    pychronicle benchmark [--events 1000]
"""

from __future__ import annotations

import argparse
import os
import runpy
import sys
import time
from typing import Optional

from pychronicle.storage.database import Database
from pychronicle.storage.manager import StorageManager


def cmd_run(args: argparse.Namespace) -> int:
    """Execute a target Python script with PyChronicle tracing and storage."""
    script_path = args.script
    if not os.path.isfile(script_path):
        print(f"Error: Target script '{script_path}' not found.", file=sys.stderr)
        return 1

    db_path = args.db
    enable_delta = not args.no_delta

    print("=" * 60)
    print(f"  PyChronicle — Tracing: {os.path.basename(script_path)}")
    print(f"  Database : {db_path} | Delta Compression: {'ON' if enable_delta else 'OFF'}")
    print("=" * 60)

    storage = StorageManager(
        db_path=db_path,
        enable_delta=enable_delta,
        checkpoint_interval=args.checkpoint_interval,
    )
    exec_id = storage.start_execution(
        script_name=os.path.basename(script_path),
        metadata={"path": os.path.abspath(script_path)},
    )

    event_count = 0

    def tracer_callback(frame, event, arg):
        nonlocal event_count
        if event == "line":
            # Only trace code from the target script file
            code_filename = frame.f_code.co_filename
            if os.path.abspath(code_filename) == os.path.abspath(script_path):
                event_count += 1
                # Filter out internal private names starting with '__'
                clean_locals = {
                    k: v for k, v in frame.f_locals.items() if not k.startswith("__")
                }
                storage.record_event(
                    line_number=frame.f_lineno,
                    state=clean_locals,
                    function_name=frame.f_code.co_name,
                )
        return tracer_callback

    start_time = time.time()
    sys.settrace(tracer_callback)
    try:
        # Run target script in its own namespace
        runpy.run_path(script_path, run_name="__main__")
    except Exception as e:
        print(f"\n[PyChronicle] Program terminated with exception: {e}")
    finally:
        sys.settrace(None)
        storage.finish_execution(exec_id)
        duration = time.time() - start_time
        storage.close()

    db_size_kb = os.path.getsize(db_path) / 1024.0 if os.path.exists(db_path) else 0.0

    print("\n" + "=" * 60)
    print("  Execution Trace Completed Successfully!")
    print(f"  • Total Events Recorded : {event_count:,}")
    print(f"  • Execution Duration     : {duration:.3f} s")
    print(f"  • Saved Database         : {db_path} ({db_size_kb:.1f} KB)")
    print("=" * 60)
    print(f"Run 'pychronicle view {db_path}' to inspect the recorded timeline.")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Inspect execution sessions inside a trace database."""
    db_path = args.db
    if not os.path.isfile(db_path):
        print(f"Error: Trace database '{db_path}' not found.", file=sys.stderr)
        return 1

    db = Database(db_path)
    executions = db.list_executions()

    print("=" * 65)
    print(f"  PyChronicle Trace Info: {db_path}")
    print("=" * 65)

    if not executions:
        print("No execution records found in database.")
        db.close()
        return 0

    for ex in executions:
        events = db.conn.execute(
            "SELECT COUNT(*) FROM trace_events WHERE execution_id = ?", (ex.id,)
        ).fetchone()[0]
        vars_count = db.conn.execute(
            """
            SELECT COUNT(*) FROM variable_states v
            JOIN trace_events e ON v.event_id = e.id
            WHERE e.execution_id = ?
            """,
            (ex.id,),
        ).fetchone()[0]

        duration = (ex.completed_at - ex.started_at) if ex.completed_at else 0.0

        print(f"Session ID   : {ex.id}")
        print(f"Script       : {ex.script_name}")
        print(f"Events       : {events:,}")
        print(f"Var Entries  : {vars_count:,}")
        print(f"Duration     : {duration:.3f} s")
        print("-" * 65)

    db.close()
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    """View chronological events or variable history from a trace database."""
    db_path = args.db
    if not os.path.isfile(db_path):
        print(f"Error: Trace database '{db_path}' not found.", file=sys.stderr)
        return 1

    storage = StorageManager(db_path, enable_delta=True)
    executions = storage.db.list_executions()
    if not executions:
        print("No executions found.")
        storage.close()
        return 0

    exec_id = executions[0].id

    if args.var:
        # Watch variable view
        history = storage.get_variable_history(args.var, exec_id)
        print("=" * 55)
        print(f"  Watch Variable History: '{args.var}'")
        print("=" * 55)
        if not history:
            print(f"Variable '{args.var}' was not recorded in this session.")
        else:
            print(f"{'Seq':<6} | {'Line':<6} | {'Value':<16} | {'Type'}")
            print("-" * 55)
            for h in history[: args.limit]:
                print(f"{h['sequence']:<6} | Line {h['line_number']:<2} | {str(h['value']):<16} | {h['value_type']}")
    else:
        # Event timeline view
        events = storage.get_events(exec_id)
        print("=" * 70)
        print(f"  Chronological Timeline (Showing first {min(len(events), args.limit)} events)")
        print("=" * 70)
        print(f"{'Seq':<6} | {'Line':<6} | {'Function':<14} | {'Variables State'}")
        print("-" * 70)
        for ev in events[: args.limit]:
            state_str = ", ".join(f"{k}={v}" for k, v in ev.state.items())
            if len(state_str) > 40:
                state_str = state_str[:37] + "..."
            print(f"{ev.sequence:<6} | Line {ev.line_number:<2} | {ev.function_name:<14} | {state_str}")

    storage.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="pychronicle",
        description="PyChronicle: AST-Powered Time-Travel Debugger CLI",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available commands")

    # Command: run
    p_run = subparsers.add_parser("run", help="Run a script with time-travel tracing")
    p_run.add_argument("script", help="Path to Python script to trace")
    p_run.add_argument("--db", default="trace.db", help="Output SQLite database file (default: trace.db)")
    p_run.add_argument("--no-delta", action="store_true", help="Disable delta compression (store full snapshots)")
    p_run.add_argument("--checkpoint-interval", type=int, default=50, help="Keyframe snapshot interval (default: 50)")

    # Command: info
    p_info = subparsers.add_parser("info", help="Inspect a recorded trace database")
    p_info.add_argument("db", nargs="?", default="trace.db", help="Path to trace database (default: trace.db)")

    # Command: view
    p_view = subparsers.add_parser("view", help="View timeline steps or variable history")
    p_view.add_argument("db", nargs="?", default="trace.db", help="Path to trace database (default: trace.db)")
    p_view.add_argument("--var", help="Watch a specific variable across time")
    p_view.add_argument("--limit", type=int, default=25, help="Maximum number of rows to display")

    return parser


def main() -> int:
    """CLI entry point."""
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()
    if args.subcommand == "run":
        return cmd_run(args)
    elif args.subcommand == "info":
        return cmd_info(args)
    elif args.subcommand == "view":
        return cmd_view(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
