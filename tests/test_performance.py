"""Performance and stress benchmarks for PyChronicle Storage Subsystem."""

import os
import time
import pytest
from pychronicle.storage.manager import StorageManager


def test_insert_and_retrieve_1000_events(tmp_path):
    """Benchmark inserting and retrieving 1,000 events with multiple variable states."""
    db_file = str(tmp_path / "bench_1k.db")
    storage = StorageManager(db_file)
    exec_id = storage.start_execution("bench_1k.py")

    start_insert = time.perf_counter()
    for i in range(1, 1001):
        storage.record_event(
            line_number=10 + (i % 20),
            state={"i": i, "running_total": i * 10, "label": f"item_{i}"},
        )
    storage.finish_execution(exec_id)
    insert_duration = time.perf_counter() - start_insert

    # Verify retrieval
    start_read = time.perf_counter()
    events = storage.get_events(exec_id)
    read_duration = time.perf_counter() - start_read

    storage.close()
    file_size_kb = os.path.getsize(db_file) / 1024

    assert len(events) == 1000
    assert insert_duration < 5.0, f"1k insert took too long: {insert_duration:.3f}s"
    assert read_duration < 2.0, f"1k read took too long: {read_duration:.3f}s"
