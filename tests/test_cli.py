"""Unit tests for PyChronicle CLI packaging (Week 4).

Tests command-line parsing, argument validation, and invocation for:
    - pychronicle --help
    - pychronicle demo
    - pychronicle view <db>
    - pychronicle run <script>
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pytest

from pychronicle.cli import main
from pychronicle.storage.manager import StorageManager


def test_cli_help(capsys):
    """Verify pychronicle --help outputs usage information and exits cleanly."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "PyChronicle" in captured.out
    assert "run" in captured.out
    assert "view" in captured.out
    assert "demo" in captured.out


def test_cli_demo_invokes_app():
    """Verify pychronicle demo launches PyChronicleApp."""
    with patch("pychronicle.cli.PyChronicleApp") as mock_app_cls:
        mock_instance = MagicMock()
        mock_app_cls.return_value = mock_instance

        main(["demo"])

        mock_app_cls.assert_called_once_with()
        mock_instance.run.assert_called_once()


def test_cli_default_action_is_demo():
    """Verify running pychronicle with no args defaults to demo."""
    with patch("pychronicle.cli.PyChronicleApp") as mock_app_cls:
        mock_instance = MagicMock()
        mock_app_cls.return_value = mock_instance

        main([])

        mock_app_cls.assert_called_once_with()
        mock_instance.run.assert_called_once()


def test_cli_view_missing_file_exits(capsys):
    """Verify pychronicle view with non-existent database file exits with error."""
    with pytest.raises(SystemExit) as exc_info:
        main(["view", "non_existent_database_file_12345.db"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Database file" in captured.err


def test_cli_view_existing_database(tmp_path):
    """Verify pychronicle view loads specified database file."""
    db_file = str(tmp_path / "test_trace.db")
    # Initialize a valid storage DB
    storage = StorageManager(db_file)
    exec_id = storage.start_execution("test.py")
    storage.finish_execution(exec_id)
    storage.close()

    with patch("pychronicle.cli.PyChronicleApp") as mock_app_cls:
        mock_instance = MagicMock()
        mock_app_cls.return_value = mock_instance

        main(["view", db_file, "--exec-id", str(exec_id)])

        mock_app_cls.assert_called_once_with(
            db_path=db_file,
            execution_id=exec_id,
            script_path=None,
        )
        mock_instance.run.assert_called_once()


def test_cli_run_missing_script_exits(capsys):
    """Verify pychronicle run with missing script file exits with error."""
    with pytest.raises(SystemExit) as exc_info:
        main(["run", "non_existent_script_file_12345.py"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Script file" in captured.err


def test_cli_run_traces_script(tmp_path):
    """Verify pychronicle run traces script execution and initializes app with storage."""
    script_path = str(tmp_path / "sample_code.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("a = 10\nb = 20\nc = a + b\n")

    with patch("pychronicle.cli.PyChronicleApp") as mock_app_cls:
        mock_instance = MagicMock()
        mock_app_cls.return_value = mock_instance

        main(["run", script_path])

        mock_app_cls.assert_called_once()
        call_kwargs = mock_app_cls.call_args[1]
        assert "storage" in call_kwargs
        assert "execution_id" in call_kwargs
        assert "source_code" in call_kwargs
        assert "a = 10" in call_kwargs["source_code"]
        assert call_kwargs["script_path"] == os.path.abspath(script_path)
        mock_instance.run.assert_called_once()
