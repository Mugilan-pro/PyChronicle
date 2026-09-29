from pychronicle.cli.commands import main
from pychronicle.storage.database import SQLiteStore


def test_cli_runs_script_and_prints_history(tmp_path, capsys) -> None:
    script = tmp_path / "cli_target.py"
    database = tmp_path / "cli.sqlite3"
    script.write_text("answer = 6 * 7\n", encoding="utf-8")

    assert main(["run", "--db", str(database), str(script)]) == 0
    output = capsys.readouterr().out
    assert "Recorded" in output

    assert main(["inspect", str(database)]) == 0
    output = capsys.readouterr().out
    assert "cli_target.py" in output
    with SQLiteStore(database) as store:
        event = next(item for item in store.events() if item.changes.get("answer") == 42)
        assert store.state_at(event.id)["answer"] == 42