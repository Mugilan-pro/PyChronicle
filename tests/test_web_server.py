"""Unit and integration tests for PyChronicle Web Server and REST APIs."""

import json
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
import pytest

from pychronicle.web.server import PyChronicleServer, start_server


@pytest.fixture(scope="module")
def web_server():
    """Start an in-process PyChronicle web server on a test port."""
    server = start_server(
        database="history.sqlite3",
        host="127.0.0.1",
        port=9123,
        open_browser=False,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.4)

    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    yield base_url, server

    server.shutdown()
    server.server_close()


def test_static_assets_served(web_server):
    base_url, _ = web_server

    # Index page
    with urllib.request.urlopen(f"{base_url}/") as response:
        assert response.status == 200
        content = response.read().decode("utf-8")
        assert "PyChronicle" in content
        assert "Time-Travel Debugger" in content

    # CSS
    with urllib.request.urlopen(f"{base_url}/style.css") as response:
        assert response.status == 200
        css = response.read().decode("utf-8")
        assert "--accent-cyan" in css

    # JS
    with urllib.request.urlopen(f"{base_url}/app.js") as response:
        assert response.status == 200
        js = response.read().decode("utf-8")
        assert "PyChronicle" in js


def test_api_status(web_server):
    base_url, _ = web_server
    with urllib.request.urlopen(f"{base_url}/api/status") as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert "version" in data
        assert "active_database" in data
        assert data["database_exists"] is True


def test_api_databases(web_server):
    base_url, _ = web_server
    with urllib.request.urlopen(f"{base_url}/api/databases") as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert "databases" in data
        assert any("history.sqlite3" in db for db in data["databases"])


def test_api_runs_and_timeline(web_server):
    base_url, _ = web_server
    # Runs
    with urllib.request.urlopen(f"{base_url}/api/runs") as response:
        assert response.status == 200
        runs = json.loads(response.read().decode("utf-8"))
        assert len(runs) > 0
        latest_run = runs[0]
        assert "id" in latest_run
        assert "target_name" in latest_run

    # Timeline for latest run
    with urllib.request.urlopen(f"{base_url}/api/timeline?run_id={latest_run['id']}") as response:
        assert response.status == 200
        events = json.loads(response.read().decode("utf-8"))
        assert len(events) > 0
        first_event = events[0]
        assert "sequence" in first_event
        assert "line_number" in first_event

    # Snapshot for first event
    event_id = first_event["id"]
    with urllib.request.urlopen(f"{base_url}/api/snapshot?event_id={event_id}&frame_id={first_event['frame_id']}") as response:
        assert response.status == 200
        snapshot = json.loads(response.read().decode("utf-8"))
        assert "variables" in snapshot
        assert "event" in snapshot


def test_api_ast_analysis(web_server):
    base_url, _ = web_server
    # Test GET /api/ast with existing file
    target = urllib.parse.quote("examples/debugging_example.py")
    with urllib.request.urlopen(f"{base_url}/api/ast?path={target}") as response:
        assert response.status == 200
        ast_data = json.loads(response.read().decode("utf-8"))
        assert "assignments" in ast_data
        assert "all_variables" in ast_data
        assert "scopes" in ast_data
        assert len(ast_data["assignments"]) > 0

    # Test POST /api/ast with custom code
    req = urllib.request.Request(
        f"{base_url}/api/ast",
        data=json.dumps({"code": "x = 42\ny = x + 1\n"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        res = json.loads(response.read().decode("utf-8"))
        assert "x" in res["all_variables"]
        assert "y" in res["all_variables"]


def test_api_examples(web_server):
    base_url, _ = web_server
    with urllib.request.urlopen(f"{base_url}/api/examples") as response:
        assert response.status == 200
        examples = json.loads(response.read().decode("utf-8"))
        assert len(examples) > 0
        example_names = [e["name"] for e in examples]
        assert "debugging_example.py" in example_names
