"""Command-line interface (CLI) for PyChronicle (Week 4 Packaging).

Provides commands:
    pychronicle run <script.py>   - Run and time-travel debug a Python script
    pychronicle view <trace.db>    - View an existing SQLite execution trace
    pychronicle demo               - Launch the built-in time-travel demo
"""

from __future__ import annotations

import argparse
import os
import sys

from pychronicle.storage.manager import StorageManager
from pychronicle.ui.app import PyChronicleApp


def trace_and_debug_script(script_path: str) -> None:
    """Trace execution of a Python script using sys.settrace and open TUI."""
    if not os.path.exists(script_path):
        print(f"Error: Script file '{script_path}' not found.", file=sys.stderr)
        sys.exit(1)

    abs_path = os.path.abspath(script_path)
    storage = StorageManager(":memory:")
    exec_id = storage.start_execution(script_path)

    # Simple execution tracer for CLI run command
    def tracer(frame, event, arg):
        if event == "line":
            # Only trace code from target script
            code_file = os.path.abspath(frame.f_code.co_filename)
            if code_file == abs_path:
                clean_state = {}
                for k, v in frame.f_locals.items():
                    if not k.startswith("__"):
                        clean_state[k] = v
                storage.record_event(
                    line_number=frame.f_lineno,
                    state=clean_state,
                    function_name=frame.f_code.co_name,
                )
        return tracer

    with open(abs_path, "r", encoding="utf-8") as f:
        source_code = f.read()

    # Run the script with tracing enabled
    old_trace = sys.gettrace()
    compiled = compile(source_code, abs_path, "exec")
    sys.settrace(tracer)
    try:
        exec(compiled, {"__name__": "__main__", "__file__": abs_path})
    except Exception as e:
        print(f"Execution error while tracing: {e}")
    finally:
        sys.settrace(old_trace)
        storage.finish_execution(exec_id)

    # Launch PyChronicle TUI
    app = PyChronicleApp(
        storage=storage,
        execution_id=exec_id,
        source_code=source_code,
        script_path=abs_path,
    )
    app.run()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="pychronicle",
        description="PyChronicle — AST-Powered Time-Travel Debugger CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Trace and debug a Python script")
    run_parser.add_argument("script", help="Path to Python script to execute and debug")

    # Command: view
    view_parser = subparsers.add_parser("view", help="Inspect an existing SQLite trace database")
    view_parser.add_argument("database", help="Path to SQLite database (.db) file")
    view_parser.add_argument("--exec-id", type=int, default=None, help="Execution ID to load")
    view_parser.add_argument("--script", type=str, default=None, help="Source code path to display")

    # Command: demo
    subparsers.add_parser("demo", help="Launch the interactive demo session")

    args = parser.parse_args(argv)

    if args.command == "run":
        trace_and_debug_script(args.script)
    elif args.command == "view":
        if not os.path.exists(args.database):
            print(f"Error: Database file '{args.database}' not found.", file=sys.stderr)
            sys.exit(1)
        app = PyChronicleApp(
            db_path=args.database,
            execution_id=args.exec_id,
            script_path=args.script,
        )
        app.run()
    elif args.command == "demo" or args.command is None:
        # Default action: run demo
        app = PyChronicleApp()
        app.run()


if __name__ == "__main__":
    main()
