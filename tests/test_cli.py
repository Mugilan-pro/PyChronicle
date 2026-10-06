"""Unit tests for PyChronicle CLI tool."""

import os
import tempfile
import pytest
from pychronicle.cli import build_parser, cmd_info, cmd_run, cmd_view


def test_cli_parser_subcommands():
    """Verify CLI parser recognizes run, info, and view subcommands."""
    parser = build_parser()

    # Test run arguments
    args_run = parser.parse_args(["run", "target.py", "--db", "custom.db", "--no-delta"])
    assert args_run.subcommand == "run"
    assert args_run.script == "target.py"
    assert args_run.db == "custom.db"
    assert args_run.no_delta is True

    # Test info arguments
    args_info = parser.parse_args(["info", "test.db"])
    assert args_info.subcommand == "info"
    assert args_info.db == "test.db"

    # Test view arguments
    args_view = parser.parse_args(["view", "test.db", "--var", "counter", "--limit", "10"])
    assert args_view.subcommand == "view"
    assert args_view.db == "test.db"
    assert args_view.var == "counter"
    assert args_view.limit == 10


def test_cli_run_and_inspect_lifecycle(tmp_path):
    """End-to-end test tracing a Python script and viewing its trace data."""
    # 1. Create a dummy Python script to trace
    script_file = str(tmp_path / "sample_app.py")
    with open(script_file, "w") as f:
        f.write("total = 0\nfor i in range(3):\n    total += i * 2\n")

    db_file = str(tmp_path / "test_trace.db")

    # 2. Run the script via CLI
    parser = build_parser()
    args_run = parser.parse_args(["run", script_file, "--db", db_file])
    exit_code_run = cmd_run(args_run)
    assert exit_code_run == 0
    assert os.path.exists(db_file)

    # 3. Test info subcommand
    args_info = parser.parse_args(["info", db_file])
    exit_code_info = cmd_info(args_info)
    assert exit_code_info == 0

    # 4. Test view subcommand for timeline
    args_view = parser.parse_args(["view", db_file])
    exit_code_view = cmd_view(args_view)
    assert exit_code_view == 0

    # 5. Test view subcommand for variable watch
    args_view_var = parser.parse_args(["view", db_file, "--var", "total"])
    exit_code_var = cmd_view(args_view_var)
    assert exit_code_var == 0
