"""Deterministic offline runner for synthetic detector evaluation.

This module executes fa-redact detectors against the synthetic detection corpus,
computes exact-span precision, recall, and F1 across detector suites, entity types,
and linguistic/syntactic categories, and serializes privacy-safe, value-free results.

Zero external runtime dependencies are required. Model execution and network
lookups are strictly excluded.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fa_redact.detectors.bank_card import BankCardDetector
from fa_redact.detectors.email import EmailDetector
from fa_redact.detectors.legal_entity_id import IranianLegalEntityIDDetector
from fa_redact.detectors.pattern import PatternDetector
from fa_redact.pipeline import detect
from fa_redact.protocols import Detector
from research.detection_corpus import (
    SYNTHETIC_DETECTION_CORPUS,
    SYNTHETIC_PATTERN_RULES,
    SyntheticDetectionCase,
    validate_detection_corpus,
)
from research.evaluation import (
    EntitySpan,
    ExactSpanMetrics,
    evaluate_corpus,
    evaluate_exact_spans,
)

SCHEMA_VERSION: str = "1.0.0"
TOOL_IDENTIFIER: str = "fa-redact synthetic detection corpus benchmark runner"

# Suite to detector mapping
DEFAULT_SUITE_DETECTORS: dict[str, Sequence[Detector] | None] = {
    "default": None,
    "email": (EmailDetector(),),
    "bank_card": (BankCardDetector(),),
    "pattern": (PatternDetector(SYNTHETIC_PATTERN_RULES),),
    "legal_entity_id": (IranianLegalEntityIDDetector(),),
}


@dataclass(frozen=True, slots=True)
class DetectionBenchmarkResult:
    """Privacy-safe, value-free result container for detection corpus evaluation.

    Attributes:
        schema_version: Semantic version of the output schema.
        generated_by: Tool identifier.
        case_count: Number of synthetic cases evaluated.
        gold_entity_count: Total number of gold entity spans in the corpus.
        prediction_count: Total number of predicted entity spans emitted.
        overall: Micro-averaged exact-span metrics across the entire corpus.
        by_type: Exact-span metrics per entity type (e.g. 'IR_NATIONAL_ID', 'EMAIL').
        by_category: Exact-span metrics per test category.
        failed_case_ids: Sorted tuple of IDs for cases with non-matching predictions.
    """

    schema_version: str
    generated_by: str
    case_count: int
    gold_entity_count: int
    prediction_count: int
    overall: ExactSpanMetrics
    by_type: dict[str, ExactSpanMetrics]
    by_category: dict[str, ExactSpanMetrics]
    failed_case_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert benchmark results to a value-free, privacy-safe dictionary."""

        def _metrics_dict(m: ExactSpanMetrics) -> dict[str, Any]:
            return {
                "f1": m.f1,
                "false_negatives": m.false_negatives,
                "false_positives": m.false_positives,
                "precision": m.precision,
                "recall": m.recall,
                "total_gold": m.total_gold,
                "total_predicted": m.total_predicted,
                "true_positives": m.true_positives,
            }

        return {
            "by_category": {
                k: _metrics_dict(v) for k, v in sorted(self.by_category.items())
            },
            "by_type": {k: _metrics_dict(v) for k, v in sorted(self.by_type.items())},
            "case_count": self.case_count,
            "failed_case_ids": list(self.failed_case_ids),
            "generated_by": self.generated_by,
            "gold_entity_count": self.gold_entity_count,
            "overall": _metrics_dict(self.overall),
            "prediction_count": self.prediction_count,
            "schema_version": self.schema_version,
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize benchmark result to deterministic JSON format."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True) + "\n"


def run_detection_corpus_benchmark(
    corpus: Sequence[SyntheticDetectionCase] | None = None,
    *,
    suite_detectors: Mapping[str, Sequence[Detector] | None] | None = None,
    duplicate_prediction_policy: str = "count_as_fp",
) -> DetectionBenchmarkResult:
    """Execute detection evaluation over the synthetic regression corpus.

    Args:
        corpus: Optional custom sequence of SyntheticDetectionCase instances.
            Defaults to SYNTHETIC_DETECTION_CORPUS.
        suite_detectors: Optional custom mapping of suite names to detector sequences.
            Defaults to DEFAULT_SUITE_DETECTORS.
        duplicate_prediction_policy: 'count_as_fp' (default) or 'reject'.

    Returns:
        DetectionBenchmarkResult containing overall, per-type, and per-category metrics.

    Raises:
        ValueError: If an unknown suite name is encountered.
    """
    cases = (
        validate_detection_corpus(corpus)
        if corpus is not None
        else SYNTHETIC_DETECTION_CORPUS
    )
    detector_map = (
        suite_detectors if suite_detectors is not None else DEFAULT_SUITE_DETECTORS
    )

    all_gold_docs: list[tuple[EntitySpan, ...]] = []
    all_pred_docs: list[list[EntitySpan]] = []
    failed_ids: list[str] = []

    # Category tracking
    category_cases: dict[
        str, list[tuple[tuple[EntitySpan, ...], list[EntitySpan]]]
    ] = {}

    for case in cases:
        if case.suite not in detector_map:
            raise ValueError(
                f"Unknown suite {case.suite!r} in case {case.id!r}; "
                f"expected one of {sorted(detector_map.keys())}"
            )

        active_detectors = detector_map[case.suite]
        detections = detect(case.text, detectors=active_detectors)
        pred_spans = [EntitySpan.from_detection(d) for d in detections]

        all_gold_docs.append(case.gold_spans)
        all_pred_docs.append(pred_spans)

        # Track per-category
        if case.category not in category_cases:
            category_cases[case.category] = []
        category_cases[case.category].append((case.gold_spans, pred_spans))

        # Check for case failure
        doc_metrics = evaluate_exact_spans(
            case.gold_spans,
            pred_spans,
            duplicate_prediction_policy=duplicate_prediction_policy,
        )
        if doc_metrics.false_positives > 0 or doc_metrics.false_negatives > 0:
            failed_ids.append(case.id)

    # Corpus overall and per-type metrics
    corpus_eval = evaluate_corpus(
        all_gold_docs,
        all_pred_docs,
        duplicate_prediction_policy=duplicate_prediction_policy,
    )

    # Compute per-category metrics
    by_category: dict[str, ExactSpanMetrics] = {}
    for cat_name in sorted(category_cases.keys()):
        cat_gold = [item[0] for item in category_cases[cat_name]]
        cat_pred = [item[1] for item in category_cases[cat_name]]
        cat_eval = evaluate_corpus(
            cat_gold,
            cat_pred,
            duplicate_prediction_policy=duplicate_prediction_policy,
        )
        by_category[cat_name] = cat_eval.overall

    return DetectionBenchmarkResult(
        schema_version=SCHEMA_VERSION,
        generated_by=TOOL_IDENTIFIER,
        case_count=len(cases),
        gold_entity_count=sum(len(g) for g in all_gold_docs),
        prediction_count=sum(len(p) for p in all_pred_docs),
        overall=corpus_eval.overall,
        by_type=corpus_eval.by_type,
        by_category=by_category,
        failed_case_ids=tuple(sorted(failed_ids)),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for running the synthetic detection benchmark."""
    parser = argparse.ArgumentParser(
        prog="detection_corpus_benchmark",
        description="Run offline evaluation against the synthetic detection corpus.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Path to write the resulting JSON benchmark report.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with non-zero status if any case fails or F1 < 1.0.",
    )

    args = parser.parse_args(argv)

    print("=" * 70)
    print("fa-redact Synthetic Detection Corpus Benchmark Runner")
    print("=" * 70)

    result = run_detection_corpus_benchmark()

    print(f"Cases Evaluated: {result.case_count}")
    print(f"Gold Entities:   {result.gold_entity_count}")
    print(f"Predictions:     {result.prediction_count}")
    print(
        f"Overall:         TP={result.overall.true_positives} "
        f"FP={result.overall.false_positives} "
        f"FN={result.overall.false_negatives} | "
        f"Prec={result.overall.precision:.4f} "
        f"Rec={result.overall.recall:.4f} "
        f"F1={result.overall.f1:.4f}"
    )
    print("-" * 70)
    print("Per-Type Results:")
    for entity_type, m in sorted(result.by_type.items()):
        print(
            f"  {entity_type:<18}: TP={m.true_positives:<3} FP={m.false_positives:<3} "
            f"FN={m.false_negatives:<3} | P={m.precision:.4f} "
            f"R={m.recall:.4f} F1={m.f1:.4f}"
        )
    print("-" * 70)
    print(f"Failed Case IDs: {list(result.failed_case_ids)}")
    print("=" * 70)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        json_str = result.to_json()
        args.output.write_text(json_str, encoding="utf-8")
        print(f"Results written to: {args.output}")

    if args.check or result.failed_case_ids:
        if result.failed_case_ids or result.overall.f1 < 1.0:
            print(
                f"FAILED: {len(result.failed_case_ids)} failed cases detected.",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
