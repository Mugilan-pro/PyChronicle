"""Unified PyChronicle Runner.

Integrates the AST Analyzer, AST Rewriter, Execution Tracer, and Storage Engine
into a seamless developer workflow.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pychronicle.rewriter import (
    AnalysisResult,
    analyze_code,
    analyze_file,
    compile_rewritten,
    rewrite_ast,
)
import ast
from pychronicle.storage import StorageManager
from pychronicle.storage.models import ExecutionRecord, TraceEvent
from pychronicle.tracer import ExecutionTracer, TraceFilter


class PyChronicleRunner:
    """Unified execution runner for PyChronicle time-travel debugging.

    Supports two instrumentation modes:
    1. 'tracer' (default): Uses sys.settrace with AST-informed variable scoping.
    2. 'rewriter': Uses dynamic AST rewriting to inject state capture callbacks
       directly into statement bodies at runtime.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self.storage = StorageManager(db_path=db_path)
        self.last_analysis: Optional[AnalysisResult] = None
        self.last_execution_id: Optional[int] = None

    def run_code(
        self,
        source_code: str,
        filename: str = "<pychronicle_script>",
        mode: str = "tracer",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Analyze, instrument, and execute Python source code.

        Args:
            source_code: Python source code string.
            filename: Virtual filename for traceback and filtering.
            mode: 'tracer' (sys.settrace) or 'rewriter' (AST rewriting).
            metadata: Optional execution session metadata.

        Returns:
            The execution ID of this run.
        """
        # Step 1: Week 1 AST Analysis
        self.last_analysis = analyze_code(source_code, filename=filename)

        # Step 2: Start Storage Session
        exec_meta = metadata or {}
        exec_meta.update({
            "mode": mode,
            "total_ast_assignments": len(self.last_analysis.assignments),
            "target_variables": sorted(list(self.last_analysis.all_variables)),
        })
        exec_id = self.storage.start_execution(script_name=filename, metadata=exec_meta)
        self.last_execution_id = exec_id

        user_globals: Dict[str, Any] = {
            "__name__": "__main__",
            "__file__": filename,
        }

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

        self.storage.finish_execution(exec_id)
        return exec_id

    def run_file(
        self,
        filepath: str,
        mode: str = "tracer",
        metadata: Optional[Dict[str, Any]] = None,
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

    def close(self) -> None:
        """Close storage engine."""
        self.storage.close()

    def __enter__(self) -> PyChronicleRunner:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
