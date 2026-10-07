"""Abstract Syntax Tree (AST) Rewriter & Dynamic Instrumentation Engine.

Dynamically transforms Python scripts to inject state-capturing hooks at runtime
without modifying the original source code files on disk.
"""

from __future__ import annotations

import ast
from typing import List, Optional, Tuple


class ASTRewriter(ast.NodeTransformer):
    """Subclasses ast.NodeTransformer to inject PyChronicle state capture hooks.

    Hooks are inserted after variable assignments and at statement boundaries so
    the execution engine observes exact post-mutation variable values.
    """

    def __init__(self, hook_name: str = "__pychronicle_hook__") -> None:
        self.hook_name = hook_name
        self.scope_stack: List[str] = ["<module>"]

    @property
    def current_scope(self) -> str:
        return self.scope_stack[-1]

    def _create_hook_call(
        self,
        lineno: int,
        scope_name: str,
        event_type: str = "line",
        extra_vars: Optional[List[str]] = None,
    ) -> ast.Expr:
        """Construct an AST node calling:
        __pychronicle_hook__(lineno, scope_name, locals(), event_type)
        """
        hook_call = ast.Expr(
            value=ast.Call(
                func=ast.Name(id=self.hook_name, ctx=ast.Load()),
                args=[
                    ast.Constant(value=lineno),
                    ast.Constant(value=scope_name),
                    ast.Call(
                        func=ast.Name(id="locals", ctx=ast.Load()),
                        args=[],
                        keywords=[],
                    ),
                    ast.Constant(value=event_type),
                ],
                keywords=[],
            )
        )
        return hook_call

    def _transform_statement_list(
        self,
        stmts: List[ast.stmt],
        scope_name: str,
        is_function_body: bool = False,
    ) -> List[ast.stmt]:
        """Transforms a sequence of statements, injecting hooks around them."""
        new_stmts: List[ast.stmt] = []
        start_idx = 0

        # Check for docstring at start of block
        if stmts and isinstance(stmts[0], ast.Expr):
            if isinstance(stmts[0].value, ast.Constant) and isinstance(stmts[0].value.value, str):
                new_stmts.append(stmts[0])
                start_idx = 1

        # In function body, inject initial 'call' hook to record input arguments
        if is_function_body and stmts:
            first_lineno = getattr(stmts[0], "lineno", 1)
            call_hook = self._create_hook_call(
                lineno=first_lineno,
                scope_name=scope_name,
                event_type="call",
            )
            ast.copy_location(call_hook, stmts[0])
            new_stmts.append(call_hook)

        for stmt in stmts[start_idx:]:
            transformed = self.visit(stmt)

            if transformed is None:
                continue

            # Return statement handling: capture state right before returning
            if isinstance(transformed, ast.Return):
                ret_lineno = getattr(transformed, "lineno", 1)
                if transformed.value is not None:
                    # Evaluate return value into temp var, capture locals, then return temp var
                    temp_var_name = "__pychronicle_ret__"
                    assign_temp = ast.Assign(
                        targets=[ast.Name(id=temp_var_name, ctx=ast.Store())],
                        value=transformed.value,
                    )
                    ast.copy_location(assign_temp, transformed)
                    new_stmts.append(assign_temp)

                    ret_hook = self._create_hook_call(
                        lineno=ret_lineno,
                        scope_name=scope_name,
                        event_type="return",
                    )
                    ast.copy_location(ret_hook, transformed)
                    new_stmts.append(ret_hook)

                    actual_return = ast.Return(
                        value=ast.Name(id=temp_var_name, ctx=ast.Load())
                    )
                    ast.copy_location(actual_return, transformed)
                    new_stmts.append(actual_return)
                else:
                    ret_hook = self._create_hook_call(
                        lineno=ret_lineno,
                        scope_name=scope_name,
                        event_type="return",
                    )
                    ast.copy_location(ret_hook, transformed)
                    new_stmts.append(ret_hook)
                    new_stmts.append(transformed)
                continue

            # Break / Continue handling: capture state right before loop jump
            if isinstance(transformed, (ast.Break, ast.Continue)):
                jump_lineno = getattr(transformed, "lineno", 1)
                jump_hook = self._create_hook_call(
                    lineno=jump_lineno,
                    scope_name=scope_name,
                    event_type="line",
                )
                ast.copy_location(jump_hook, transformed)
                new_stmts.append(jump_hook)
                new_stmts.append(transformed)
                continue

            # Append the original (or recursively transformed) statement
            new_stmts.append(transformed)

            # Skip injecting hooks after nested function/class definitions themselves
            if isinstance(transformed, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue

            # Inject post-execution hook with exact line location
            lineno = getattr(transformed, "end_lineno", getattr(transformed, "lineno", 1))
            hook = self._create_hook_call(
                lineno=lineno,
                scope_name=scope_name,
                event_type="line",
            )
            ast.copy_location(hook, transformed)
            new_stmts.append(hook)

        return new_stmts

    def visit_Module(self, node: ast.Module) -> ast.Module:
        node.body = self._transform_statement_list(node.body, "<module>")
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        parent_scope = self.current_scope
        func_name = f"{parent_scope}.{node.name}" if parent_scope != "<module>" else node.name
        self.scope_stack.append(func_name)

        # Recursively transform body with function scope
        node.body = self._transform_statement_list(
            node.body,
            scope_name=func_name,
            is_function_body=True,
        )

        self.scope_stack.pop()
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        parent_scope = self.current_scope
        func_name = f"{parent_scope}.{node.name}" if parent_scope != "<module>" else node.name
        self.scope_stack.append(func_name)

        node.body = self._transform_statement_list(
            node.body,
            scope_name=func_name,
            is_function_body=True,
        )

        self.scope_stack.pop()
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        parent_scope = self.current_scope
        class_name = f"{parent_scope}.{node.name}" if parent_scope != "<module>" else node.name
        self.scope_stack.append(class_name)

        node.body = self._transform_statement_list(node.body, scope_name=class_name)

        self.scope_stack.pop()
        return node

    def visit_For(self, node: ast.For) -> ast.For:
        self.generic_visit(node)
        node.body = self._transform_statement_list(node.body, scope_name=self.current_scope)
        if node.orelse:
            node.orelse = self._transform_statement_list(node.orelse, scope_name=self.current_scope)
        return node

    def visit_AsyncFor(self, node: ast.AsyncFor) -> ast.AsyncFor:
        self.generic_visit(node)
        node.body = self._transform_statement_list(node.body, scope_name=self.current_scope)
        if node.orelse:
            node.orelse = self._transform_statement_list(node.orelse, scope_name=self.current_scope)
        return node

    def visit_While(self, node: ast.While) -> ast.While:
        self.generic_visit(node)
        node.body = self._transform_statement_list(node.body, scope_name=self.current_scope)
        if node.orelse:
            node.orelse = self._transform_statement_list(node.orelse, scope_name=self.current_scope)
        return node

    def visit_If(self, node: ast.If) -> ast.If:
        self.generic_visit(node)
        node.body = self._transform_statement_list(node.body, scope_name=self.current_scope)
        if node.orelse:
            node.orelse = self._transform_statement_list(node.orelse, scope_name=self.current_scope)
        return node

    def visit_With(self, node: ast.With) -> ast.With:
        self.generic_visit(node)
        node.body = self._transform_statement_list(node.body, scope_name=self.current_scope)
        return node

    def visit_AsyncWith(self, node: ast.AsyncWith) -> ast.AsyncWith:
        self.generic_visit(node)
        node.body = self._transform_statement_list(node.body, scope_name=self.current_scope)
        return node

    def visit_Try(self, node: ast.Try) -> ast.Try:
        self.generic_visit(node)
        node.body = self._transform_statement_list(node.body, scope_name=self.current_scope)
        for handler in node.handlers:
            handler.body = self._transform_statement_list(handler.body, scope_name=self.current_scope)
        if node.orelse:
            node.orelse = self._transform_statement_list(node.orelse, scope_name=self.current_scope)
        if node.finalbody:
            node.finalbody = self._transform_statement_list(node.finalbody, scope_name=self.current_scope)
        return node


def rewrite_ast(
    tree: ast.AST,
    hook_name: str = "__pychronicle_hook__",
) -> ast.AST:
    """Transform an AST in-memory by injecting state-capture hooks."""
    rewriter = ASTRewriter(hook_name=hook_name)
    transformed = rewriter.visit(tree)
    ast.fix_missing_locations(transformed)
    return transformed


def rewrite_code(
    source_code: str,
    filename: str = "<string>",
    hook_name: str = "__pychronicle_hook__",
) -> Tuple[str, ast.AST]:
    """Parse source code, rewrite AST with state hooks, and return (unparsed_code, ast_tree)."""
    tree = ast.parse(source_code, filename=filename)
    transformed = rewrite_ast(tree, hook_name=hook_name)
    try:
        unparsed = ast.unparse(transformed)
    except Exception:
        unparsed = ""
    return unparsed, transformed


def compile_rewritten(
    tree: ast.AST,
    filename: str = "<pychronicle_instrumented>",
):
    """Compile an instrumented AST into an executable Python code object."""
    ast.fix_missing_locations(tree)
    return compile(tree, filename, "exec")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sample = '''"""Sample script for AST rewriter demonstration."""
x = 10
y = 20
total = x + y

for i in range(3):
    total += i

def calculate(val):
    result = val * 2
    return result

ans = calculate(total)
print(f"Final calculation: {ans}")
'''
    if len(sys.argv) > 1:
        target_path = Path(sys.argv[1])
        if target_path.exists():
            source = target_path.read_text(encoding="utf-8")
            print(f"=== Rewriting File: {target_path} ===")
        else:
            print(f"Error: {target_path} not found.", file=sys.stderr)
            sys.exit(1)
    else:
        source = sample
        print("=== Rewriting Built-in Demo Code ===")

    print("\n--- Original Source Code ---")
    print(source.strip())

    unparsed, tree = rewrite_code(source)
    print("\n--- Rewritten AST (with state-capturing hooks injected) ---")
    print(unparsed)

    print("\n--- Executing Rewritten AST with Mock Hook ---")
    events = []

    def demo_hook(lineno: int, scope: str, local_vars: dict, event_type: str = "line"):
        clean_vars = {k: v for k, v in local_vars.items() if not k.startswith("__")}
        events.append((lineno, scope, clean_vars, event_type))
        print(f"  [Hook Event] L{lineno:<3} | Scope: {scope:<12} | Event: {event_type:<6} | Locals: {clean_vars}")

    compiled = compile_rewritten(tree)
    exec_globals = {"__pychronicle_hook__": demo_hook}
    exec(compiled, exec_globals)

    print(f"\nTotal state-capture events recorded: {len(events)}")
