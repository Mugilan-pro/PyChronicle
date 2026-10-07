# Development

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

The project targets Python 3.10+. It uses the standard library for parsing,
tracing, and SQLite; Textual powers the optional terminal UI.

## Commands

```powershell
pychronicle run examples\loop.py --db history.sqlite3
pychronicle inspect history.sqlite3
pychronicle ui history.sqlite3
pytest
```

The `run` command accepts `--db` before the target script. Any arguments after
the script path are forwarded to it.

## Contribution areas

- AST: parser, assignment analyzer, and instrumentation helpers.
- Tracer: frame lifecycle, line-event semantics, and mutation detection.
- Storage/timeline: schema, encoding, ordered history, and replay.
- UI/integration: CLI, keyboard navigation, watch filtering, examples, and docs.

Run the complete test suite before integrating changes. Do not commit generated
SQLite trace files or virtual environments.