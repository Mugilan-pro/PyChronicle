"""Lightweight embedded HTTP server for PyChronicle Web UI."""

from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
from typing import Any, Optional
import urllib.parse
import webbrowser

from pychronicle import __version__
from pychronicle.rewriter.analyzer import analyze_code, analyze_file
from pychronicle.storage.database import SQLiteStore
from pychronicle.timeline.history import Timeline
from pychronicle.tracer.engine import run_script

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _safe_json_serialize(obj: Any) -> Any:
    """Helper to ensure custom types like sets or enums are JSON serializable."""
    if isinstance(obj, set):
        return sorted(list(obj))
    if hasattr(obj, "value"):
        return obj.value
    if hasattr(obj, "__dict__"):
        return {k: _safe_json_serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    if isinstance(obj, dict):
        return {str(k): _safe_json_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json_serialize(i) for i in obj]
    return obj


class PyChronicleRequestHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler providing REST API and serving static web assets."""

    server: "PyChronicleServer"  # Type hint for server instance

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        # Quiet standard logging unless debug is desired
        pass

    def _send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        serialized = json.dumps(_safe_json_serialize(data), ensure_ascii=False)
        encoded = serialized.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_error_json(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        self._send_json({"error": message}, status=status)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path.startswith("/api/"):
            self._handle_api_get(path, query)
            return

        # Serve static assets
        if path == "/" or not path:
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get("Content-Length", 0))
        body_raw = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(body_raw.decode("utf-8")) if body_raw else {}
        except Exception:
            body = {}

        if path.startswith("/api/"):
            self._handle_api_post(path, body)
            return

        self._send_error_json("Endpoint not found", HTTPStatus.NOT_FOUND)

    def _handle_api_get(self, path: str, query: dict[str, list[str]]) -> None:
        try:
            if path == "/api/status":
                self._api_status()
            elif path == "/api/databases":
                self._api_databases()
            elif path == "/api/runs":
                self._api_runs()
            elif path == "/api/timeline":
                run_id = int(query["run_id"][0]) if "run_id" in query else None
                self._api_timeline(run_id)
            elif path == "/api/snapshot":
                if "event_id" not in query:
                    self._send_error_json("Missing 'event_id' parameter")
                    return
                event_id = int(query["event_id"][0])
                frame_id = int(query["frame_id"][0]) if "frame_id" in query else None
                self._api_snapshot(event_id, frame_id)
            elif path == "/api/source":
                filepath = query.get("path", [""])[0]
                self._api_source(filepath)
            elif path == "/api/ast":
                filepath = query.get("path", [""])[0]
                self._api_ast(filepath)
            elif path == "/api/examples":
                self._api_examples()
            elif path == "/api/example":
                name = query.get("name", [""])[0]
                self._api_example(name)
            else:
                self._send_error_json(f"Unknown API endpoint: {path}", HTTPStatus.NOT_FOUND)
        except Exception as e:
            self._send_error_json(str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_api_post(self, path: str, body: dict[str, Any]) -> None:
        try:
            if path == "/api/select_db":
                db_name = body.get("database")
                if not db_name:
                    self._send_error_json("Missing 'database' in body")
                    return
                self.server.set_database(db_name)
                self._send_json({"success": True, "database": str(self.server.active_db)})
            elif path == "/api/ast":
                code = body.get("code", "")
                filename = body.get("filename", "<editor>")
                res = analyze_code(code, filename=filename)
                self._send_json({
                    "filename": res.filename,
                    "all_variables": sorted(list(res.all_variables)),
                    "assignments": [
                        {
                            "target_name": a.target_name,
                            "line_number": a.line_number,
                            "col_offset": a.col_offset,
                            "kind": a.kind.value,
                            "scope_name": a.scope_name,
                            "scope_type": a.scope_type,
                            "is_definition": a.is_definition,
                            "raw_code_snippet": a.raw_code_snippet,
                            "end_line_number": a.end_line_number,
                        }
                        for a in res.assignments
                    ],
                    "variables_by_line": {str(k): sorted(list(v)) for k, v in res.variables_by_line.items()},
                    "scopes": {
                        k: {
                            "name": v.name,
                            "scope_type": v.scope_type,
                            "parent_scope": v.parent_name,
                            "start_line": v.start_line,
                            "end_line": v.end_line,
                            "variables": sorted(list(v.assigned_vars)),
                        }
                        for k, v in res.scopes.items()
                    }
                })
            elif path == "/api/trace":
                code = body.get("code")
                script_path = body.get("script_path")

                if script_path:
                    target_path = Path(script_path).resolve()
                    if not target_path.is_file():
                        self._send_error_json(f"Script file not found: {script_path}")
                        return
                    store = run_script(target_path, (), self.server.active_db)
                    store.close()
                    # Return latest run
                    with SQLiteStore(self.server.active_db) as s:
                        run_ids = s.run_ids()
                        latest_run_id = run_ids[-1] if run_ids else None
                    self._send_json({"success": True, "run_id": latest_run_id})
                elif code:
                    # Write to temporary file in examples or scratch
                    temp_dir = Path("examples") if Path("examples").is_dir() else Path(tempfile.gettempdir())
                    temp_file = temp_dir / "_web_trace_temp.py"
                    temp_file.write_text(code, encoding="utf-8")
                    try:
                        store = run_script(temp_file, (), self.server.active_db)
                        store.close()
                        with SQLiteStore(self.server.active_db) as s:
                            run_ids = s.run_ids()
                            latest_run_id = run_ids[-1] if run_ids else None
                        self._send_json({"success": True, "run_id": latest_run_id, "target": str(temp_file)})
                    except Exception as err:
                        self._send_error_json(f"Execution error: {err}")
                else:
                    self._send_error_json("Either 'code' or 'script_path' must be provided")
            else:
                self._send_error_json(f"Unknown POST endpoint: {path}", HTTPStatus.NOT_FOUND)
        except Exception as e:
            self._send_error_json(str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    def _api_status(self) -> None:
        self._send_json({
            "version": __version__,
            "active_database": str(self.server.active_db),
            "database_exists": self.server.active_db.is_file(),
            "workspace_dir": str(Path.cwd()),
        })

    def _api_databases(self) -> None:
        cwd = Path.cwd()
        dbs = list(cwd.glob("*.sqlite3")) + list(cwd.glob("*.db"))
        # Format as relative names
        db_list = [str(p.relative_to(cwd)) for p in sorted(dbs)]
        self._send_json({"databases": db_list, "active": str(self.server.active_db.name if self.server.active_db.is_file() else self.server.active_db)})

    def _api_runs(self) -> None:
        if not self.server.active_db.is_file():
            self._send_json([])
            return

        with SQLiteStore(self.server.active_db) as store:
            run_ids = store.run_ids()
            runs = []
            for r_id in reversed(run_ids):
                info = store.run_info(r_id)
                events_count = store.connection.execute(
                    "SELECT COUNT(*) FROM events WHERE run_id = ?", (r_id,)
                ).fetchone()[0]
                runs.append({
                    "id": info["id"],
                    "target": info["target"],
                    "target_name": Path(info["target"]).name,
                    "started_at": info["started_at"],
                    "finished_at": info["finished_at"],
                    "status": info["status"],
                    "error": info["error"],
                    "event_count": events_count,
                })
            self._send_json(runs)

    def _api_timeline(self, run_id: Optional[int]) -> None:
        if not self.server.active_db.is_file():
            self._send_json([])
            return

        with SQLiteStore(self.server.active_db) as store:
            events = store.events(run_id)
            data = []
            for e in events:
                data.append({
                    "id": e.id,
                    "run_id": e.run_id,
                    "sequence": e.sequence,
                    "timestamp": e.timestamp,
                    "filename": e.filename,
                    "filename_short": Path(e.filename).name,
                    "line_number": e.line_number,
                    "function_name": e.function_name,
                    "frame_id": e.frame_id,
                    "changes": e.changes,
                    "changed_keys": sorted(list(e.changes.keys())),
                })
            self._send_json(data)

    def _api_snapshot(self, event_id: int, frame_id: Optional[int]) -> None:
        if not self.server.active_db.is_file():
            self._send_error_json("Database does not exist")
            return

        with SQLiteStore(self.server.active_db) as store:
            variables = store.state_at(event_id, frame_id)
            # Also get the event itself
            row = store.connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            if row is None:
                self._send_error_json("Event not found")
                return
            event_info = dict(row)
            self._send_json({
                "event": event_info,
                "variables": variables,
            })

    def _api_source(self, filepath: str) -> None:
        if not filepath:
            self._send_error_json("Path parameter is required")
            return

        path = Path(filepath)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()

        if not path.is_file():
            self._send_error_json(f"Source file not found: {path}")
            return

        try:
            content = path.read_text(encoding="utf-8")
            self._send_json({
                "path": str(path),
                "filename": path.name,
                "content": content,
                "lines": content.splitlines(),
                "line_count": len(content.splitlines()),
            })
        except Exception as e:
            self._send_error_json(f"Failed to read file: {e}")

    def _api_ast(self, filepath: str) -> None:
        if not filepath:
            self._send_error_json("Path parameter is required")
            return

        path = Path(filepath)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()

        if not path.is_file():
            self._send_error_json(f"File not found: {path}")
            return

        try:
            res = analyze_file(path)
            self._send_json({
                "filename": res.filename,
                "all_variables": sorted(list(res.all_variables)),
                "assignments": [
                    {
                        "target_name": a.target_name,
                        "line_number": a.line_number,
                        "col_offset": a.col_offset,
                        "kind": a.kind.value,
                        "scope_name": a.scope_name,
                        "scope_type": a.scope_type,
                        "is_definition": a.is_definition,
                        "raw_code_snippet": a.raw_code_snippet,
                        "end_line_number": a.end_line_number,
                    }
                    for a in res.assignments
                ],
                "variables_by_line": {str(k): sorted(list(v)) for k, v in res.variables_by_line.items()},
                "scopes": {
                    k: {
                        "name": v.name,
                        "scope_type": v.scope_type,
                        "parent_scope": v.parent_name,
                        "start_line": v.start_line,
                        "end_line": v.end_line,
                        "variables": sorted(list(v.assigned_vars)),
                    }
                    for k, v in res.scopes.items()
                }
            })
        except Exception as e:
            self._send_error_json(f"AST Analysis failed: {e}")

    def _api_examples(self) -> None:
        examples_dir = Path("examples")
        if not examples_dir.is_dir():
            self._send_json([])
            return

        examples = []
        for file in sorted(examples_dir.glob("*.py")):
            examples.append({
                "name": file.name,
                "path": str(file),
                "size": file.stat().st_size,
            })
        self._send_json(examples)

    def _api_example(self, name: str) -> None:
        if not name:
            self._send_error_json("Name parameter required")
            return
        target = Path("examples") / name
        if not target.is_file():
            self._send_error_json(f"Example {name} not found")
            return
        content = target.read_text(encoding="utf-8")
        self._send_json({"name": name, "path": str(target), "content": content})


class PyChronicleServer(ThreadingHTTPServer):
    """Threading HTTP Server customized for PyChronicle Web UI."""

    def __init__(self, host: str, port: int, initial_database: str | Path) -> None:
        self.active_db = Path(initial_database).resolve()
        super().__init__((host, port), PyChronicleRequestHandler)

    def set_database(self, database: str | Path) -> None:
        self.active_db = Path(database).resolve()


def start_server(
    database: str | Path = "history.sqlite3",
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> PyChronicleServer:
    """Instantiate and run the PyChronicle Web UI server."""
    # If the specified database doesn't exist yet, check fallback to pychronicle.sqlite3 if present
    db_path = Path(database)
    if not db_path.is_file():
        if Path("history.sqlite3").is_file():
            db_path = Path("history.sqlite3")
        elif Path("pychronicle.sqlite3").is_file():
            db_path = Path("pychronicle.sqlite3")

    # Try binding to port; if already taken, try next available port
    server = None
    for attempt_port in range(port, port + 20):
        try:
            server = PyChronicleServer(host, attempt_port, db_path)
            port = attempt_port
            break
        except OSError:
            continue

    if server is None:
        raise OSError(f"Could not bind to {host} on ports {port}-{port+20}")

    url = f"http://{host}:{port}/"
    print(f"============================================================")
    print(f" PyChronicle Web UI Time-Travel Debugger")
    print(f" Web Dashboard: {url}")
    print(f" Active Database: {server.active_db.name}")
    print(f" Press Ctrl+C to stop the server.")
    print(f"============================================================")

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    return server


if __name__ == "__main__":
    server = start_server()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down PyChronicle Web Server...")
        server.server_close()
