# PyChronicle — AST-Powered Time-Travel Debugger

> **Member 3: Storage & Delta Subsystem**

PyChronicle is an execution tracer and time-travel debugger for Python. It uses Abstract Syntax Trees (`ast`) and Python's runtime tracing (`sys.settrace`) to record line execution and variable mutations into SQLite, enabling a Textual Terminal UI (TUI) to scrub backward and forward through program history without restarting execution.

---

## Storage Subsystem Overview

The storage subsystem serves as the core persistence engine:
- **`pychronicle.storage.models`**: In-memory domain objects (`ExecutionRecord`, `TraceEvent`, `VariableState`).
- **`pychronicle.storage.database`**: SQLite engine using Write-Ahead Logging (WAL), indexed sequence ordering, and atomic transactions.
- **`pychronicle.storage.serializer`**: Safe JSON serializer with object ID cycle-detection and graceful fallbacks for unpicklable types.
- **`pychronicle.storage.manager`**: High-level facade for teammates (`start_execution`, `record_event`, `get_events`, `get_variable_history`).
- **`pychronicle.storage.mock_tracer`**: Standalone fake event generator for independent verification.

---

## Quickstart & Verification

### 1. Run the Interactive Time-Travel Demo
```bash
python demo_phase1_phase2.py
```

### 2. Run the Automated Test Suite
```bash
python -m pytest -v
```

### 3. Run the 1k & 10k Event Benchmark
```bash
python benchmark.py
```

---

## Documentation
- See [STORAGE_DOCS.md](STORAGE_DOCS.md) for full architecture and teammate integration contracts.
- See [TEAM_LEAD_EXPLANATION.txt](TEAM_LEAD_EXPLANATION.txt) for conceptual breakdowns and design rationale.
