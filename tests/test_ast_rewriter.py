"""Unit tests for PyChronicle AST Rewriter & Dynamic Instrumenter."""

import ast
import pytest
from pychronicle.rewriter.transformer import (
    ASTRewriter,
    compile_rewritten,
    rewrite_ast,
    rewrite_code,
)


def test_rewrite_preserves_docstring():
    code = '''"""Module docstring."""
x = 10
'''
    tree = ast.parse(code)
    rewritten = rewrite_ast(tree)
    # The first statement must remain the docstring Expr
    first_stmt = rewritten.body[0]
    assert isinstance(first_stmt, ast.Expr)
    assert isinstance(first_stmt.value, ast.Constant)
    assert first_stmt.value.value == "Module docstring."


def test_rewrite_injects_hooks():
    code = """
a = 1
b = 2
c = a + b
"""
    unparsed, tree = rewrite_code(code)
    assert "__pychronicle_hook__" in unparsed


def test_rewritten_code_execution():
    code = """
x = 5
y = x * 2
total = x + y
"""
    _, tree = rewrite_code(code)
    compiled = compile_rewritten(tree)

    captured_events = []

    def mock_hook(lineno, scope, local_dict, event_type="line"):
        captured_events.append((lineno, scope, dict(local_dict), event_type))

    user_globals = {"__pychronicle_hook__": mock_hook}
    exec(compiled, user_globals)

    assert len(captured_events) >= 3
    final_state = captured_events[-1][2]
    assert final_state.get("x") == 5
    assert final_state.get("y") == 10
    assert final_state.get("total") == 15


def test_function_return_capture():
    code = """
def multiply(a, b):
    res = a * b
    return res

answer = multiply(3, 4)
"""
    _, tree = rewrite_code(code)
    compiled = compile_rewritten(tree)

    events = []

    def mock_hook(lineno, scope, local_dict, event_type="line"):
        events.append((lineno, scope, dict(local_dict), event_type))

    user_globals = {"__pychronicle_hook__": mock_hook}
    exec(compiled, user_globals)

    # Check that return event captured the return value
    return_events = [e for e in events if e[3] == "return"]
    assert len(return_events) == 1
    assert return_events[0][2].get("__pychronicle_ret__") == 12
    assert user_globals.get("answer") == 12


def test_loop_and_branch_rewriting():
    code = """
nums = []
for i in range(3):
    if i == 1:
        nums.append(100)
    else:
        nums.append(i)
"""
    _, tree = rewrite_code(code)
    compiled = compile_rewritten(tree)

    events = []

    def mock_hook(lineno, scope, local_dict, event_type="line"):
        events.append(dict(local_dict))

    user_globals = {"__pychronicle_hook__": mock_hook}
    exec(compiled, user_globals)

    assert user_globals["nums"] == [0, 100, 2]
    assert len(events) >= 6
