"""Abstract Syntax Tree (AST) Analyzer for Python scripts.

Fulfills Week 1 Core Engineering specification:
"AST Parsing: Build a script that reads a target Python file, parses its
Abstract Syntax Tree, and identifies all variable assignments."
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pychronicle.rewriter.models import (
    AnalysisResult,
    AssignmentKind,
    AssignmentRecord,
    ScopeInfo,
)


class ASTAnalyzer(ast.NodeVisitor):
    """Walks an AST to detect, categorize, and catalog all variable assignments.

    Tracks scopes, line numbers, column offsets, and assignment mechanisms across
    the entire Python grammar.
    """

    def __init__(self, source_code: str, filename: str = "<string>") -> None:
        self.source_code = source_code
        self.filename = filename
        self.source_lines = source_code.splitlines()

        self.assignments: List[AssignmentRecord] = []
        self.assignments_by_line: Dict[int, List[AssignmentRecord]] = {}
        self.variables_by_line: Dict[int, Set[str]] = {}

        # Scope tracking stack
        self.scopes: Dict[str, ScopeInfo] = {}
        self.scope_stack: List[ScopeInfo] = []

        # Global scope initialization
        module_scope = ScopeInfo(
            name="<module>",
            scope_type="module",
            start_line=1,
            end_line=max(1, len(self.source_lines)),
        )
        self.scopes["<module>"] = module_scope
        self.scope_stack.append(module_scope)

    @property
    def current_scope(self) -> ScopeInfo:
        return self.scope_stack[-1]

    def _get_snippet(self, lineno: int, end_lineno: Optional[int] = None) -> Optional[str]:
        if 1 <= lineno <= len(self.source_lines):
            end = end_lineno if (end_lineno and end_lineno <= len(self.source_lines)) else lineno
            lines = self.source_lines[lineno - 1 : end]
            return "\n".join(lines).strip()
        return None

    def _record_assignment(
        self,
        target_name: str,
        lineno: int,
        col_offset: int,
        kind: AssignmentKind,
        end_lineno: Optional[int] = None,
    ) -> None:
        scope = self.current_scope
        is_first = target_name not in scope.assigned_vars
        scope.assigned_vars.add(target_name)

        snippet = self._get_snippet(lineno, end_lineno)
        record = AssignmentRecord(
            target_name=target_name,
            line_number=lineno,
            col_offset=col_offset,
            kind=kind,
            scope_name=scope.name,
            scope_type=scope.scope_type,
            is_definition=is_first,
            raw_code_snippet=snippet,
            end_line_number=end_lineno,
        )

        self.assignments.append(record)
        self.assignments_by_line.setdefault(lineno, []).append(record)
        self.variables_by_line.setdefault(lineno, set()).add(target_name)

    def _extract_target_nodes(
        self,
        node: ast.AST,
        is_unpacking: bool = False,
    ) -> List[Tuple[str, int, int, AssignmentKind]]:
        """Recursively decomposes AST targets (tuples, lists, starred, attributes)."""
        results: List[Tuple[str, int, int, AssignmentKind]] = []
        lineno = getattr(node, "lineno", self.current_scope.start_line)
        col_offset = getattr(node, "col_offset", 0)

        if isinstance(node, ast.Name):
            kind = AssignmentKind.UNPACKING if is_unpacking else AssignmentKind.SIMPLE
            results.append((node.id, lineno, col_offset, kind))

        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                results.extend(self._extract_target_nodes(elt, is_unpacking=True))

        elif isinstance(node, ast.Starred):
            results.extend(self._extract_target_nodes(node.value, is_unpacking=True))

        elif isinstance(node, ast.Attribute):
            try:
                attr_str = ast.unparse(node)
            except Exception:
                attr_str = getattr(node, "attr", "unknown_attr")
            results.append((attr_str, lineno, col_offset, AssignmentKind.ATTR_SUBSCRIPT))

        elif isinstance(node, ast.Subscript):
            try:
                sub_str = ast.unparse(node)
            except Exception:
                sub_str = "subscript_target"
            results.append((sub_str, lineno, col_offset, AssignmentKind.ATTR_SUBSCRIPT))

        return results

    # --- AST Visitor Hook Implementations ---

    def visit_Assign(self, node: ast.Assign) -> None:
        """Handles standard assignments: x = 1, a, b = 2, 3, etc."""
        is_unpack = len(node.targets) > 1
        for target in node.targets:
            targets = self._extract_target_nodes(
                target,
                is_unpacking=is_unpack or isinstance(target, (ast.Tuple, ast.List)),
            )
            for name, lineno, col, kind in targets:
                self._record_assignment(
                    name, lineno, col, kind, getattr(node, "end_lineno", None)
                )

        self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Handles augmented assignments: x += 1, total *= 2."""
        targets = self._extract_target_nodes(node.target)
        for name, lineno, col, _ in targets:
            self._record_assignment(
                name,
                lineno,
                col,
                AssignmentKind.AUGMENTED,
                getattr(node, "end_lineno", None),
            )
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Handles type annotated assignments: x: int = 10."""
        targets = self._extract_target_nodes(node.target)
        for name, lineno, col, _ in targets:
            self._record_assignment(
                name,
                lineno,
                col,
                AssignmentKind.ANNOTATED,
                getattr(node, "end_lineno", None),
            )
        if node.value:
            self.visit(node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        """Handles walrus operator: if (x := get_val()): ..."""
        targets = self._extract_target_nodes(node.target)
        for name, lineno, col, _ in targets:
            self._record_assignment(
                name,
                lineno,
                col,
                AssignmentKind.WALRUS,
                getattr(node, "end_lineno", None),
            )
        self.visit(node.value)

    def visit_For(self, node: ast.For) -> None:
        """Handles for loops: for i in range(10): or for k, v in pairs:"""
        targets = self._extract_target_nodes(
            node.target,
            is_unpacking=isinstance(node.target, (ast.Tuple, ast.List)),
        )
        for name, lineno, col, _ in targets:
            self._record_assignment(
                name,
                lineno,
                col,
                AssignmentKind.FOR_LOOP,
                getattr(node, "end_lineno", None),
            )

        self.visit(node.iter)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        """Handles async for loops."""
        targets = self._extract_target_nodes(
            node.target,
            is_unpacking=isinstance(node.target, (ast.Tuple, ast.List)),
        )
        for name, lineno, col, _ in targets:
            self._record_assignment(
                name,
                lineno,
                col,
                AssignmentKind.ASYNC_FOR,
                getattr(node, "end_lineno", None),
            )

        self.visit(node.iter)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_With(self, node: ast.With) -> None:
        """Handles with statements: with open(...) as f:"""
        for item in node.items:
            if item.optional_vars:
                targets = self._extract_target_nodes(
                    item.optional_vars,
                    is_unpacking=isinstance(item.optional_vars, (ast.Tuple, ast.List)),
                )
                for name, lineno, col, _ in targets:
                    self._record_assignment(
                        name,
                        lineno,
                        col,
                        AssignmentKind.WITH,
                        getattr(node, "end_lineno", None),
                    )
            self.visit(item.context_expr)

        for stmt in node.body:
            self.visit(stmt)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        """Handles async with statements."""
        for item in node.items:
            if item.optional_vars:
                targets = self._extract_target_nodes(
                    item.optional_vars,
                    is_unpacking=isinstance(item.optional_vars, (ast.Tuple, ast.List)),
                )
                for name, lineno, col, _ in targets:
                    self._record_assignment(
                        name,
                        lineno,
                        col,
                        AssignmentKind.ASYNC_WITH,
                        getattr(node, "end_lineno", None),
                    )
            self.visit(item.context_expr)

        for stmt in node.body:
            self.visit(stmt)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Handles exception bindings: except ValueError as err:"""
        if node.name:
            self._record_assignment(
                node.name,
                node.lineno,
                node.col_offset,
                AssignmentKind.EXCEPT,
                getattr(node, "end_lineno", None),
            )
        if node.type:
            self.visit(node.type)
        for stmt in node.body:
            self.visit(stmt)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Handles function definitions, recording parameters and new scope."""
        self._record_assignment(
            node.name,
            node.lineno,
            node.col_offset,
            AssignmentKind.FUNCTION_DEF,
            getattr(node, "end_lineno", None),
        )

        parent_scope = self.current_scope.name
        full_name = f"{parent_scope}.{node.name}" if parent_scope != "<module>" else node.name
        func_scope = ScopeInfo(
            name=full_name,
            scope_type="function",
            parent_name=parent_scope,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
        )
        self.scopes[full_name] = func_scope
        self.scope_stack.append(func_scope)

        # Record parameter bindings
        args = node.args
        all_params = (
            getattr(args, "posonlyargs", [])
            + args.args
            + ([args.vararg] if args.vararg else [])
            + args.kwonlyargs
            + ([args.kwarg] if args.kwarg else [])
        )
        for arg in all_params:
            if arg:
                self._record_assignment(
                    arg.arg,
                    getattr(arg, "lineno", node.lineno),
                    getattr(arg, "col_offset", node.col_offset),
                    AssignmentKind.FUNCTION_PARAM,
                )

        # Visit decorators and defaults in outer scope
        for d in node.decorator_list:
            self.visit(d)

        # Visit body in function scope
        for stmt in node.body:
            self.visit(stmt)

        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Handles async function definitions."""
        self._record_assignment(
            node.name,
            node.lineno,
            node.col_offset,
            AssignmentKind.FUNCTION_DEF,
            getattr(node, "end_lineno", None),
        )

        parent_scope = self.current_scope.name
        full_name = f"{parent_scope}.{node.name}" if parent_scope != "<module>" else node.name
        func_scope = ScopeInfo(
            name=full_name,
            scope_type="function",
            parent_name=parent_scope,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
        )
        self.scopes[full_name] = func_scope
        self.scope_stack.append(func_scope)

        args = node.args
        all_params = (
            getattr(args, "posonlyargs", [])
            + args.args
            + ([args.vararg] if args.vararg else [])
            + args.kwonlyargs
            + ([args.kwarg] if args.kwarg else [])
        )
        for arg in all_params:
            if arg:
                self._record_assignment(
                    arg.arg,
                    getattr(arg, "lineno", node.lineno),
                    getattr(arg, "col_offset", node.col_offset),
                    AssignmentKind.FUNCTION_PARAM,
                )

        for d in node.decorator_list:
            self.visit(d)

        for stmt in node.body:
            self.visit(stmt)

        self.scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Handles class definitions and class bodies."""
        self._record_assignment(
            node.name,
            node.lineno,
            node.col_offset,
            AssignmentKind.CLASS_DEF,
            getattr(node, "end_lineno", None),
        )

        parent_scope = self.current_scope.name
        full_name = f"{parent_scope}.{node.name}" if parent_scope != "<module>" else node.name
        class_scope = ScopeInfo(
            name=full_name,
            scope_type="class",
            parent_name=parent_scope,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
        )
        self.scopes[full_name] = class_scope
        self.scope_stack.append(class_scope)

        for d in node.decorator_list:
            self.visit(d)
        for b in node.bases:
            self.visit(b)
        for stmt in node.body:
            self.visit(stmt)

        self.scope_stack.pop()

    def visit_Import(self, node: ast.Import) -> None:
        """Handles module imports: import math, sys."""
        for alias in node.names:
            name = alias.asname or alias.name
            self._record_assignment(
                name,
                node.lineno,
                node.col_offset,
                AssignmentKind.IMPORT,
                getattr(node, "end_lineno", None),
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handles from imports: from collections import defaultdict as dd."""
        for alias in node.names:
            name = alias.asname or alias.name
            self._record_assignment(
                name,
                node.lineno,
                node.col_offset,
                AssignmentKind.IMPORT,
                getattr(node, "end_lineno", None),
            )

    def visit_Global(self, node: ast.Global) -> None:
        for name in node.names:
            self.current_scope.global_vars.add(name)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        for name in node.names:
            self.current_scope.nonlocal_vars.add(name)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.current_scope.referenced_vars.add(node.id)


def analyze_code(source_code: str, filename: str = "<string>") -> AnalysisResult:
    """Parse source code string and produce an AnalysisResult."""
    tree = ast.parse(source_code, filename=filename)
    analyzer = ASTAnalyzer(source_code=source_code, filename=filename)
    analyzer.visit(tree)

    return AnalysisResult(
        filename=filename,
        source_code=source_code,
        assignments=analyzer.assignments,
        assignments_by_line=analyzer.assignments_by_line,
        variables_by_line=analyzer.variables_by_line,
        scopes=analyzer.scopes,
    )


def analyze_file(filepath: str | Path) -> AnalysisResult:
    """Read a Python file from disk, parse its AST, and produce an AnalysisResult."""
    path = Path(filepath)
    with open(path, "r", encoding="utf-8") as f:
        source_code = f.read()
    return analyze_code(source_code, filename=str(path))


if __name__ == "__main__":
    import sys

    sample_code = """# Sample code for AST analysis
total = 0
for i in range(3):
    total += i

def multiply(a, b=2):
    return a * b
"""
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if not target.exists():
            print(f"Error: {target} not found.", file=sys.stderr)
            sys.exit(1)
        res = analyze_file(target)
    else:
        res = analyze_code(sample_code, filename="demo_sample.py")

    print(f"=== PyChronicle AST Analysis: {res.filename} ===")
    print(f"Total assignments detected: {len(res.assignments)}")
    print(f"Unique variables cataloged: {', '.join(sorted(res.all_variables))}")
    print(f"Scopes identified: {', '.join(res.scopes.keys())}")
    for rec in res.assignments:
        print(f"  L{rec.line_number:<3} | {rec.target_name:<16} | {rec.kind.value:<14} | Scope: {rec.scope_name}")
