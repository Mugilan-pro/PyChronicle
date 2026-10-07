"""Command Line Interface (CLI) for PyChronicle.

Fulfills Week 4 Packaging specification:
"Packaging: Package the tool as a CLI utility using Click or Typer (e.g., pychronicle run myscript.py)."
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pychronicle._version import __version__
from pychronicle.rewriter import analyze_file
from pychronicle.runner import PyChronicleRunner
from pychronicle.storage.manager import StorageManager
from pychronicle.ui.app import PyChronicleApp

console = Console()


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(__version__, "-v", "--version", message="PyChronicle version %(version)s")
def cli() -> None:
    """PyChronicle — AST-Powered Time-Travel Debugger for Python.
    
    Travel backward and forward through program execution without re-running code.
    """
    pass


@cli.command("run")
@click.argument("script", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--delta/--no-delta", default=True, help="Enable Week 3 Delta Compression (90%+ storage savings).")
@click.option("--tui/--no-tui", default=True, help="Launch interactive Textual TUI dashboard after execution.")
@click.option("--db", "db_path", default="trace.db", help="Path to SQLite persistence database (or ':memory:').")
@click.option("--mode", type=click.Choice(["tracer", "rewriter"]), default="tracer", help="Instrumentation mode.")
@click.option("--checkpoint-interval", default=50, type=int, help="Frames between full-state keyframes.")
def cmd_run(
    script: str,
    delta: bool,
    tui: bool,
    db_path: str,
    mode: str,
    checkpoint_interval: int,
) -> None:
    """Execute a Python script under PyChronicle and inspect execution in time-travel TUI."""
    abs_script = os.path.abspath(script)
    console.print(f"[bold cyan]PyChronicle Time-Travel Debugger[/bold cyan] v{__version__}")
    console.print(f"[dim]Instrumenting:[/dim] [green]{abs_script}[/green] (mode={mode}, delta={delta})")

    start_time = time.perf_counter()
    runner = PyChronicleRunner(
        db_path=db_path,
        delta_mode=delta,
        checkpoint_interval=checkpoint_interval,
    )

    try:
        exec_id = runner.run_file(abs_script, mode=mode)
    except Exception as e:
        console.print(f"[bold red]Execution error:[/bold red] {e}")
        return

    duration = time.perf_counter() - start_time
    events = runner.get_timeline(exec_id)
    stats = runner.get_storage_stats(exec_id)

    # Summary table
    table = Table(title="Execution Summary", box=None, padding=(0, 2))
    table.add_column("Metric", style="bold white")
    table.add_column("Value", style="green")

    table.add_row("Total Execution Steps", str(len(events)))
    table.add_row("Execution Duration", f"{duration * 1000:.2f} ms")
    table.add_row("Instrumentation Mode", mode)
    table.add_row("Delta Compression", "Enabled (90%+ savings)" if delta else "Disabled (Full State)")
    table.add_row("Keyframe Snapshots", str(stats.get("keyframe_events", 0)))
    table.add_row("Delta Steps", str(stats.get("delta_events", 0)))
    table.add_row("Total Variable Rows", str(stats.get("total_variable_rows", 0)))
    table.add_row("Database Location", db_path)

    if runner.last_exception:
        table.add_row("Unhandled Exception", f"[bold red]{type(runner.last_exception).__name__}: {runner.last_exception}[/bold red]")

    console.print(table)

    if tui:
        # Launch Textual TUI
        exc_str = f"{type(runner.last_exception).__name__}: {runner.last_exception}" if runner.last_exception else None
        with open(abs_script, "r", encoding="utf-8") as f:
            code = f.read()

        app = PyChronicleApp(
            events=events,
            source_code=code,
            script_name=os.path.basename(abs_script),
            storage=runner.storage,
            exception_info=exc_str,
        )
        app.run()


@cli.command("view")
@click.argument("db_file", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--script", "script_path", default=None, help="Path to original source file if moved.")
@click.option("--exec-id", default=None, type=int, help="Specific execution ID to view (defaults to latest).")
def cmd_view(db_file: str, script_path: Optional[str], exec_id: Optional[int]) -> None:
    """Launch the Time-Travel TUI to inspect a pre-recorded SQLite session file."""
    console.print(f"[bold cyan]PyChronicle Session Viewer[/bold cyan] — Loading [green]{db_file}[/green]...")

    storage = StorageManager(db_path=db_file)
    exec_record = storage.get_execution(exec_id)
    if not exec_record:
        console.print("[bold red]No execution session found in database.[/bold red]")
        return

    events = storage.get_events(exec_record.id)
    console.print(f"Loaded session #[cyan]{exec_record.id}[/cyan] ({exec_record.script_name}): [green]{len(events)} steps[/green]")

    source_path = script_path or exec_record.script_name
    source_code = ""
    if source_path and os.path.exists(source_path):
        with open(source_path, "r", encoding="utf-8") as f:
            source_code = f.read()

    app = PyChronicleApp(
        events=events,
        source_code=source_code,
        script_name=os.path.basename(source_path) if source_path else "script.py",
        storage=storage,
    )
    app.run()


@cli.command("analyze")
@click.argument("script", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--json", "json_output", is_flag=True, help="Print machine-readable JSON output.")
def cmd_analyze(script: str, json_output: bool) -> None:
    """Parse Abstract Syntax Tree (AST) and catalog all variable assignments (Week 1)."""
    abs_script = os.path.abspath(script)
    result = analyze_file(abs_script)

    if json_output:
        payload = {
            "file": result.filename,
            "total_assignments": len(result.assignments),
            "variables": sorted(list(result.all_variables)),
            "assignments": [
                {
                    "target": a.target_name,
                    "line": a.line_number,
                    "kind": a.kind.value,
                    "scope": a.scope_name,
                }
                for a in result.assignments
            ],
        }
        click.echo(json.dumps(payload, indent=2))
        return

    console.print(Panel(
        f"[bold green]Static AST Assignment Analysis[/bold green]\n"
        f"Target: [cyan]{abs_script}[/cyan]\n"
        f"Unique Variables: [yellow]{len(result.all_variables)}[/yellow] | "
        f"Total Assignments: [yellow]{len(result.assignments)}[/yellow]",
        border_style="green",
    ))

    table = Table(box=None, padding=(0, 2))
    table.add_column("Line", style="cyan", width=6)
    table.add_column("Target Variable", style="bold white", width=18)
    table.add_column("Assignment Kind", style="yellow", width=16)
    table.add_column("Scope", style="dim magenta")

    for a in result.assignments:
        table.add_row(str(a.line_number), a.target_name, a.kind.value, a.scope_name)

    console.print(table)


@cli.command("watch")
@click.argument("script", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--var", "var_name", required=True, help="Name of the variable to watch across time.")
@click.option("--delta/--no-delta", default=True, help="Use delta compression.")
def cmd_watch(script: str, var_name: str, delta: bool) -> None:
    """Run script and output the chronological mutation history of a specific variable (Week 4)."""
    abs_script = os.path.abspath(script)
    runner = PyChronicleRunner(db_path=":memory:", delta_mode=delta)
    runner.run_file(abs_script)

    history = runner.watch_variable(var_name)

    console.print(Panel(
        f"[bold magenta]Watch Variable History: '{var_name}'[/bold magenta]\n"
        f"Script: [cyan]{abs_script}[/cyan] | Total Mutations: [yellow]{len(history)}[/yellow]",
        border_style="magenta",
    ))

    if not history:
        console.print(f"[dim]Variable '{var_name}' was never assigned or mutated during execution.[/dim]")
        return

    table = Table(box=None, padding=(0, 2))
    table.add_column("Step", style="dim cyan", width=6)
    table.add_column("Line", style="cyan", width=6)
    table.add_column("Type", style="dim", width=10)
    table.add_column("Value", style="bold white")

    prev_val = None
    for h in history:
        val = h["value"]
        val_str = repr(val)
        if prev_val is not None and prev_val != val:
            val_display = f"[bold yellow]{val_str}[/bold yellow] (was {repr(prev_val)})"
        else:
            val_display = val_str
        table.add_row(f"#{h['sequence']}", f"L{h['line_number']}", h.get("value_type", ""), val_display)
        prev_val = val

    console.print(table)


@cli.command("benchmark")
@click.argument("script", type=click.Path(exists=True, dir_okay=False, readable=True))
def cmd_benchmark(script: str) -> None:
    """Head-to-head benchmark: Raw Python vs. Full-State Tracing vs. Delta Compression."""
    abs_script = os.path.abspath(script)
    with open(abs_script, "r", encoding="utf-8") as f:
        code = f.read()

    console.print(f"[bold cyan]Benchmarking Execution Modes for:[/bold cyan] {os.path.basename(abs_script)}")

    # 1. Raw Python
    compiled = compile(code, abs_script, "exec")
    t0 = time.perf_counter()
    exec(compiled, {"__name__": "__main__"})
    raw_time = time.perf_counter() - t0

    # 2. Full-State Tracing (Weeks 1 & 2)
    runner_full = PyChronicleRunner(":memory:", delta_mode=False)
    t0 = time.perf_counter()
    full_id = runner_full.run_code(code, filename=abs_script)
    full_time = time.perf_counter() - t0
    full_stats = runner_full.get_storage_stats(full_id)

    # 3. Delta Compression (Week 3)
    runner_delta = PyChronicleRunner(":memory:", delta_mode=True, checkpoint_interval=50)
    t0 = time.perf_counter()
    delta_id = runner_delta.run_code(code, filename=abs_script)
    delta_time = time.perf_counter() - t0
    delta_stats = runner_delta.get_storage_stats(delta_id)

    # Comparison Table
    table = Table(title="Benchmark Comparison", box=None, padding=(0, 2))
    table.add_column("Execution Mode", style="bold white")
    table.add_column("Time (ms)", style="cyan", justify="right")
    table.add_column("Total Steps", justify="right")
    table.add_column("Variable Rows", justify="right")
    table.add_column("Storage Reduction", style="bold green", justify="right")

    table.add_row("Raw Python (No Tracing)", f"{raw_time * 1000:.2f} ms", "─", "0", "─")
    table.add_row(
        "Full-State Tracing (Weeks 1-2)",
        f"{full_time * 1000:.2f} ms",
        str(full_stats["total_events"]),
        str(full_stats["total_variable_rows"]),
        "Baseline (0%)",
    )

    full_rows = full_stats["total_variable_rows"]
    delta_rows = delta_stats["total_variable_rows"]
    pct_reduction = ((full_rows - delta_rows) / max(1, full_rows)) * 100.0

    table.add_row(
        "Delta Compression (Week 3)",
        f"{delta_time * 1000:.2f} ms",
        str(delta_stats["total_events"]),
        str(delta_stats["total_variable_rows"]),
        f"{pct_reduction:.1f}% Savings",
    )

    console.print(table)


def main() -> None:
    """Console script entry point."""
    cli()


if __name__ == "__main__":
    main()
