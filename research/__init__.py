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
from research.persian_ner_benchmark import (
    BenchmarkAggregateSummary,
    bio_tokens_to_spans,
    parse_bio_label,
    parse_conll_data,
    serialize_benchmark_result,
    subwords_to_entity_spans,
)
from research.synthetic_fixtures import (
    SYNTHETIC_CHALLENGE_FIXTURES,
    SyntheticFixture,
)

__all__: list[str] = [
    "SYNTHETIC_CHALLENGE_FIXTURES",
    "BenchmarkAggregateSummary",
    "CorpusEvaluationResult",
    "EntitySpan",
    "ExactSpanMetrics",
    "SpanErrorAnalysis",
    "SyntheticFixture",
    "analyze_errors",
    "bio_tokens_to_spans",
    "calculate_metrics",
    "evaluate_corpus",
    "evaluate_exact_spans",
    "parse_bio_label",
    "parse_conll_data",
    "serialize_benchmark_result",
    "subwords_to_entity_spans",
]
