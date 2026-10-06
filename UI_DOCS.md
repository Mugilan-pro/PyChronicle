# PyChronicle — Terminal UI & CLI Architecture Documentation (Weeks 1–4)

**Role:** Member 4 — Terminal UI (Textual) & CLI Packaging  
**Project:** PyChronicle (AST-Powered Time-Travel Debugger)  
**Tech Stack:** Python 3.12, Textual 8.x, Rich 15.x, Pytest 9.x  

---

## 1. Executive Summary & Deliverables

PyChronicle's Terminal UI gives developers a visual dashboard to inspect Python program execution step-by-step. It reads trace events and serialized variable states recorded in SQLite by Member 3's storage engine and presents them inside a synchronized, responsive terminal interface.

Over the 4-week development cycle, Member 4 has delivered:
- **Week 1:** Storage schema integration contract consuming `execution_id`, `line_number`, `timestamp`, `state` snapshots, and chronological variable history from the SQLite backend.
- **Week 2:** TUI layout scaffolding combining a dual-pane workspace (58% code pane, 42% state & watch pane) and a bottom timeline dock. Implemented `CodeViewer` with syntax highlighting and program counter auto-scroll, plus `TimelineControl` with interactive step buttons and autoplay engine.
- **Week 3:** Time-scrubbing synchronization and differential state inspection. Calculated real-time delta markers (`✨ MOD` with "was X ➔ Y", `🆕 NEW` for initializations, and `·` for unchanged values) with priority sorting and search filtering.
- **Week 4:** Watch Variables panel (`WatchViewer`), mutation timeline badges, click-to-jump historical time-travel, `AddWatchModal` dialog with current-scope variable auto-suggestions, `HelpModal`, and CLI packaging (`pychronicle run`, `pychronicle view`, `pychronicle demo`).

---

## 2. Terminal UI Layout Architecture

The application layout is structured cleanly using Textual containers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Header (PyChronicle — Time-Travel Debugger)                      [Clock]    │
├───────────────────────────────────────┬─────────────────────────────────────┤
│         CodeViewer Pane (58%)         │      VariableViewer Pane (55% top)  │
│  - Python syntax highlighting         │  - Real-time variable table         │
│  - Active program counter highlight   │  - Status (Δ), Var, Type, Value     │
│  - Monokai color theme                │  - Mutation Delta (was A ➔ B)       │
│  - Centering auto-scroll              │  - Real-time filter search bar      │
│  - Missing file fallback handling     ├─────────────────────────────────────┤
│                                       │       WatchViewer Pane (45% bottom) │
│                                       │  - Tracked variables list           │
│                                       │  - Current scope value              │
│                                       │  - Interactive mutation badges:     │
│                                       │    [#1: 0] [#2: 1] [#3: 2] ...      │
│                                       │  - Click badge to jump back in time │
│                                       │  - [+ Add Watch] / [✕ Remove]       │
├───────────────────────────────────────┴─────────────────────────────────────┤
│                    TimelineControl Dock (Bottom Scrubber)                   │
│  - Step count and progress badge: [ Step 4 / 20 ] (20%)                     │
│  - Interactive track: [====>----------------------------------------------] │
│  - Controls: [⏮ First] [◀ Prev] [▶ Play / ⏸ Pause] [Next ▶] [Last ⏭] [1.0x]│
│  - Event metadata: Line 13 | Function: compute_fibonacci_stats | STEP       │
├─────────────────────────────────────────────────────────────────────────────┤
│ Footer (q: Quit | h/l: Step | g/G: Jump | Space: Play | w: Watch | f: Filter)│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Component Breakdown

### 3.1 `PyChronicleApp` (`pychronicle.ui.app`)
The top-level Textual application orchestrator.
- **Data Binding:** Connects to `StorageManager` (either an active session, an existing `.db` file, or an in-memory session).
- **Event Dispatch:** Catches messages from child widgets (`StepChanged`, `JumpToStep`, `VariableSelected`, `RequestAddWatch`) and coordinates updates across panes.
- **Demo Fallback:** Bundles a self-contained algorithm trace (`sample_scripts/demo_algorithm.py`) so evaluator runs require zero configuration.
- **Keybindings:** Global shortcuts for stepping (`Left`/`h`, `Right`/`l`), jumping (`Home`/`g`, `End`/`G`), autoplay (`Space`/`p`), watching (`w`), filtering (`f`), and help (`?`).

### 3.2 `CodeViewer` (`pychronicle.ui.code_viewer`)
Displays Python source code with syntax highlighting and program counter tracking.
- **Renderer:** Uses `rich.syntax.Syntax` with the Monokai theme and explicit line numbers.
- **Program Counter:** Highlights the line corresponding to the current execution event.
- **Viewport Auto-Scroll:** Centers the active line in the viewport as code steps forward or backward.
- **Defensive Fallback:** If the source script is unavailable or moved, renders a clean fallback banner without crashing.

### 3.3 `TimelineControl` (`pychronicle.ui.timeline`)
The interactive execution scrubber bar.
- **State Display:** Shows `Step X / Total`, percentage complete, and an ASCII track bar.
- **Navigation Controls:** First (`⏮`), Prev (`◀`), Play/Pause (`▶`/`⏸`), Next (`▶`), and Last (`⏭`).
- **Autoplay Engine:** Background timer that steps forward automatically with selectable playback speeds (`0.5x`, `1.0x`, `2.0x`, `4.0x`). Automatically pauses when reaching the end of the trace.
- **Clamping:** Safely bounds navigation between step 1 and the total number of events.

### 3.4 `VariableViewer` (`pychronicle.ui.variable_viewer`)
Interactive variable inspection table with differential state analysis.
- **Data Columns:** Status badge (`Δ`), Variable name, Type, Current Value, and Mutation Delta.
- **Differential Detection:**
  * `✨ MOD`: Variable changed value in this step (displays `was OldValue ➔ NewValue`).
  * `🆕 NEW`: Variable initialized for the first time in the active scope.
  * `·`: Unchanged variable state.
- **Priority Sorting:** Sorts mutated and newly initialized variables to the top of the table for immediate visibility.
- **Real-Time Filter:** Instant search box filtering variables by name or type.
- **Row-to-Watch Integration:** Clicking any variable row immediately adds it to the Watch Variables panel.

### 3.5 `WatchViewer` (`pychronicle.ui.watch_viewer`)
Specialized tracking panel for developer-selected variables across execution time.
- **Watch Cards:** Displays watched variable name, active value (or `(out of scope)`), and total mutation count.
- **Chronological History Badges:** Renders interactive badges for each recorded mutation (e.g., `[#1: 0]`, `[#2: 1]`, `[#3: 2]`).
- **Click-to-Jump Time Travel:** Clicking any mutation badge emits a `JumpToStep` message, rewinding or fast-forwarding the timeline, code viewer, and variable table directly to that step.
- **Management:** Add variables via modal or remove them via the `✕` button.

### 3.6 Modals (`pychronicle.ui.modals`)
- **`AddWatchModal`:** Centered popup dialog with an input field and clickable suggestion buttons listing all variables in the current execution scope.
- **`HelpModal`:** Modal cheat sheet listing all keyboard shortcuts and navigation tips.

---

## 4. CLI Packaging & Commands (`pychronicle.cli`)

PyChronicle includes a unified command-line entry point:

```bash
# 1. Trace and debug any Python script directly
pychronicle run path/to/script.py

# 2. Inspect a pre-recorded SQLite trace database
pychronicle view path/to/trace.db [--exec-id ID] [--script path/to/code.py]

# 3. Launch the full interactive 4-week demo
pychronicle demo

# 4. View help
pychronicle --help
```

Package distribution configuration is maintained in `pyproject.toml` with console scripts mapped to `pychronicle.cli:main`.

---

## 5. Keyboard Navigation Reference

| Key Binding | Action Name | Function |
| :--- | :--- | :--- |
| `Right` / `l` | `step_forward` | Step forward 1 execution event |
| `Left` / `h` | `step_backward` | Step backward 1 execution event |
| `Home` / `g` | `jump_start` | Jump immediately to Step 1 (Start) |
| `End` / `G` | `jump_end` | Jump immediately to the final event |
| `Space` / `p` | `toggle_play` | Toggle automatic playback (Play / Pause) |
| `w` | `add_watch` | Open the Add Watch Variable modal dialog |
| `f` | `focus_filter` | Focus the variable search filter input |
| `?` | `show_help` | Open the keyboard shortcuts help screen |
| `q` / `Ctrl+C` | `quit` | Cleanly close storage and exit PyChronicle |

---

## 6. Test Suite & Verification

The test suite validates UI rendering, user actions, storage contracts, and CLI commands:

- `tests/test_cli.py`: 7 tests covering `--help`, `demo`, `view`, `run`, error handling for missing files, and argument parsing.
- `tests/test_ui.py`: 11 asynchronous tests covering widget mounting, code line highlighting, timeline boundary clamping, autoplay and speed cycling, differential variable inspection, search filtering, watch variable addition/removal/history, click jumps, modals, and empty-trace handling.
- `tests/test_ui_week1_week2.py`: 5 tests validating core scaffolding and fallback states.
- Storage & serialization tests: 26 unit tests covering SQLite tables, transactions, models, and JSON serialization.

**Total Test Count:** 49 tests passing with 100% success rate.
