"""Performance analysis library: no orchestration or database dependencies."""

from .evaluator import compare_candidate, evaluate_candidate
from .normalizer import K6Normalizer
from .report import build_analysis_report
from .validation import parse_analysis, parse_normalized, parse_policy

__all__ = [
    "K6Normalizer",
    "build_analysis_report",
    "compare_candidate",
    "evaluate_candidate",
    "parse_analysis",
    "parse_normalized",
    "parse_policy",
]
__version__ = "0.5.0"
