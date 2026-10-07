"""Automated tests for PyChronicle Click CLI."""

import json
import os
import tempfile
import pytest
from click.testing import CliRunner
from pychronicle.cli import cli


@pytest.fixture
def sample_script(tmp_path):
    path = tmp_path / "calc.py"
    path.write_text(
        "total = 0\n"
        "for i in range(1, 4):\n"
        "    total += i * 10\n"
        "print('Done:', total)\n",
        encoding="utf-8",
    )
    return str(path)


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "PyChronicle version" in result.output


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Time-Travel Debugger" in result.output
    assert "run" in result.output
    assert "view" in result.output
    assert "analyze" in result.output
    assert "watch" in result.output
    assert "benchmark" in result.output


def test_cli_analyze(sample_script):
    runner = CliRunner()
    # Test human-readable table output
    result = runner.invoke(cli, ["analyze", sample_script])
    assert result.exit_code == 0
    assert "Static AST Assignment Analysis" in result.output
    assert "total" in result.output

    # Test machine-readable JSON output
    result_json = runner.invoke(cli, ["analyze", sample_script, "--json"])
    assert result_json.exit_code == 0
    data = json.loads(result_json.output)
    assert "assignments" in data
    assert "variables" in data
    assert "total" in data["variables"]


def test_cli_run_headless(sample_script, tmp_path):
    db_file = str(tmp_path / "test_run.db")
    runner = CliRunner()
    result = runner.invoke(cli, ["run", sample_script, "--no-tui", "--db", db_file])
    assert result.exit_code == 0
    assert "Execution Summary" in result.output
    assert "Total Execution Steps" in result.output
    assert os.path.exists(db_file)


def test_cli_watch(sample_script):
    runner = CliRunner()
    result = runner.invoke(cli, ["watch", sample_script, "--var", "total"])
    assert result.exit_code == 0
    assert "Watch Variable History: 'total'" in result.output
    assert "Total Mutations" in result.output


def test_cli_benchmark(sample_script):
    runner = CliRunner()
    result = runner.invoke(cli, ["benchmark", sample_script])
    assert result.exit_code == 0
    assert "Benchmark Comparison" in result.output
    assert "Delta" in result.output
