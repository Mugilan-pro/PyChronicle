# PyChronicle — Terminal UI Documentation (Weeks 1 & 2)

**Author:** Member 4 (Terminal UI)  
**Phase:** Weeks 1 & 2  
**Tech:** Python 3.12, Textual 8.x, Rich 15.x, Pytest  

---

## 1. Overview

PyChronicle's Terminal UI gives developers a visual dashboard to inspect Python script execution step-by-step. It reads trace events and variable states recorded in SQLite by Member 3's storage engine and displays them in a split-pane terminal interface.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 PyChronicleApp (Main Application)                           │
├───────────────────────────────────────┬─────────────────────────────────────┤
│          CodeViewer Pane (58%)        │        Variable State Pane (42%)    │
│  - Python syntax highlighting         │  - Real-time variable table         │
│  - Active line pointer & highlight    │  - Variable types & values          │
│  - Viewport auto-scroll               │  - Mutation indicators (MOD, NEW)   │
│  - Missing file fallback handling     │  - Search / filter input            │
├───────────────────────────────────────┴─────────────────────────────────────┤
│                    Timeline Slider Control (Bottom Scrubber)                │
│  - Step count and progress percentage: [ Step 4 / 20 ] (20%)                │
│  - Scrubber track: [====>-----------------------------]                     │
│  - Buttons: [⏮ First] [◀ Prev] [▶ Play / ⏸ Pause] [Next ▶] [Last ⏭]         │
│  - Event details: Line | Function | Event Type                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Components

### `PyChronicleApp` (`pychronicle.ui.app`)
The top-level Textual application widget.
- Initializes the dual-column layout and bottom timeline dock.
- Loads trace events using `StorageManager.get_events()`.
- Catches `TimelineControl.StepChanged` messages and updates both `CodeViewer` and `VariableViewer`.
- If started without arguments, loads the bundled sample script (`sample_scripts/demo_algorithm.py`) so it runs immediately.

### `CodeViewer` (`pychronicle.ui.code_viewer`)
Displays Python source code with syntax highlighting and line tracking.
- Uses `rich.syntax.Syntax` with the Monokai theme.
- Highlights the current executing line number.
- Calls `scroll_to()` to keep the active line centered in the viewport as code executes.
- If the script file is missing from disk, shows an informational message instead of crashing.

### `TimelineControl` (`pychronicle.ui.timeline`)
The bottom scrubber bar.
- Shows current step, total steps, and a visual progress track.
- Provides step buttons (`First`, `Prev`, `Play/Pause`, `Next`, `Last`).
- Supports autoplay with adjustable playback speed (`0.5x`, `1x`, `2x`, `4x`).
- Emits `StepChanged` whenever the step changes.

### `VariableViewer` (`pychronicle.ui.variable_viewer`)
Displays local variables in a Textual `DataTable`.
- Shows columns: status (`Δ`), variable name, type, current value, and delta.
- Compares values against the previous step:
  * `✨ MOD`: Value changed at this line (shows `was X -> Y`).
  * `🆕 NEW`: Variable initialized for the first time in this scope.
  * `·`: Unchanged.
- Search filter bar allows filtering variables by name or type.

### `HelpModal` (`pychronicle.ui.modals`)
Simple modal dialog showing keyboard shortcuts. Dismissed with `Esc` or `Enter`.

---

## 3. Keyboard Shortcuts

| Key | Action | Description |
| :--- | :--- | :--- |
| `Right` / `l` | `step_forward` | Step forward 1 event |
| `Left` / `h` | `step_backward` | Step backward 1 event |
| `Home` / `g` | `jump_start` | Jump to step 1 |
| `End` / `G` | `jump_end` | Jump to last step |
| `Space` / `p` | `toggle_play` | Toggle autoplay playback |
| `f` | `focus_filter` | Focus variable filter search bar |
| `?` | `show_help` | Open help modal |
| `q` / `Ctrl+C` | `quit` | Exit application |

---

## 4. Tests

Tests are run using `pytest` and `pytest-asyncio` with Textual's async test pilot:

- `tests/test_ui_week1_week2.py`: 5 tests verifying Week 1 & 2 requirements (app mount, code view pane, timeline slider, storage contract, and fallback handling).
- `tests/test_ui.py`: 9 tests verifying navigation, autoplay, stepping boundaries, diff highlighting, filtering, and modals.
- Plus 26 storage tests from Member 3.

**Total:** 40 passed in ~2.3 seconds.

---

## 5. Running the Application

### Interactive Demo
```bash
python demo_week1_week2_tui.py
```

### Inspect an Existing SQLite Trace File
```bash
python run_tui.py --db trace.db
```

### Run Tests
```bash
pytest -v tests/
```
