"""Data models for PyChronicle's AST Analyzer and Rewriter.

Defines representations for variable assignments, scopes, and AST analysis metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class AssignmentKind(str, Enum):
    """Enumeration of all Python syntax forms that bind or mutate variables."""
    SIMPLE = "simple"                  # x = 10
    AUGMENTED = "augmented"            # x += 1
    ANNOTATED = "annotated"            # x: int = 10
    UNPACKING = "unpacking"            # a, b = 1, 2 or a, *rest = items
    WALRUS = "walrus"                  # if (n := len(items)): ...
    FOR_LOOP = "for_loop"              # for i in range(10):
    ASYNC_FOR = "async_for"            # async for item in stream:
    WITH = "with"                      # with open(...) as f:
    ASYNC_WITH = "async_with"          # async with lock as l:
    EXCEPT = "except"                  # except Exception as e:
    ATTR_SUBSCRIPT = "attr_subscript"  # d["key"] = val or obj.attr = val
    FUNCTION_PARAM = "function_param"  # def foo(x, y=1, *args, **kwargs):
    FUNCTION_DEF = "function_def"      # def foo(): ...
    CLASS_DEF = "class_def"            # class Bar: ...
    IMPORT = "import"                  # import os, from math import sqrt as s


@dataclass
class AssignmentRecord:
    """Represents a single variable assignment or binding identified in the AST.

    Attributes:
        target_name: Identifier of the variable (e.g. 'total', 'user.name').
        line_number: Line number where assignment occurs (1-indexed).
        col_offset: Column offset where assignment occurs.
        kind: AssignmentKind classification.
        scope_name: Name of enclosing scope (e.g. '<module>', 'calculate').
        scope_type: Type of enclosing scope ('module', 'function', 'class').
        is_definition: True if this is the first binding of the variable in scope.
        raw_code_snippet: Source code snippet corresponding to the statement.
        end_line_number: Optional ending line number for multi-line statements.
    """
    target_name: str
    line_number: int
    col_offset: int
    kind: AssignmentKind
    scope_name: str = "<module>"
    scope_type: str = "module"
    is_definition: bool = False
    raw_code_snippet: Optional[str] = None
    end_line_number: Optional[int] = None


@dataclass
class ScopeInfo:
    """Represents a lexical scope (module, function, or class)."""
    name: str
    scope_type: str
    parent_name: Optional[str] = None
    start_line: int = 1
    end_line: int = 1
    assigned_vars: Set[str] = field(default_factory=set)
    referenced_vars: Set[str] = field(default_factory=set)
    global_vars: Set[str] = field(default_factory=set)
    nonlocal_vars: Set[str] = field(default_factory=set)


@dataclass
class AnalysisResult:
    """Aggregated result of AST parsing and variable assignment analysis."""
    filename: str
    source_code: str
    assignments: List[AssignmentRecord] = field(default_factory=list)
    assignments_by_line: Dict[int, List[AssignmentRecord]] = field(default_factory=dict)
    variables_by_line: Dict[int, Set[str]] = field(default_factory=dict)
    scopes: Dict[str, ScopeInfo] = field(default_factory=dict)

    @property
    def all_variables(self) -> Set[str]:
        """Set of all unique variable names assigned anywhere in the target."""
        return {record.target_name for record in self.assignments}

    def get_variables_at_line(self, line_number: int) -> Set[str]:
        """Return the set of variable names assigned or modified on a given line."""
        return self.variables_by_line.get(line_number, set())

    def get_assignments_for_variable(self, var_name: str) -> List[AssignmentRecord]:
        """Return all assignment records for a specific variable identifier."""
        return [r for r in self.assignments if r.target_name == var_name]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize analysis result to a summary dictionary."""
        return {
            "filename": self.filename,
            "total_assignments": len(self.assignments),
            "unique_variables": sorted(list(self.all_variables)),
            "lines_with_mutations": sorted(list(self.variables_by_line.keys())),
            "scopes": list(self.scopes.keys()),
        }
