# Testing

Run tests from the repository root:

```powershell
pytest
```

The suite covers:

- AST assignment discovery, including tuple, augmented, loop, and annotated
  assignments.
- SQLite event ordering, value serialization, tombstones, and historical replay.
- Real script tracing, loop iterations, nested frame separation, mutable values,
  command-line arguments, and failed runs.
- Timeline navigation and Textual helper rendering.
- CLI execution and inspection using temporary trace databases.

Integration tests run only small temporary scripts and do not execute the example
programs as part of the test suite.