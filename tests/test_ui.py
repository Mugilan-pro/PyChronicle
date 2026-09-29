import asyncio

from pychronicle.storage.database import SQLiteStore
from pychronicle.ui.app import HistoryApp


def test_textual_history_app_mounts_and_navigates(tmp_path) -> None:
    source = tmp_path / "viewed.py"
    source.write_text("first = 1\nsecond = 2\n", encoding="utf-8")
    database = tmp_path / "view.sqlite3"
    with SQLiteStore(database) as store:
        run_id = store.create_run(str(source))
        for sequence, line, name, value in ((1, 1, "first", 1), (2, 2, "second", 2)):
            store.record_event(
                run_id=run_id,
                sequence=sequence,
                filename=str(source),
                line_number=line,
                function_name="<module>",
                frame_id=1,
                changes={name: value},
            )

    async def exercise() -> None:
        app = HistoryApp(database)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert "Event 1/2" in str(app.query_one("#timeline").render())
            await pilot.press("right")
            await pilot.pause()
            assert "Event 2/2" in str(app.query_one("#timeline").render())

    asyncio.run(exercise())
