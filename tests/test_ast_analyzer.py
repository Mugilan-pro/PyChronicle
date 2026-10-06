"""Unit tests for PyChronicle AST Analyzer (Week 1 Core Engineering)."""

import pytest
from pychronicle.rewriter.analyzer import ASTAnalyzer, analyze_code
from pychronicle.rewriter.models import AssignmentKind


def test_simple_and_chained_assignment():
    code = """
a = 10
b = c = 20
"""
    result = analyze_code(code)
    vars_found = result.all_variables
    assert "a" in vars_found
    assert "b" in vars_found
    assert "c" in vars_found

    record_a = result.get_assignments_for_variable("a")[0]
    assert record_a.kind == AssignmentKind.SIMPLE
    assert record_a.line_number == 2
    assert record_a.is_definition is True


def test_augmented_assignment():
    code = """
count = 0
count += 1
count *= 10
"""
    result = analyze_code(code)
    records = result.get_assignments_for_variable("count")
    assert len(records) == 3
    assert records[0].kind == AssignmentKind.SIMPLE
    assert records[0].is_definition is True
    assert records[1].kind == AssignmentKind.AUGMENTED
    assert records[1].is_definition is False
    assert records[2].kind == AssignmentKind.AUGMENTED


def test_annotated_assignment():
    code = """
score: int = 100
name: str = "Alice"
"""
    result = analyze_code(code)
    records_score = result.get_assignments_for_variable("score")
    assert len(records_score) == 1
    assert records_score[0].kind == AssignmentKind.ANNOTATED
    assert records_score[0].line_number == 2


def test_unpacking_assignments():
    code = """
x, y = 10, 20
head, *tail, last = [1, 2, 3, 4, 5]
"""
    result = analyze_code(code)
    assert {"x", "y", "head", "tail", "last"}.issubset(result.all_variables)
    for v in ["x", "y", "head", "tail", "last"]:
        records = result.get_assignments_for_variable(v)
        assert len(records) >= 1
        assert records[0].kind == AssignmentKind.UNPACKING


def test_walrus_operator():
    code = """
data = [1, 2, 3]
if (n := len(data)) > 2:
    msg = f"Length {n}"
"""
    result = analyze_code(code)
    assert "n" in result.all_variables
    n_rec = result.get_assignments_for_variable("n")[0]
    assert n_rec.kind == AssignmentKind.WALRUS
    assert n_rec.line_number == 3


def test_for_and_with_and_except_bindings():
    code = """
for i, item in enumerate([10, 20]):
    pass

with open("dummy.txt", "r") as f:
    pass

try:
    raise ValueError("test")
except ValueError as err:
    pass
"""
    result = analyze_code(code)
    assert "i" in result.all_variables
    assert "item" in result.all_variables
    assert "f" in result.all_variables
    assert "err" in result.all_variables

    assert result.get_assignments_for_variable("i")[0].kind == AssignmentKind.FOR_LOOP
    assert result.get_assignments_for_variable("f")[0].kind == AssignmentKind.WITH
    assert result.get_assignments_for_variable("err")[0].kind == AssignmentKind.EXCEPT


def test_function_and_class_scopes():
    code = """
global_var = 1

def compute(x, y=2):
    local_acc = x + y
    return local_acc

class Worker:
    def execute(self, task):
        result = task * 2
        return result
"""
    result = analyze_code(code)
    assert "<module>" in result.scopes
    assert "compute" in result.scopes
    assert "Worker" in result.scopes
    assert "Worker.execute" in result.scopes

    # Parameters
    assert "x" in result.scopes["compute"].assigned_vars
    assert "y" in result.scopes["compute"].assigned_vars
    assert "local_acc" in result.scopes["compute"].assigned_vars

    # Methods
    assert "self" in result.scopes["Worker.execute"].assigned_vars
    assert "task" in result.scopes["Worker.execute"].assigned_vars
    assert "result" in result.scopes["Worker.execute"].assigned_vars


def test_line_mutation_mapping():
    code = """a = 1
b = 2
a, b = b, a
"""
    result = analyze_code(code)
    assert result.get_variables_at_line(1) == {"a"}
    assert result.get_variables_at_line(2) == {"b"}
    assert result.get_variables_at_line(3) == {"a", "b"}
