# PyChronicle — Storage & Delta Subsystem Documentation

## 1. Architecture Overview

PyChronicle records runtime variable state at every line of Python execution without modifying source code. The Storage Subsystem provides a clean, zero-SQL interface for the Tracer engine (Member 2) and the Textual TUI (Member 1 & 2).

```
┌─────────────────────────────────┐
│     Tracer Engine (sys.settrace)│
└────────────────┬────────────────┘
                 │ record_event(line_number=10, state={'x': 1})
                 ▼
┌─────────────────────────────────┐
│         StorageManager          │
│   (Session, Sequence, State)    │
└────────┬───────────────┬────────┘
         │               │
         ▼               ▼
┌────────────────┐ ┌──────────────┐
│ValueSerializer │ │   Database   │
│(Cycle Safe,    │ │(SQLite, WAL, │
│ JSON Fallback) │ │ Transactions)│
└────────────────┘ └──────┬───────┘
                          ▼
                   ┌──────────────┐
                   │ SQLite DB    │
                   │ (:memory: or │
                   │  file on disk│
                   └──────────────┘
```

---

## 2. Database Schema

The database design implements a normalized event-and-variable model optimized for fast chronological playback and variable watchpoints.

### `executions`
Tracks execution sessions.
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `script_name`: TEXT NOT NULL
- `started_at`: REAL NOT NULL (Unix timestamp)
- `completed_at`: REAL (Unix timestamp, NULL if running)
- `metadata_json`: TEXT DEFAULT '{}'

### `trace_events`
Tracks each line executed in chronological order.
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `execution_id`: INTEGER NOT NULL (FK -> executions.id ON DELETE CASCADE)
- `sequence`: INTEGER NOT NULL (Monotonic counter: 1, 2, 3...)
- `line_number`: INTEGER NOT NULL
- `function_name`: TEXT NOT NULL DEFAULT '<module>'
- `event_type`: TEXT NOT NULL DEFAULT 'line'
- `timestamp`: REAL NOT NULL
- `is_delta`: INTEGER NOT NULL DEFAULT 0 (Hook for Week 3)
- `UNIQUE(execution_id, sequence)`

### `variable_states`
Stores the serialized value of each variable present at an event.
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `event_id`: INTEGER NOT NULL (FK -> trace_events.id ON DELETE CASCADE)
- `var_name`: TEXT NOT NULL
- `serialized_value`: TEXT NOT NULL
- `value_type`: TEXT NOT NULL DEFAULT 'unknown'

### Indices
- `idx_events_exec_seq ON trace_events(execution_id, sequence)`
- `idx_var_states_event ON variable_states(event_id)`
- `idx_var_states_name ON variable_states(var_name)`

---

## 3. Tracer-Storage API Contract

Teammates interact exclusively with `StorageManager`. No direct SQL queries are needed.

### Core Methods:

```python
from pychronicle.storage import StorageManager

storage = StorageManager("trace.db")  # or ":memory:"

# 1. Start execution
exec_id = storage.start_execution("my_script.py", metadata={"env": "dev"})

# 2. Record events (called inside sys.settrace callback)
storage.record_event(
    line_number=10,
    state={"x": 5, "total": 100},
    function_name="calculate",
)

# 3. Complete execution
storage.finish_execution()

# 4. TUI Time-Travel: Retrieve all events in chronological sequence
events = storage.get_events()
for ev in events:
    print(f"Step {ev.sequence} | Line {ev.line_number} | State: {ev.state}")

# 5. TUI Watch Variable: Query a single variable's timeline
history = storage.get_variable_history("total")
# Returns: [{'sequence': 1, 'line_number': 10, 'value': 100, ...}]
```

---

## 4. Commands to Run Tests and Benchmarks

### Run Unit Tests
```cmd
python -m pytest -v
```

### Run 1k & 10k Performance Benchmark
```cmd
python benchmark.py
```

### Run Interactive Demo
```cmd
python demo_phase1_phase2.py
```
