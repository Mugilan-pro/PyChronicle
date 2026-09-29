import pytest

from pychronicle.storage.database import SQLiteStore
from pychronicle.timeline.history import Timeline


def test_timeline_navigates_snapshots() -> None:
    with SQLiteStore() as store:
        run_id = store.create_run("sample.py")
        store.record_event(
            run_id=run_id,
            sequence=1,
            filename="sample.py",
            line_number=1,
            function_name="<module>",
            frame_id=1,
            changes={"count": 1},
        )
        last_id = store.record_event(
            run_id=run_id,
            sequence=2,
            filename="sample.py",
            line_number=2,
            function_name="<module>",
            frame_id=1,
            changes={"count": 2},
        )

        timeline = Timeline(store, run_id)
        assert len(timeline) == 2
        assert timeline.at(0).variables == {"count": 1}
        assert timeline.at(1).event.id == last_id
        assert timeline.at(1).variables == {"count": 2}
        with pytest.raises(IndexError):
            timeline.at(2)