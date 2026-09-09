"""Performance analysis library: no orchestration or database dependencies."""

from .evaluator import compare_candidate, evaluate_candidate
from .kube_burner_normalizer import KubeBurnerNormalizer
from .normalizer import K6Normalizer
from .playwright_normalizer import PlaywrightNormalizer
from .report import ReferenceInput, build_analysis_report
from .validation import parse_analysis, parse_normalized, parse_policy

__all__ = [
    "K6Normalizer",
    "KubeBurnerNormalizer",
    "PlaywrightNormalizer",
    "ReferenceInput",
    "build_analysis_report",
    "compare_candidate",
    "evaluate_candidate",
    "parse_analysis",
    "parse_normalized",
    "parse_policy",
]
__version__ = "0.8.1"
