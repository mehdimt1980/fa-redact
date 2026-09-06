"""Research utilities and evaluation harnesses for fa-redact."""

from __future__ import annotations

from research.evaluation import (
    CorpusEvaluationResult,
    EntitySpan,
    ExactSpanMetrics,
    SpanErrorAnalysis,
    analyze_errors,
    calculate_metrics,
    evaluate_corpus,
    evaluate_exact_spans,
)
from research.synthetic_fixtures import (
    SYNTHETIC_CHALLENGE_FIXTURES,
    SyntheticFixture,
)

__all__: list[str] = [
    "SYNTHETIC_CHALLENGE_FIXTURES",
    "CorpusEvaluationResult",
    "EntitySpan",
    "ExactSpanMetrics",
    "SpanErrorAnalysis",
    "SyntheticFixture",
    "analyze_errors",
    "calculate_metrics",
    "evaluate_corpus",
    "evaluate_exact_spans",
]
