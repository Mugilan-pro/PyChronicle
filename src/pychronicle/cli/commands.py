"""Command-line commands for recording and reviewing a trace."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from pychronicle import __version__
from pychronicle.storage.database import SQLiteStore
from pychronicle.tracer.engine import run_script


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pychronicle",
        description="Record Python variable history and inspect it without rerunning the script.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run a Python script under the tracer")
    run.add_argument("--db", default="pychronicle.sqlite3", help="SQLite history file")
    run.add_argument("script", type=Path)
    run.add_argument("script_args", nargs=argparse.REMAINDER, help="arguments passed to the script")
    inspect = commands.add_parser("inspect", help="print the recorded event timeline")
    inspect.add_argument("database", type=Path)
    ui = commands.add_parser("ui", help="open the interactive history viewer")
    ui.add_argument("database", type=Path)
    web = commands.add_parser("web", help="open the interactive web-based history viewer")
    web.add_argument("database", nargs="?", default=Path("history.sqlite3"), type=Path, help="SQLite history file (default: history.sqlite3)")
    web.add_argument("--port", type=int, default=8765, help="server port (default: 8765)")
    web.add_argument("--host", default="127.0.0.1", help="server host (default: 127.0.0.1)")
    web.add_argument("--no-open", action="store_true", help="do not automatically open the browser")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "run":
        try:
            store = run_script(args.script, args.script_args, args.db)
        except (OSError, SyntaxError) as error:
            print(f"pychronicle: {error}", file=sys.stderr)
            return 1
        try:
            events = store.events()
            run_info = store.run_info(events[-1].run_id) if events else None
            print(f"Recorded {len(events)} line events to {args.db}")
            if run_info:
                print(f"Run status: {run_info['status']}")
        finally:
            store.close()
        return 0
    if args.command == "inspect":
        if not args.database.is_file():
            print(f"pychronicle: history database not found: {args.database}", file=sys.stderr)
            return 1
        with SQLiteStore(args.database) as store:
            events = store.events()
            for event in events:
                changed = ", ".join(event.changes)
                suffix = f"  changed: {changed}" if changed else ""
                print(
                    f"{event.sequence:>6}  {Path(event.filename).name}:"
                    f"{event.line_number:<5} {event.function_name}{suffix}"
                )
            if not events:
                print("No trace events found.")
        return 0
    if args.command == "web":
        from pychronicle.web.server import start_server
        server = start_server(
            database=args.database,
            host=args.host,
            port=args.port,
            open_browser=not args.no_open,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down PyChronicle Web Server...")
            server.server_close()
        return 0
    if not args.database.is_file():
        print(f"pychronicle: history database not found: {args.database}", file=sys.stderr)
        return 1
    from pychronicle.ui.app import HistoryApp

    HistoryApp(args.database).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())