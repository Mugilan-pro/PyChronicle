# PyChronicle — AST-Powered Time-Travel Debugger

PyChronicle is an execution tracer and time-travel debugger for Python that records runtime events and variable states into SQLite, allowing developers to step through code execution history inside an interactive, full-featured terminal dashboard.

This repository contains the complete **4-Week implementation** for **Member 4 (Terminal UI & CLI Packaging)**.

---

## Deliverables Summary (Weeks 1–4)

- **Week 1: Storage Schema Integration Contract**
  - Consumes SQLite execution traces (`execution_id`, `line_number`, `timestamp`, `state`).
  - Queries chronological variable history for time-travel lookups.
- **Week 2: TUI Layout & Scaffolding**
  - Dual-pane layout: 58% code pane, 42% variables/watches pane, and bottom scrubber dock.
  - `CodeViewer`: Python syntax highlighting (Monokai), line pointer, and auto-scrolling viewport centering.
  - `TimelineControl`: Scrubber bar with step counter, percentage indicator, step navigation, and autoplay engine (`0.5x`–`4x`).
- **Week 3: Time-Scrubbing & Differential State Inspection**
  - Synchronizes scrubber events to SQLite storage.
  - Differential state analysis: `✨ MOD` (with "was X ➔ Y"), `🆕 NEW` for newly initialized variables, and `·` for unchanged state.
  - Priority sorting: Mutated and new variables are automatically hoisted to the top.
  - Real-time search filter for variable names and types.
- **Week 4: Watch Variables, Time-Travel Jumps & CLI Packaging**
  - `WatchViewer`: Dedicated tracking panel displaying watched variables and mutation badges (`#seq: val`).
  - **Click-to-Jump Time Travel:** Clicking any historical mutation badge immediately rewinds or advances the entire debugger to that point in execution.
  - `AddWatchModal` with current-scope variable auto-suggestions (`w` key) and `HelpModal` (`?` key).
  - CLI Packaging: `pychronicle run <script>`, `pychronicle view <db>`, and `pychronicle demo`.

---

## Quickstart

### 1. Setup Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Full 4-Week Interactive Demo
```bash
python demo_all_weeks.py
```
*(On macOS, you can also double-click `run.command` directly).*

### 3. Run the CLI
```bash
# Launch interactive demo
python -m pychronicle demo

# Trace and debug your own script
python -m pychronicle run sample_scripts/demo_algorithm.py

# Inspect an existing SQLite trace database
python -m pychronicle view trace.db
```

### 4. Run the Test Suite
```bash
pytest -v tests/
```

---

## Keyboard Controls

| Key | Action | Description |
| :--- | :--- | :--- |
| `Right` / `l` | `step_forward` | Step forward 1 event |
| `Left` / `h` | `step_backward` | Step backward 1 event |
| `Home` / `g` | `jump_start` | Jump to start (Step 1) |
| `End` / `G` | `jump_end` | Jump to last step |
| `Space` / `p` | `toggle_play` | Toggle autoplay playback |
| `w` | `add_watch` | Open Add Watch Variable modal dialog |
| `f` | `focus_filter` | Focus variable search filter |
| `?` | `show_help` | Show keyboard shortcuts modal |
| `q` / `Ctrl+C` | `quit` | Cleanly exit PyChronicle |

---

## Project Structure

```text
pychronicle/
  ├── __init__.py
  ├── __main__.py             # Entry point for python -m pychronicle
  ├── cli.py                  # CLI commands: run, view, demo
  ├── ui/                     # Member 4: Terminal UI implementation
  │   ├── __init__.py         # Exported UI classes
  │   ├── app.py              # Main PyChronicleApp orchestrator
  │   ├── code_viewer.py      # CodeViewer with Monokai syntax highlighting
  │   ├── timeline.py         # TimelineControl scrubber & autoplay engine
  │   ├── variable_viewer.py  # VariableViewer with diff badges & filter
  │   ├── watch_viewer.py     # WatchViewer with mutation badges & time-jump
  │   └── modals.py           # AddWatchModal and HelpModal screens
  └── storage/                # Member 3: SQLite storage engine backend
tests/
  ├── test_cli.py             # CLI tests (run, view, demo, args)
  ├── test_ui.py              # 11 asynchronous Textual UI tests (Weeks 1-4)
  ├── test_ui_week1_week2.py  # Scaffolding & fallback tests
  └── test_*.py               # Storage backend tests
demo_all_weeks.py             # Complete 4-week interactive demo launcher
demo_week1_week2_tui.py       # Weeks 1 & 2 scaffolding demo launcher
run_tui.py                    # Customizable TUI launcher script
run.command                   # macOS 1-click launcher
pyproject.toml                # Package configuration & console scripts
requirements.txt              # Project dependencies
UI_DOCS.md                    # In-depth architectural documentation
```

---

## Test Verification

```text
tests/test_cli.py .............................. 7 passed
tests/test_database.py ......................... 7 passed
tests/test_integration.py ...................... 2 passed
tests/test_manager.py .......................... 7 passed
tests/test_models.py ........................... 3 passed
tests/test_performance.py ...................... 1 passed
tests/test_serializer.py ....................... 6 passed
tests/test_ui.py ............................... 11 passed
tests/test_ui_week1_week2.py ................... 5 passed
========================= 49 passed in ~2.9s =========================
```
