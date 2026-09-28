"""Performance Benchmark Suite for PyChronicle Storage Subsystem.

Evaluates write throughput, read latency, and disk footprint for
1,000 and 10,000 execution events.

Run from Command Prompt:
    python benchmark.py
"""

import os
import tempfile
import time
from pychronicle.storage.manager import StorageManager


def run_benchmark(count: int, use_memory: bool = False):
    target_type = "In-Memory" if use_memory else "SQLite File (WAL mode)"
    print(f"\n---> Running Benchmark: {count:,} Events [{target_type}]")

    temp_db_path = ":memory:" if use_memory else os.path.join(tempfile.gettempdir(), f"pychronicle_bench_{count}.db")
    if not use_memory and os.path.exists(temp_db_path):
        os.remove(temp_db_path)

    try:
        storage = StorageManager(temp_db_path)
        exec_id = storage.start_execution(f"benchmark_{count}.py")

        # 1. Insertion Benchmark
        t0 = time.perf_counter()
        for i in range(1, count + 1):
            storage.record_event(
                line_number=10 + (i % 25),
                state={
                    "step": i,
                    "accumulator": i * 15,
                    "flag": (i % 2 == 0),
                    "tag": f"val_{i}",
                },
            )
        storage.finish_execution(exec_id)
        insert_time = time.perf_counter() - t0
        insert_rate = count / insert_time

        # 2. Retrieval Benchmark
        t1 = time.perf_counter()
        events = storage.get_events(exec_id)
        read_time = time.perf_counter() - t1
        read_rate = len(events) / read_time

        # 3. Variable Watch Query Benchmark
        t2 = time.perf_counter()
        history = storage.get_variable_history("accumulator", exec_id)
        watch_time = time.perf_counter() - t2

        # 4. Storage Footprint
        file_size_kb = 0.0
        if not use_memory and os.path.exists(temp_db_path):
            file_size_kb = os.path.getsize(temp_db_path) / 1024.0

        storage.close()

        # Display Results
        print(f"  • Insert Time      : {insert_time:.4f} s ({insert_rate:,.0f} events/sec)")
        print(f"  • Read Time (All)  : {read_time:.4f} s ({read_rate:,.0f} events/sec)")
        print(f"  • Watch Query Time : {watch_time:.4f} s (Retrieved {len(history):,} points)")
        if not use_memory:
            print(f"  • Database Size    : {file_size_kb:,.1f} KB ({file_size_kb / count:.2f} KB/event)")

        return {
            "count": count,
            "insert_time": insert_time,
            "insert_rate": insert_rate,
            "read_time": read_time,
            "read_rate": read_rate,
            "size_kb": file_size_kb,
        }

    finally:
        if not use_memory and os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except OSError:
                pass


def main():
    print("=" * 65)
    print("  PyChronicle — Mid-Project Storage Performance Benchmark")
    print("=" * 65)

    # Benchmark 1: 1,000 events
    res_1k = run_benchmark(1_000, use_memory=False)

    # Benchmark 2: 10,000 events
    res_10k = run_benchmark(10_000, use_memory=False)

    print("\n" + "=" * 65)
    print("  Benchmark Summary")
    print("=" * 65)
    print(f"1,000 Events  : {res_1k['insert_rate']:,.0f} inserts/sec | Read: {res_1k['read_rate']:,.0f} reads/sec")
    print(f"10,000 Events : {res_10k['insert_rate']:,.0f} inserts/sec | Read: {res_10k['read_rate']:,.0f} reads/sec")
    print("=" * 65)


if __name__ == "__main__":
    main()
