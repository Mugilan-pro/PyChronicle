import ast
import keyword
import tokenize
from io import StringIO


class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.variables = set()
        self.assignments = 0
        self.functions = 0
        self.classes = 0

    # Normal assignments:
    # x = 10
    def visit_Assign(self, node):
        self.assignments += 1

        for target in node.targets:
            self.collect_variables(target)

        self.generic_visit(node)

    # x += 1, x -= 1, etc.
    def visit_AugAssign(self, node):
        self.assignments += 1
        self.collect_variables(node.target)
        self.generic_visit(node)

    def collect_variables(self, node):
        if isinstance(node, ast.Name):
            self.variables.add(node.id)

        elif isinstance(node, (ast.Tuple, ast.List)):
            for element in node.elts:
                self.collect_variables(element)

    def visit_FunctionDef(self, node):
        self.functions += 1

        # Function parameters are also variables
        for arg in node.args.args:
            self.variables.add(arg.arg)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.functions += 1

        for arg in node.args.args:
            self.variables.add(arg.arg)

        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.classes += 1
        self.generic_visit(node)


def calculate_assignment_score(assignments):
    """
    Assignment score:
    More assignments = higher score.
    """
    return assignments * 10


def calculate_lexical_score(source_code):
    """
    Calculate lexical score using:
    - identifiers
    - keywords
    - operators
    - literals
    """

    identifiers = 0
    keywords = 0
    operators = 0
    literals = 0

    try:
        tokens = tokenize.generate_tokens(StringIO(source_code).readline)

        for token in tokens:
            token_type = token.type
            token_value = token.string

            # Names such as x, total, calculate
            if token_type == tokenize.NAME:

                if keyword.iskeyword(token_value):
                    keywords += 1
                else:
                    identifiers += 1

            # Operators such as +, -, *, =, ==, etc.
            elif token_type == tokenize.OP:
                operators += 1

            # Numbers and strings
            elif token_type == tokenize.NUMBER:
                literals += 1

            elif token_type == tokenize.STRING:
                literals += 1

    except tokenize.TokenError:
        pass

    total_tokens = identifiers + keywords + operators + literals

    if total_tokens == 0:
        return 0

    # Simple lexical complexity score
    score = (
        identifiers * 1
        + keywords * 2
        + operators * 2
        + literals * 1
    )

    return score


def analyze_code(source_code):
    """
    Analyze Python source code and return all scores.
    """

    try:
        tree = ast.parse(source_code)
    except SyntaxError as error:
        return {
            "error": f"Syntax Error: {error}"
        }

    analyzer = CodeAnalyzer()
    analyzer.visit(tree)

    unique_variables = len(analyzer.variables)

    assignment_score = calculate_assignment_score(
        analyzer.assignments
    )

    lexical_score = calculate_lexical_score(
        source_code
    )

    return {
        "unique_variables": unique_variables,
        "variables": sorted(analyzer.variables),
        "assignments": analyzer.assignments,
        "assignment_score": assignment_score,
        "functions": analyzer.functions,
        "classes": analyzer.classes,
        "lexical_score": lexical_score
    }


# --------------------------------------------------
# Example
# --------------------------------------------------

code = """
x = 10
y = 20
total = x + y
name = "Mugilan"

def calculate(a, b):
    result = a + b
    return result

total = calculate(x, y)
"""

result = analyze_code(code)

print("===== CODE ANALYSIS =====")

if "error" in result:
    print(result["error"])
else:
    print("Unique Variables :", result["unique_variables"])
    print("Variables        :", result["variables"])
    print("Assignments      :", result["assignments"])
    print("Assignment Score :", result["assignment_score"])
    print("Functions        :", result["functions"])
    print("Classes          :", result["classes"])
    print("Lexical Score    :", result["lexical_score"])