# Architecture

## Execution path

1. The CLI validates the target and creates a run row in SQLite.
2. `TraceEngine` launches the script with `runpy.run_path`, preserving its
   `__main__` behavior, command-line arguments, and normal imports.
3. `sys.settrace` observes call, line, exception, and return events for files
   beneath the target script's directory. Each Python frame receives its own
   monotonically allocated frame ID.
4. On each line callback, locals and referenced globals are compared against
   serialized fingerprints from the previous callback. The event stores the
   line that just executed when a changed value is observed; deleted locals are
   stored as tombstones.
5. `Timeline` loads ordered events, while `SQLiteStore.state_at` replays deltas
   for the selected run and frame up to the selected event.
6. The Textual UI displays the captured source line, reconstructed frame locals,
   and a keyboard-controlled timeline.

The tracer observes Python's existing interpreter events and does not rewrite or
modify target source files. The AST parser/analyzer is a separate static-analysis
surface. `TraceHookTransformer` is provided for consumers that explicitly need
AST hook insertion, but the normal CLI relies on `sys.settrace`.

## Storage

- `runs`: target, start/end time, completion state, and an error summary.
- `events`: ordered line metadata and the owning frame.
- `deltas`: variable name, JSON value or safe representation, and deletion flag.

Every traced line has an event row, even when no local changed. Values use JSON
when possible; other values are represented by type and `repr`. No pickle is
used. Frame IDs scope local names so repeated names in recursive calls do not
collide. Referenced globals in function frames use the `global:` prefix.

## Boundaries

PyChronicle is a development debugger, not a sandbox. A traced program runs with
the invoking user's permissions. It traces Python code under the target
directory, not subprocesses, native execution, or Python files outside that
directory.