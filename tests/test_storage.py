from pychronicle.storage.database import SQLiteStore


def test_sqlite_store_records_and_reconstructs_deltas(tmp_path) -> None:
    path = tmp_path / "trace.sqlite3"
    with SQLiteStore(path) as store:
        run_id = store.create_run("sample.py")
        first = store.record_event(
            run_id=run_id,
            sequence=1,
            filename="sample.py",
            line_number=1,
            function_name="<module>",
            frame_id=1,
            changes={"value": 1, "items": [1]},
        )
        second = store.record_event(
            run_id=run_id,
            sequence=2,
            filename="sample.py",
            line_number=2,
            function_name="<module>",
            frame_id=1,
            changes={"items": [1, 2]},
            deleted={"value"},
        )
        store.finish_run(run_id, "completed")

        events = store.events(run_id)
        assert [event.sequence for event in events] == [1, 2]
        assert events[1].changes["value"] == {"__deleted__": True}
        assert store.state_at(first) == {"value": 1, "items": [1]}
        assert store.state_at(second) == {"items": [1, 2]}
        assert store.run_info(run_id)["status"] == "completed"


def test_non_json_objects_are_stored_as_safe_representations() -> None:
    with SQLiteStore() as store:
        run_id = store.create_run("sample.py")
        event_id = store.record_event(
            run_id=run_id,
            sequence=1,
            filename="sample.py",
            line_number=1,
            function_name="<module>",
            frame_id=1,
            changes={"marker": object()},
        )

        value = store.state_at(event_id)["marker"]
        assert value["__type__"] == "object"
        assert "object at" in value["__repr__"]


def test_serialization_does_not_call_custom_repr() -> None:
    class Noisy:
        def __repr__(self) -> str:
            raise AssertionError("repr must not run while tracing")

    from pychronicle.storage.database import serialize_value

    value = Noisy()
    assert "Noisy" in serialize_value(value)
    assert serialize_value([value]) != "[]"