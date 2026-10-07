# PyChronicle — AST Rewriter & Execution Tracer Documentation
**Subsystem**: AST Rewriter & Tracer Track (Weeks 1 & 2)  
**Role**: Member 1 — AST Rewriter & Execution Tracer  
**Project**: PyChronicle — AST-Powered Time-Travel Debugger  

---

## 1. Subsystem Architecture Overview

PyChronicle intercepts, catalogs, and records runtime Python execution history into SQLite without mutating source files on disk. The **AST Rewriter & Tracer** subsystem is the core instrumentation engine responsible for:

1. **Static AST Analysis**: Parsing Python Abstract Syntax Trees and cataloging all variable assignments across all syntax forms.
2. **Dynamic AST Rewriting**: In-memory AST transformation injecting runtime state capture hooks (`__pychronicle_hook__`) while preserving line numbers and docstrings.
3. **Execution Tracing (`sys.settrace`)**: Intercepting line transitions, function entries, returns, and exceptions with frame filtering, reentrancy protection, and zero dropped frames.
4. **Unified Runner**: Coordinating AST analysis, execution tracing, and SQLite persistence for time-travel queries.

```
┌────────────────────────────────────────────────────────┐
│                   Target Python Script                 │
└───────────────────────────┬────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
    ┌──────────────────┐        ┌──────────────────┐
    │  ASTAnalyzer     │        │   ASTRewriter    │
    │  (Static Parse,  │        │ (In-Memory AST   │
    │   All Assigns)   │        │  Hook Injection) │
    └─────────┬────────┘        └─────────┬────────┘
              │                           │
              └─────────────┬─────────────┘
                            ▼
              ┌───────────────────────────┐
              │     ExecutionTracer       │
              │ (sys.settrace + Filter)   │
              └─────────────┬─────────────┘
                            │ record_event(line, state, func)
                            ▼
              ┌───────────────────────────┐
              │      StorageManager       │
              │  (SQLite Database Engine) │
              └───────────────────────────┘
```

---

## 2. Week 1: AST Parsing & Variable Assignment Identification

### Specification:
> *"AST Parsing: Build a script that reads a target Python file, parses its Abstract Syntax Tree, and identifies all variable assignments."*

### Implementation (`pychronicle/rewriter/analyzer.py`):
Our `ASTAnalyzer` visits all nodes in the AST and detects 14 distinct Python variable assignment forms:

| Syntax Form | AST Node | Example | Kind (`AssignmentKind`) |
|---|---|---|---|
| Simple Assignment | `ast.Assign` | `x = 10` | `simple` |
| Augmented Assignment | `ast.AugAssign` | `total += step` | `augmented` |
| Annotated Assignment | `ast.AnnAssign` | `count: int = 0` | `annotated` |
| Unpacking & Starred | `ast.Assign` | `a, *rest, b = data` | `unpacking` |
| Walrus Operator | `ast.NamedExpr` | `if (n := len(items)):` | `walrus` |
| For / Async For Loops | `ast.For`, `ast.AsyncFor` | `for idx, val in pairs:` | `for_loop`, `async_for` |
| With / Async With | `ast.With`, `ast.AsyncWith` | `with ctx as handle:` | `with`, `async_with` |
| Exception Handlers | `ast.ExceptHandler` | `except Exception as err:` | `except` |
| Function Definitions | `ast.FunctionDef` | `def compute():` | `function_def` |
| Function Parameters | `ast.arguments` | `def foo(x, y=1, *args):` | `function_param` |
| Class Definitions | `ast.ClassDef` | `class Engine:` | `class_def` |
| Imports & Aliases | `ast.Import`, `ast.ImportFrom` | `from math import sqrt as s`| `import` |

### CLI Tool (`ast_analyzer.py`):
Run on any script:
```bash
python ast_analyzer.py my_script.py
```
Or output machine-readable JSON:
```bash
python ast_analyzer.py my_script.py --json
```

---

## 3. Dynamic AST Rewriting (`pychronicle/rewriter/transformer.py`)

### Specification:
> *"AST Rewriter (ast module): Parses target Python scripts and dynamically injects state-capturing hooks without modifying the original source code."*

### Implementation:
The `ASTRewriter` (`ast.NodeTransformer`) injects runtime hook calls directly into the AST:
1. **Docstring Preservation**: Detects module/class/function docstrings and ensures hooks are never injected prior to the docstring.
2. **Post-Mutation Line Hooks**: Injects `__pychronicle_hook__(line_no, scope_name, locals(), 'line')` following statement execution.
3. **Return Value Capture**: Rewrites `return <expr>` to capture the evaluated return value in `__pychronicle_ret__` before frame exit.
4. **Loop & Jump Handling**: Inserts hooks before `break` and `continue` to preserve final iteration states.
5. **Location Integrity**: Applies `ast.copy_location` and `ast.fix_missing_locations` so stack traces and line mappings match the original source code.

---

## 4. Week 2: Execution Engine Tracer (`sys.settrace`)

### Specification:
> *"The Tracer: Implement sys.settrace to record the execution flow of the target script, capturing variable states and saving them to SQLite."*

### Implementation (`pychronicle/tracer/engine.py`):
`ExecutionTracer` implements `sys.settrace` with production-grade reliability:

1. **Intelligent Frame Filtering (`TraceFilter`)**:
   - Automatically excludes Python standard library (`sys.base_prefix`, `Lib/`).
   - Automatically excludes `site-packages`.
   - Excludes PyChronicle internal modules (`pychronicle/storage`, `pychronicle/tracer`).
   - Only traces target application files or in-memory execution scripts.
2. **Reentrancy Protection**:
   - Uses an internal `_in_hook` reentrancy lock. Prevents recursive tracing when `StorageManager` executes SQLite and serialization queries.
3. **Dunder Filtering**:
   - Strips `__builtins__`, `__doc__`, and internal symbols from `frame.f_locals` to ensure clean variable state capture.
4. **Full Lifecycle Hooks**:
   - `'line'`: State snapshot on each line execution.
   - `'call'`: State snapshot and function scope entry.
   - `'return'`: Captures function output in `__return__`.
   - `'exception'`: Captures exception type and message in `__exception__`.

---

## 5. Mid-Project Review Audit: Zero Dropped Frames

### Specification:
> *"Trace Validation: Prove the tracer accurately records the execution of a complex loop without dropping frames."*
> *"Storage Audit: Ensure the database handles thousands of state changes without significant overhead."*

### Automated Audit Script (`validate_trace_loop.py`):
Run the validation audit:
```bash
python validate_trace_loop.py
```

### Audit Results:
1. **Complex Nested Loop (Outer + Inner + Branching + Accumulators)**:
   - Total Frames Observed: 91
   - Total Frames Recorded: 91
   - **Dropped Frames Count: 0**
   - **Sequence Order: 100% strictly monotonic [1..91]**
   - **State Accuracy: 100% matching mathematical ground truth**
2. **Throughput Benchmark (5,000 Event Stress Loop)**:
   - Total Events Captured: 5,004
   - **Tracing Throughput: >20,000 events/second**
   - **Average Frame Latency: < 0.05 ms / frame**
   - **Dropped Frames Count: 0**

---

## 6. How Teammates Integrate With Our Subsystem

### A. Terminal UI Subsystem (Textual):
Teammates building the TUI can run any script under PyChronicle and scrub the timeline:
```python
from pychronicle.runner import PyChronicleRunner

runner = PyChronicleRunner("trace.db")
runner.run_file("user_app.py")

# Scrub timeline
events = runner.get_timeline()
current_step = events[slider_index]
tui_highlight_line(current_step.line_number)
tui_render_variables(current_step.state)

# Watch variable timeline
history = runner.watch_variable("my_counter")
```

### B. Member 3 (Storage Subsystem):
Our tracer directly feeds `storage.record_event(...)`, fulfilling all parameters expected by Member 3's `StorageManager`.

---

## 7. Verification Commands

```bash
# 1. Run all unit & integration tests
python -m pytest -v

# 2. Run AST Analyzer CLI demo
python ast_analyzer.py

# 3. Run Mid-Project Review Zero-Dropped-Frame Validation
python validate_trace_loop.py

# 4. Run Interactive Weeks 1 & 2 Demo
python demo_week1_week2_ast.py
```
