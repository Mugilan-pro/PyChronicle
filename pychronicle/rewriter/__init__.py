"""PyChronicle AST Rewriter Subsystem.

Provides static AST analysis, variable assignment detection, scope mapping,
and dynamic AST rewriting with state capture hooks.
"""

from pychronicle.rewriter.analyzer import ASTAnalyzer, analyze_code, analyze_file
from pychronicle.rewriter.models import (
    AnalysisResult,
    AssignmentKind,
    AssignmentRecord,
    ScopeInfo,
)
from pychronicle.rewriter.transformer import (
    ASTRewriter,
    compile_rewritten,
    rewrite_ast,
    rewrite_code,
)

__all__ = [
    "ASTAnalyzer",
    "ASTRewriter",
    "AnalysisResult",
    "AssignmentKind",
    "AssignmentRecord",
    "ScopeInfo",
    "analyze_code",
    "analyze_file",
    "compile_rewritten",
    "rewrite_ast",
    "rewrite_code",
]
