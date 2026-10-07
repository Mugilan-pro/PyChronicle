# PyChronicle — Week 4 Packaging, CLI & TUI Documentation

**Subsystem**: Packaging, CLI Utility & Terminal User Interface  
**Project**: PyChronicle — Time-Travel Debugger  
**Milestone**: Week 4 Core Engineering & Interface Polish  

---

## 1. Subsystem Overview

Week 4 completes the PyChronicle time-travel debugging system by providing:
1. **Packaging**: Standardized Python packaging via `pyproject.toml` and `setup.py`, installable via `pip install -e .`.
2. **Command Line Interface (`click`)**: Full suite of terminal commands: `run`, `view`, `analyze`, `watch`, and `benchmark`.
3. **Interactive Terminal User Interface (`textual`)**: Hacker-style, responsive TUI with active code highlighting, timeline slider, live delta variable inspector, and interactive watchpoint inspection.
4. **Post-Mortem Crash Time-Travel**: Automatic capture and backward stepping from unhandled runtime exceptions.

---

## 2. CLI Command Reference

### `pychronicle run <SCRIPT> [OPTIONS]`
Instruments and executes a Python target script.
- `--delta / --no-delta`: Enable Week 3 Delta Compression (default: on).
- `--tui / --no-tui`: Launch the interactive Textual TUI (default: on).
- `--db PATH`: SQLite output path (default: `trace.db`).
- `--mode [tracer|rewriter]`: Instrumentation mode (default: `tracer`).

```bash
pychronicle run app.py --db trace.db
```

### `pychronicle view <DB_FILE> [OPTIONS]`
Replays past execution history directly from SQLite without re-running any code.
- `--script PATH`: Optional path to original source file.
- `--exec-id INT`: Target execution session ID (defaults to latest).

```bash
pychronicle view trace.db
```

### `pychronicle analyze <SCRIPT> [OPTIONS]`
Runs Week 1 static AST analysis and prints all 14 assignment syntax forms.
- `--json`: Output machine-readable JSON structure.

```bash
pychronicle analyze complex_script.py
```

### `pychronicle watch <SCRIPT> --var <NAME> [OPTIONS]`
Traces script and outputs a chronological audit table of every mutation to the watched variable.

```bash
pychronicle watch calculations.py --var running_total
```

### `pychronicle benchmark <SCRIPT>`
Runs a 3-way head-to-head benchmark comparing:
1. Raw Python (uninstrumented)
2. Full-State Tracing (Weeks 1-2 baseline)
3. Delta-Compressed Tracing (Week 3)

---

## 3. Terminal User Interface (Textual) Layout & Controls

```
+--------------------------------------------------------------------------+
| PyChronicle — Time-Travel Debugger                               00:15:30|
+------------------------------------+-------------------------------------+
| Source Code Pane                   | Variables Inspector                 |
| (sample_algorithm.py)              | (Active Locals at Step 23/73)       |
|                                    +-------------------------------------+
|   1  def sieve_primes(max_val):    | Variable | Type | Value     | Delta |
|   2      primes = []               | primes   | list | [2, 3, 5] | MOD   |
| ▶ 3      is_prime = [True] * ...   | p        | int  | 5         | NEW   |
|   4                                +-------------------------------------+
|   5      for p in range(2, max_val)| Watch Variable Timeline             |
|                                    | (Track variable mutations over time)|
|                                    | Step 12: primes = [2]               |
|                                    | Step 18: primes = [2, 3]            |
|                                    | Step 23: primes = [2, 3, 5]         |
+------------------------------------+-------------------------------------+
| Timeline Scrubber: [===============>                  ] Step 23/73  31.5%|
| Scope: sieve_primes() | Event: LINE | Status: PAUSED                     |
| [⏮ Start] [◀ Back] [▶ Play] [Fwd ▶] [End ⏭]                             |
+--------------------------------------------------------------------------+
| [h] Step Back | [l] Step Fwd | [Space] Play/Pause | [w] Watch Var | [q]  |
+--------------------------------------------------------------------------+
```

### Keybindings:
- `h` / `Left`: Step backward 1 frame in time.
- `l` / `Right`: Step forward 1 frame in time.
- `j` / `Down`: Jump backward 10 frames.
- `k` / `Up`: Jump forward 10 frames.
- `g` / `Home`: Jump to execution start (Step 1).
- `G` / `End`: Jump to execution end.
- `Space`: Toggle automatic forward playback animation.
- `w`: Focus watch variable input field.
- `q`: Exit cleanly.

---

## 4. Post-Mortem Crash Time-Travel

If target script crashes with an unhandled exception (e.g. `ZeroDivisionError`):
1. PyChronicle catches the exception and saves the crash frame into SQLite.
2. The TUI displays a red **Unhandled Exception Banner** positioned right at the crash line.
3. The developer can press `[h]` to step backward in time, observing the variables that caused the error!
