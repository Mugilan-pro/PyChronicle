# PyChronicle — AST-Powered Time-Travel Debugger

> **Member 3: Storage & Delta Subsystem**

PyChronicle is an execution tracer and time-travel debugger for Python. It uses Abstract Syntax Trees (`ast`) and Python's runtime tracing (`sys.settrace`) to record line execution and variable mutations into SQLite, enabling a Textual Terminal UI (TUI) to scrub backward and forward through program history without restarting execution.

---

## Storage & Delta Subsystem Overview

The storage subsystem serves as the core persistence engine:
- **`pychronicle.storage.models`**: In-memory domain objects (`ExecutionRecord`, `TraceEvent`, `VariableState`).
- **`pychronicle.storage.database`**: SQLite engine using Write-Ahead Logging (WAL), indexed sequence ordering, and atomic transactions.
- **`pychronicle.storage.serializer`**: Safe JSON serializer with object ID cycle-detection and graceful fallbacks for unpicklable types.
- **`pychronicle.storage.delta`**: Delta compression calculator (`StateDelta`, `DeltaCalculator`), cutting storage footprint by ~90%.
- **`pychronicle.storage.reconstructor`**: Dynamic historical state replayer and keyframe checkpoint hydration.
- **`pychronicle.storage.manager`**: High-level facade for teammates (`start_execution`, `record_event`, `get_events`, `get_variable_history`, `reconstruct_state`).
- **`pychronicle.storage.mock_tracer`**: Standalone fake event generator for independent verification.
- **`pychronicle.cli`**: Command-line interface (`pychronicle run`, `pychronicle info`, `pychronicle view`).

---

## Quickstart & Verification

### 1. Weeks 1 & 2 Storage Foundation Demo
```bash
python demo_phase1_phase2.py
```

### 2. Weeks 3 & 4 Delta Compression & CLI Demo
```bash
python demo_weeks3_and_4.py
```

### 3. Run the Automated Test Suite (All 9 Test Modules)
```bash
python -m pytest -v
```

### 4. Run the 1k & 10k Event Benchmark
```bash
python benchmark.py
```

### 5. Using the PyChronicle CLI
```bash
# Trace any Python script with delta compression
python -m pychronicle run my_script.py --db trace.db

# Inspect recorded database sessions
python -m pychronicle info trace.db

# View chronological execution timeline
python -m pychronicle view trace.db --limit 10

# Watch a specific variable across time
python -m pychronicle view trace.db --var my_var
```

---

## Documentation
- See [STORAGE_DOCS.md](STORAGE_DOCS.md) for full architecture and teammate integration contracts.
- See [TEAM_LEAD_EXPLANATION.txt](TEAM_LEAD_EXPLANATION.txt) for conceptual breakdowns and design rationale.
- See [PyChronicle_Review_Script.pdf](PyChronicle_Review_Script.pdf) for the complete presentation guide and flowcharts.
