# Requirements and scope

## Functional requirements

1. Parse a Python source file and report assignment targets with line numbers.
2. Execute a target script without changing its source, forwarding its arguments.
3. Record ordered line events and local-variable deltas for traced frames.
4. Represent deleted variables and reconstruct state at any event in a frame.
5. Persist histories in SQLite and support reopening them later.
6. Provide CLI commands to run, inspect, and interactively browse a trace.
7. Allow users to move backward/forward through events and filter watched names.
8. Preserve normal target exceptions and process exit behavior while recording
   the failed run status.

## Non-functional requirements

- Python 3.10 or later; local SQLite, no service dependency.
- No unsafe object deserialization (in particular, do not unpickle trace values).
- Keep line metadata and variable changes separate to avoid duplicating unchanged
  locals at every event.
- Keep trace data local; it can contain sensitive program values.
- Make tracing overhead and process-boundary limitations clear to users.

## Out of scope

Distributed or multi-process tracing, deterministic replay, restoring arbitrary
live objects, and debugging native code are not part of this MVP.