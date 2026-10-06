"""CLI Script for AST Parsing and Variable Assignment Identification.

Fulfills Week 1 Core Engineering specification:
"AST Parsing: Build a script that reads a target Python file, parses its
Abstract Syntax Tree, and identifies all variable assignments."

Usage:
    python ast_analyzer.py path/to/script.py
    python ast_analyzer.py path/to/script.py --json
    python ast_analyzer.py  (runs on built-in comprehensive sample)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from pychronicle.rewriter.analyzer import analyze_code, analyze_file
from pychronicle.rewriter.models import AnalysisResult


DEMO_SAMPLE = '''"""Sample target script demonstrating multiple assignment types."""

# 1. Simple and chained assignment
total = 0
step_multiplier = 10
alpha = beta = 100

# 2. Augmented assignment
total += 5

# 3. Type annotated assignment
threshold: int = 50

# 4. Unpacking and starred assignment
x, y = 1, 2
first, *rest, last = [10, 20, 30, 40, 50]

# 5. Walrus operator (Named expression)
items = [1, 2, 3, 4]
if (item_count := len(items)) > 2:
    status = "ready"

# 6. For loop bindings
for idx in range(3):
    total += idx * step_multiplier

# 7. With statement context binding
class MockContext:
    def __enter__(self):
        return "resource_handle"
    def __exit__(self, *args):
        pass

with MockContext() as res:
    processed_resource = f"used_{res}"

# 8. Try / Except error binding
try:
    bad_val = 1 / 0
except ZeroDivisionError as err:
    error_logged = str(err)

# 9. Function definition, parameters, and return
def calculate_metrics(base, scale=2):
    subtotal = base * scale
    return subtotal

final_result = calculate_metrics(total)
'''


def print_analysis_table(result: AnalysisResult) -> None:
    print("=" * 80)
    print(f"  PyChronicle AST Analyzer  Variable Assignment Catalog")
    print(f"  Target: {result.filename}")
    print("=" * 80)

    print(f"\n[Summary]")
    print(f"  - Total assignments detected : {len(result.assignments)}")
    print(f"  - Unique variables cataloged : {len(result.all_variables)}")
    print(f"  - Unique variables list      : {', '.join(sorted(result.all_variables))}")
    print(f"  - Scopes identified          : {', '.join(result.scopes.keys())}")
    print(f"  - Lines with mutations       : {sorted(list(result.variables_by_line.keys()))}")

    print("\n[Detailed Variable Assignment Breakdown]")
    headers = f"{'Line':<6} | {'Target Name':<20} | {'Kind':<16} | {'Scope':<16} | {'Def?':<5}"
    print(headers)
    print("-" * 80)

    for record in result.assignments:
        def_flag = "YES" if record.is_definition else "NO"
        kind_str = record.kind.value
        scope_str = record.scope_name
        if len(scope_str) > 15:
            scope_str = scope_str[:12] + "..."
        target_disp = record.target_name
        if len(target_disp) > 19:
            target_disp = target_disp[:16] + "..."

        line_str = f"L{record.line_number}"
        print(f"{line_str:<6} | {target_disp:<20} | {kind_str:<16} | {scope_str:<16} | {def_flag:<5}")
        if record.raw_code_snippet:
            snippet_first = record.raw_code_snippet.splitlines()[0]
            if len(snippet_first) > 65:
                snippet_first = snippet_first[:62] + "..."
            print(f"       -> Code: {snippet_first}")

    print("\n[Line-to-Variable Mutation Map]")
    for lineno in sorted(result.variables_by_line.keys()):
        vars_mutated = ", ".join(sorted(result.variables_by_line[lineno]))
        print(f"  Line {lineno:3d}: modifies [{vars_mutated}]")

    print("\n" + "=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PyChronicle AST Analyzer: Parse Python code and identify all variable assignments."
    )
    parser.add_argument("script", nargs="?", help="Path to Python script to analyze")
    parser.add_argument("--json", action="store_true", help="Output analysis in JSON format")

    args = parser.parse_args()

    if args.script:
        target_path = Path(args.script)
        if not target_path.exists():
            print(f"Error: Target file '{args.script}' not found.", file=sys.stderr)
            sys.exit(1)
        result = analyze_file(target_path)
    else:
        print("[Notice] No script provided. Running on built-in comprehensive sample...")
        result = analyze_code(DEMO_SAMPLE, filename="demo_sample.py")

    if args.json:
        payload = {
            "filename": result.filename,
            "total_assignments": len(result.assignments),
            "unique_variables": sorted(list(result.all_variables)),
            "assignments": [
                {
                    "target": r.target_name,
                    "line": r.line_number,
                    "col": r.col_offset,
                    "kind": r.kind.value,
                    "scope": r.scope_name,
                    "is_definition": r.is_definition,
                    "snippet": r.raw_code_snippet,
                }
                for r in result.assignments
            ],
            "lines_with_mutations": {
                line: sorted(list(vars_set))
                for line, vars_set in result.variables_by_line.items()
            },
        }
        print(json.dumps(payload, indent=2))
    else:
        print_analysis_table(result)


if __name__ == "__main__":
    main()
