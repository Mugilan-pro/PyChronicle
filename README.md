# PyChronicle — AST-Powered Time-Travel Debugger

> **Subsystem Focus: Storage & Delta Engine (Member 3)**  
> **Production-grade, zero-SQL persistence layer with Delta Compression and Safe State Serialization.**

PyChronicle is an execution tracer and time-travel debugger for Python. By combining Abstract Syntax Trees (`ast`) with runtime tracing hooks (`sys.settrace`), it captures line-by-line execution and variable mutations into SQLite. This enables developers and interactive frontends (such as Textual TUI) to navigate backward and forward through execution history without restarting the target process.

---

## 🏛️ Subsystem Architecture

The **Storage & Delta Subsystem** serves as the central data backbone of PyChronicle:

```text
┌────────────────────────────────────────────────────────┐
│             Tracer Engine (sys.settrace)               │
└──────────────────────────┬─────────────────────────────┘
                           │ record_event(line, frame.f_locals)
                           ▼
┌────────────────────────────────────────────────────────┐
│                     StorageManager                     │
│         (Session, Monotonic Sequence, Facade)          │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
        [Raw Objects]              [State Diffs]
               ▼                          ▼
┌──────────────────────────────┐   ┌──────────────────────────────┐
│       ValueSerializer        │   │    DeltaCalculator (W3)      │
│  - id(obj) Cycle Detection   │   │  - State mutations & diffs   │
│  - Depth & Length Bounds     │   │  - Keyframe snapshots        │
│  - Safe JSON Type Fallbacks  │   │  - StateReconstructor        │
└──────────────┬───────────────┘   └──────────────┬───────────────┘
               │                                  │
               └─────────────────┬────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────┐
│                   Database Engine                      │
│   - SQLite WAL (Write-Ahead Logging)                   │
│   - Foreign Keys & ON DELETE CASCADE                   │
│   - Monotonic UNIQUE(execution_id, sequence)           │
│   - Parameterized SQL & Batch IN (...) Optimization    │
└────────────────────────┬───────────────────────────────┘
                         ▼
             [ SQLite Database File / Memory ]
```

---

## 📅 4-Week Engineering Roadmap & Deliverables

### **Week 1: Core Storage Engine & Schema Design**
* **Normalized Relational Schema**: 
  * `executions`: Tracks debug sessions, script metadata, and run duration.
  * `trace_events`: Chronological execution steps with deterministic monotonic sequencing.
  * `variable_states`: Individual variable captures linked via foreign keys.
* **Deterministic Replay Guarantee**: Implemented `UNIQUE(execution_id, sequence)` constraint, eliminating timestamp collision issues during rapid loop executions.
* **Performance Pragmas**: Activated Write-Ahead Logging (`WAL`), `foreign_keys = ON`, and `synchronous = NORMAL` for high-throughput concurrency.

### **Week 2: Safe Value Serialization & Facade API**
* **Safe Serialization Engine (`serializer.py`)**:
  * Prevents infinite recursion via active `seen_ids = set()` object identity tracking.
  * Caps collection depth and string length to prevent memory exhaustion.
  * Gracefully handles unpicklable objects (open files, network sockets, functions, threads) using structured fallback descriptors.
* **StorageManager Facade (`manager.py`)**: Zero-SQL public API for team members (`start_execution`, `record_event`, `finish_execution`, `get_events`, `get_variable_history`).
* **Mock Tracer (`mock_tracer.py`)**: Standalone synthetic event generator for decoupled verification.

### **Week 3: Delta Compression & State Reconstruction**
* **Delta Calculator (`delta.py`)**: Computes exact mutations (`added`, `modified`, `deleted`) between consecutive execution steps.
* **Keyframe Checkpoint Strategy**: Stores full snapshots at configurable intervals (e.g., every 50 steps), storing lightweight diffs for intermediate steps.
* **Storage Footprint Reduction**: Achieves **~80% reduction** in variable row storage overhead compared to naive full snapshotting.
* **Dynamic State Reconstruction (`reconstructor.py`)**: Replays deltas forward from the nearest keyframe checkpoint to instantly hydrate complete historical state for any arbitrary event.

### **Week 4: CLI Packaging, Watchpoints & Benchmarking**
* **CLI Tool Suite (`cli.py`, `pyproject.toml`)**:
  * `pychronicle run <script>`: Executes and traces target scripts with automatic delta compression.
  * `pychronicle info <db>`: Displays session statistics, event counts, and run duration.
  * `pychronicle view <db>`: Renders terminal timeline replay and watchpoint history.
* **Variable Watchpoints**: Fast indexed queries retrieving the historical progression of specific variables across time.
* **High-Throughput Benchmarks**: Measured **>20,000 inserts/sec** and **>80,000 reads/sec**.

---

## 🚀 Quickstart & Demonstrations

### 1. Chronological Time-Travel Playback
Demonstrates recording execution steps and replaying the timeline with variable history:
```powershell
python example_time_travel.py
```

### 2. Delta Compression & State Reconstruction
Demonstrates the ~80% storage savings and on-demand state reconstruction at Step 15:
```powershell
python example_delta_compression.py
```

### 3. Trace a Target Script using the CLI
Trace the included banking transaction sample [`sample_calc.py`](sample_calc.py):
```powershell
# Trace script and save to SQLite
python -m pychronicle run --db my_trace.db sample_calc.py

# Inspect trace metadata
python -m pychronicle info my_trace.db

# View chronological timeline
python -m pychronicle view my_trace.db --limit 10

# Watch a specific variable across execution
python -m pychronicle view my_trace.db --var balance
```

### 4. Run the Performance Benchmark
Evaluates database throughput over 1,000 and 10,000 synthetic events:
```powershell
python benchmark.py
```

---

## 🧪 Automated Test Suite

PyChronicle features an automated test suite with **35 passing tests** across 9 dedicated test modules:

```powershell
python -m pytest -v
```

| Test Module | Focus Area | Status |
| :--- | :--- | :---: |
| `tests/test_models.py` | Dataclass schemas and default values | PASSED |
| `tests/test_database.py` | WAL mode, foreign keys, monotonic ordering | PASSED |
| `tests/test_serializer.py` | Cycle detection, unpicklable fallbacks, depth limits | PASSED |
| `tests/test_manager.py` | StorageManager API lifecycle & session handling | PASSED |
| `tests/test_delta.py` | State delta calculations, additions, deletions | PASSED |
| `tests/test_reconstructor.py`| Delta compression ratio & state hydration accuracy | PASSED |
| `tests/test_integration.py` | Tracer-to-storage pipeline and disk persistence | PASSED |
| `tests/test_performance.py` | 1,000 event throughput benchmarks | PASSED |
| `tests/test_cli.py` | CLI argument parsing, run, info, and view commands | PASSED |

---

## 📂 Subsystem File Structure

```text
├── pychronicle/
│   ├── __init__.py               # Package metadata
│   ├── __main__.py               # CLI direct execution entrypoint
│   ├── cli.py                    # CLI commands: run, info, view
│   └── storage/
│       ├── __init__.py           # Clean storage module exports
│       ├── models.py             # ExecutionRecord, TraceEvent, VariableState
│       ├── database.py           # SQLite engine, schema, indexed queries
│       ├── serializer.py         # Cycle-safe JSON value serializer
│       ├── delta.py              # Delta calculation engine (Week 3)
│       ├── reconstructor.py      # State hydration from keyframes (Week 3)
│       ├── manager.py            # StorageManager unified facade
│       └── mock_tracer.py        # Synthetic trace event generator
├── tests/                        # 9 comprehensive test modules (35 tests)
├── example_time_travel.py        # Playback & watchpoints demonstration
├── example_delta_compression.py  # Delta compression & reconstruction demo
├── sample_calc.py                # Target script for CLI tracing
├── benchmark.py                  # 1k & 10k throughput benchmark
├── my_trace.db                   # Active trace database (viewable in SQLite Viewer)
├── STORAGE_DOCS.md               # Technical specifications & API contract
├── pyproject.toml                # Build configuration and CLI entry point
└── README.md                     # Project overview and documentation
```

---

## 📖 Technical Documentation

For detailed schema specifications, indexing strategy, and teammate integration contracts, refer to:
* [`STORAGE_DOCS.md`](STORAGE_DOCS.md) — Comprehensive technical reference and API documentation.
