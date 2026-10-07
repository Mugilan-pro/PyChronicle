"""Unified PyChronicle Runner.

Integrates the AST Analyzer, AST Rewriter, Execution Tracer, Storage Engine,
and Delta Compression into a seamless developer workflow.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Dict, List, Optional

from pychronicle.rewriter import (
    AnalysisResult,
    analyze_code,
    analyze_file,
    compile_rewritten,
    rewrite_ast,
)
from pychronicle.storage import StorageManager
from pychronicle.storage.models import ExecutionRecord, TraceEvent
from pychronicle.tracer import ExecutionTracer, TraceFilter


class PyChronicleRunner:
    """Unified execution runner for PyChronicle time-travel debugging.

    Supports:
    1. 'tracer' mode (default): Uses sys.settrace with AST-informed variable scoping.
    2. 'rewriter' mode: Uses dynamic AST rewriting to inject state capture callbacks.
    3. Delta Compression: High-efficiency delta recording saving 90%+ storage.
    4. Crash Time-Travel: Captures unhandled exceptions for post-mortem time-travel.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        delta_mode: bool = False,
        checkpoint_interval: int = 50,
    ) -> None:
        self.db_path = db_path
        self.delta_mode = delta_mode
        self.checkpoint_interval = checkpoint_interval
        self.storage = StorageManager(
            db_path=db_path,
            delta_mode=delta_mode,
            checkpoint_interval=checkpoint_interval,
        )
        self.last_analysis: Optional[AnalysisResult] = None
        self.last_execution_id: Optional[int] = None
        self.last_exception: Optional[BaseException] = None
        self.last_exception_traceback: Optional[str] = None

    def run_code(
        self,
        source_code: str,
        filename: str = "<pychronicle_script>",
        mode: str = "tracer",
        metadata: Optional[Dict[str, Any]] = None,
        delta_mode: Optional[bool] = None,
    ) -> int:
        """Analyze, instrument, and execute Python source code.

        Args:
            source_code: Python source code string.
            filename: Virtual filename for traceback and filtering.
            mode: 'tracer' (sys.settrace) or 'rewriter' (AST rewriting).
            metadata: Optional execution session metadata.
            delta_mode: Override delta compression setting for this run.

        Returns:
            The execution ID of this run.
        """
        if delta_mode is not None:
            self.storage.delta_mode = delta_mode

        # Step 1: Week 1 AST Analysis
        self.last_analysis = analyze_code(source_code, filename=filename)
        self.last_exception = None
        self.last_exception_traceback = None

        # Step 2: Start Storage Session
        exec_meta = metadata or {}
        exec_meta.update({
            "mode": mode,
            "delta_mode": self.storage.delta_mode,
            "total_ast_assignments": len(self.last_analysis.assignments),
            "target_variables": sorted(list(self.last_analysis.all_variables)),
            "source_lines_count": len(source_code.splitlines()),
        })
        exec_id = self.storage.start_execution(script_name=filename, metadata=exec_meta)
        self.last_execution_id = exec_id

        user_globals: Dict[str, Any] = {
            "__name__": "__main__",
            "__file__": filename,
        }

        try:
            if mode == "rewriter":
                # AST Rewriter Mode: inject state capture hooks
                tree = ast.parse(source_code, filename=filename)
                rewritten_tree = rewrite_ast(tree, hook_name="__pychronicle_hook__")
                compiled = compile_rewritten(rewritten_tree, filename=filename)

                def runtime_hook(lineno: int, func_name: str, local_dict: Dict[str, Any], event_type: str = "line"):
                    clean = {
                        k: v
                        for k, v in local_dict.items()
                        if not k.startswith("__") and not k.startswith("_pychronicle_")
                    }
                    self.storage.record_event(
                        line_number=lineno,
                        state=clean,
                        function_name=func_name,
                        event_type=event_type,
                    )

                user_globals["__pychronicle_hook__"] = runtime_hook
                exec(compiled, user_globals)

            else:
                # Tracer Mode: sys.settrace execution engine
                trace_filter = TraceFilter(target_files=[filename])
                tracer = ExecutionTracer(
                    storage=self.storage,
                    trace_filter=trace_filter,
                    analysis=self.last_analysis,
                )
                compiled = compile(source_code, filename, "exec")
                with tracer:
                    exec(compiled, user_globals)

        except BaseException as e:
            # Capture crash for Post-Mortem Time-Travel Debugging (Week 4)
            self.last_exception = e
            self.last_exception_traceback = traceback.format_exc()
            # If the exception wasn't recorded as an event, record a crash event
            tb = sys.exc_info()[2]
            crash_lineno = 1
            if tb:
                while tb.tb_next:
                    tb = tb.tb_next
                crash_lineno = tb.tb_lineno

            self.storage.record_event(
                line_number=crash_lineno,
                state={
                    "__exception__": f"{type(e).__name__}: {str(e)}",
                    "__traceback__": self.last_exception_traceback,
                },
                function_name="<crash>",
                event_type="exception",
            )
            # We don't re-raise here so the time-travel session remains inspectable,
            # but callers can check runner.last_exception

        finally:
            self.storage.finish_execution(exec_id)

        return exec_id

    def run_file(
        self,
        filepath: str,
        mode: str = "tracer",
        metadata: Optional[Dict[str, Any]] = None,
        delta_mode: Optional[bool] = None,
    ) -> int:
        """Analyze, instrument, and execute a Python script from disk."""
        abs_path = os.path.abspath(filepath)
        with open(abs_path, "r", encoding="utf-8") as f:
            code = f.read()
        return self.run_code(
            source_code=code,
            filename=abs_path,
            mode=mode,
            metadata=metadata,
            delta_mode=delta_mode,
        )

    def get_timeline(self, execution_id: Optional[int] = None) -> List[TraceEvent]:
        """Fetch chronological list of recorded events for playback."""
        exec_id = execution_id or self.last_execution_id
        if exec_id is None:
            return []
        return self.storage.get_events(execution_id=exec_id)

    def watch_variable(self, var_name: str, execution_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve historical timeline of values for a specific variable."""
        exec_id = execution_id or self.last_execution_id
        if exec_id is None:
            return []
        return self.storage.get_variable_history(var_name=var_name, execution_id=exec_id)

    def get_execution(self, execution_id: Optional[int] = None) -> Optional[ExecutionRecord]:
        """Fetch metadata about an execution session."""
        exec_id = execution_id or self.last_execution_id
        if exec_id is None:
            return None
        return self.storage.get_execution(exec_id)

    def get_storage_stats(self, execution_id: Optional[int] = None) -> Dict[str, Any]:
        """Return compression metrics and event counts for the execution session."""
        exec_id = execution_id or self.last_execution_id
        return self.storage.get_storage_stats(exec_id)

    def close(self) -> None:
        """Close storage engine."""
        self.storage.close()

    def __enter__(self) -> PyChronicleRunner:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
