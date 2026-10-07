"""PyChronicle Terminal User Interface (TUI) Launcher.

Run this script to launch the interactive time-travel debugging dashboard:
    python run_tui.py
    python run_tui.py --db path/to/trace.db
    python run_tui.py --mock-steps 15
"""

import argparse
import os
import sys

from pychronicle.storage.manager import StorageManager
from pychronicle.storage.mock_tracer import run_mock_trace_session
from pychronicle.ui.app import PyChronicleApp


def main():
    parser = argparse.ArgumentParser(
        description="PyChronicle — AST-Powered Time-Travel Debugger (Textual TUI)"
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to existing SQLite trace database file.",
    )
    parser.add_argument(
        "--exec-id",
        type=int,
        default=None,
        help="Execution ID to load from database (defaults to latest).",
    )
    parser.add_argument(
        "--script",
        type=str,
        default=None,
        help="Path to target source code file to view in Code Pane.",
    )
    parser.add_argument(
        "--mock-steps",
        type=int,
        default=None,
        help="Generate an in-memory mock trace session with N steps.",
    )

    args = parser.parse_args()

    if args.mock_steps:
        print(f"Generating {args.mock_steps}-step mock trace session...")
        storage = StorageManager(":memory:")
        exec_id = run_mock_trace_session(storage, steps=args.mock_steps)
        app = PyChronicleApp(storage=storage, execution_id=exec_id)
    elif args.db:
        if not os.path.exists(args.db):
            print(f"Error: Database file '{args.db}' not found.", file=sys.stderr)
            sys.exit(1)
        app = PyChronicleApp(
            db_path=args.db,
            execution_id=args.exec_id,
            script_path=args.script,
        )
    else:
        # Default: rich algorithm demo
        app = PyChronicleApp(script_path=args.script)

    app.run()


if __name__ == "__main__":
    main()
