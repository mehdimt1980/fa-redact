"""Standard-library-only research evaluation harness for Persian NER.

This module provides deterministic, zero-dependency metrics computation for
evaluating Named Entity Recognition (NER) predictions against gold standard
annotations using exact entity span matching.

All metrics are entity-level exact matches: a prediction is a true positive
if and only if (start, end, type) matches a gold entity exactly.
Token-level accuracy is deliberately excluded as it masks entity boundary
errors and provides misleadingly inflated scores for sparse entity tasks.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fa_redact.models import Detection


@dataclass(frozen=True, slots=True)
class EntitySpan:
    """Represents an entity span annotation for evaluation.

    Attributes:
        start: Inclusive start character index in original text.
        end: Exclusive end character index in original text.
        type: Entity type label (e.g., 'PERSON', 'ORG', 'LOC').
    """

    start: int
    end: int
    type: str

    def __post_init__(self) -> None:
        """Validate span invariants."""
        if not isinstance(self.type, str) or not self.type.strip():
            raise ValueError("type must be a non-empty, non-whitespace string")
        if self.start < 0:
            raise ValueError(f"start must be >= 0, got {self.start}")
        if self.end <= self.start:
            raise ValueError(
                f"end ({self.end}) must be strictly greater than start ({self.start})"
            )

    @classmethod
    def from_detection(cls, detection: Detection) -> EntitySpan:
        """Convert a fa_redact Detection instance to an EntitySpan."""
        return cls(
            start=detection.start,
            end=detection.end,
            type=detection.type,
        )

    @classmethod
    def from_tuple(cls, span: tuple[int, int, str]) -> EntitySpan:
        """Convert a (start, end, type) tuple to an EntitySpan."""
        start, end, entity_type = span
        return cls(start=start, end=end, type=entity_type)


@dataclass(frozen=True, slots=True)
class ExactSpanMetrics:
    """Entity-level exact-span evaluation metrics.

    Attributes:
        true_positives: Count of predicted entities matching gold in (start, end, type).
        false_positives: Count of predicted entities with no exact gold match.
        false_negatives: Count of gold entities with no exact predicted match.
        precision: Precision score in range [0.0, 1.0].
        recall: Recall score in range [0.0, 1.0].
        f1: Harmonic mean of precision and recall in range [0.0, 1.0].
        total_gold: Total number of unique gold entities evaluated.
        total_predicted: Total number of unique predicted entities evaluated.
    """

    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    total_gold: int
    total_predicted: int


@dataclass(frozen=True, slots=True)
class CorpusEvaluationResult:
    """Evaluation results across a corpus with micro-averaged and per-type metrics.

    Attributes:
        overall: Overall micro-averaged exact-span metrics.
        by_type: Dictionary mapping each entity type to its exact-span metrics.
        document_count: Number of documents/sentences evaluated.
    """

    overall: ExactSpanMetrics
    by_type: dict[str, ExactSpanMetrics]
    document_count: int


@dataclass(frozen=True, slots=True)
class SpanErrorAnalysis:
    """Detailed categorization of prediction errors for a single document.

    Attributes:
        exact_matches: List of true positive entity spans.
        false_positives: List of predicted entity spans not matching gold.
        false_negatives: List of gold entity spans not predicted.
        boundary_errors: List of pairs (gold, pred) overlapping with mismatched bounds.
        type_mismatches: Pairs (gold, pred) with identical span but differing types.
    """

    exact_matches: list[EntitySpan]
    false_positives: list[EntitySpan]
    false_negatives: list[EntitySpan]
    boundary_errors: list[tuple[EntitySpan, EntitySpan]]
    type_mismatches: list[tuple[EntitySpan, EntitySpan]]


def _coerce_span_list(
    spans: Sequence[EntitySpan | Detection | tuple[int, int, str]],
) -> list[EntitySpan]:
    """Coerce various span representations into a list of EntitySpans."""
    coerced: list[EntitySpan] = []
    for item in spans:
        if isinstance(item, EntitySpan):
            coerced.append(item)
        elif isinstance(item, Detection):
            coerced.append(EntitySpan.from_detection(item))
        elif isinstance(item, tuple) and len(item) == 3:
            coerced.append(EntitySpan.from_tuple(item))
        else:
            raise TypeError(
                f"Unsupported span item type: {type(item).__name__}; "
                "expected EntitySpan, Detection, or (start, end, type) tuple"
            )
    return coerced


def calculate_metrics(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Calculate precision, recall, and F1 given TP, FP, and FN counts.

    If both TP and FP are 0, precision is defined as 1.0 if FN is also 0, else 0.0.
    If both TP and FN are 0, recall is defined as 1.0 if FP is also 0, else 0.0.
    F1 is 0.0 if precision + recall == 0.
    """
    if tp == 0 and fp == 0 and fn == 0:
        return 1.0, 1.0, 1.0

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    if precision + recall > 0.0:
        f1 = (2.0 * precision * recall) / (precision + recall)
    else:
        f1 = 0.0

    return precision, recall, f1


def evaluate_exact_spans(
    gold: Sequence[EntitySpan | Detection | tuple[int, int, str]],
    predicted: Sequence[EntitySpan | Detection | tuple[int, int, str]],
    *,
    duplicate_prediction_policy: str = "count_as_fp",
) -> ExactSpanMetrics:
    """Compute exact-span entity metrics between gold and predicted annotations.

    Enforces that gold annotations contain no duplicate spans (failing loudly with
    ValueError if duplicate gold spans are detected).

    Duplicate predictions are evaluated according to `duplicate_prediction_policy`:
    - 'count_as_fp' (default): the first occurrence of a predicted span matches a gold
      entity (TP); subsequent duplicate predictions of the same span are counted as
      False Positives (FP), penalizing redundant emissions.
    - 'reject': raises ValueError if duplicate predicted spans are detected.

    Args:
        gold: Gold-standard entity spans.
        predicted: Model-predicted entity spans.
        duplicate_prediction_policy: 'count_as_fp' (default) or 'reject'.

    Returns:
        ExactSpanMetrics instance containing counts and precision/recall/F1.

    Raises:
        ValueError: If gold contains duplicate spans, if predicted contains duplicate
            spans under 'reject' policy, or if an invalid policy is passed.
    """
    gold_list = _coerce_span_list(gold)
    pred_list = _coerce_span_list(predicted)

    # Validate gold annotations: duplicates indicate corrupted evaluation data
    gold_set: set[EntitySpan] = set()
    for g in gold_list:
        if g in gold_set:
            raise ValueError(
                f"Duplicate gold entity span detected: start={g.start}, "
                f"end={g.end}, type='{g.type}'"
            )
        gold_set.add(g)

    # Validate prediction policy
    if duplicate_prediction_policy == "reject":
        pred_set: set[EntitySpan] = set()
        for p in pred_list:
            if p in pred_set:
                raise ValueError(
                    f"Duplicate predicted entity span detected: start={p.start}, "
                    f"end={p.end}, type='{p.type}'"
                )
            pred_set.add(p)
    elif duplicate_prediction_policy != "count_as_fp":
        raise ValueError(
            f"Invalid duplicate_prediction_policy '{duplicate_prediction_policy}'; "
            "expected 'count_as_fp' or 'reject'"
        )

    # 1-to-1 exact matching
    matched_gold: set[EntitySpan] = set()
    tp = 0
    fp = 0

    for p in pred_list:
        if p in gold_set and p not in matched_gold:
            tp += 1
            matched_gold.add(p)
        else:
            fp += 1

    fn = len(gold_set) - len(matched_gold)
    precision, recall, f1 = calculate_metrics(tp, fp, fn)

    return ExactSpanMetrics(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        total_gold=len(gold_list),
        total_predicted=len(pred_list),
    )


def evaluate_corpus(
    gold_docs: Sequence[Sequence[EntitySpan | Detection | tuple[int, int, str]]],
    predicted_docs: Sequence[Sequence[EntitySpan | Detection | tuple[int, int, str]]],
    *,
    duplicate_prediction_policy: str = "count_as_fp",
) -> CorpusEvaluationResult:
    """Evaluate exact-span metrics across multiple documents in a corpus.

    Computes overall micro-averaged exact-span metrics and per-entity-type metrics.

    Args:
        gold_docs: Sequence of gold-standard entity spans per document.
        predicted_docs: Sequence of predicted entity spans per document.
        duplicate_prediction_policy: 'count_as_fp' (default) or 'reject'.

    Returns:
        CorpusEvaluationResult with overall and per-type metrics.

    Raises:
        ValueError: If gold_docs and predicted_docs have different lengths.
    """
    if len(gold_docs) != len(predicted_docs):
        raise ValueError(
            f"Document count mismatch: len(gold_docs)={len(gold_docs)} != "
            f"len(predicted_docs)={len(predicted_docs)}"
        )

    all_types: set[str] = set()
    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_gold_count = 0
    total_pred_count = 0

    type_tp: dict[str, int] = {}
    type_fp: dict[str, int] = {}
    type_fn: dict[str, int] = {}
    type_gold_count: dict[str, int] = {}
    type_pred_count: dict[str, int] = {}

    for g_doc, p_doc in zip(gold_docs, predicted_docs, strict=True):
        doc_metrics = evaluate_exact_spans(
            g_doc,
            p_doc,
            duplicate_prediction_policy=duplicate_prediction_policy,
        )
        total_tp += doc_metrics.true_positives
        total_fp += doc_metrics.false_positives
        total_fn += doc_metrics.false_negatives
        total_gold_count += doc_metrics.total_gold
        total_pred_count += doc_metrics.total_predicted

        g_list = _coerce_span_list(g_doc)
        p_list = _coerce_span_list(p_doc)

        for s in g_list:
            all_types.add(s.type)
            type_gold_count[s.type] = type_gold_count.get(s.type, 0) + 1
        for s in p_list:
            all_types.add(s.type)
            type_pred_count[s.type] = type_pred_count.get(s.type, 0) + 1

        g_set = set(g_list)
        matched_g: set[EntitySpan] = set()
        for p in p_list:
            if p in g_set and p not in matched_g:
                type_tp[p.type] = type_tp.get(p.type, 0) + 1
                matched_g.add(p)
            else:
                type_fp[p.type] = type_fp.get(p.type, 0) + 1

        for g in g_list:
            if g not in matched_g:
                type_fn[g.type] = type_fn.get(g.type, 0) + 1

    overall_prec, overall_rec, overall_f1 = calculate_metrics(
        total_tp, total_fp, total_fn
    )
    overall_metrics = ExactSpanMetrics(
        true_positives=total_tp,
        false_positives=total_fp,
        false_negatives=total_fn,
        precision=overall_prec,
        recall=overall_rec,
        f1=overall_f1,
        total_gold=total_gold_count,
        total_predicted=total_pred_count,
    )

    by_type: dict[str, ExactSpanMetrics] = {}
    for entity_type in sorted(all_types):
        tp = type_tp.get(entity_type, 0)
        fp = type_fp.get(entity_type, 0)
        fn = type_fn.get(entity_type, 0)
        type_prec, type_rec, type_f1 = calculate_metrics(tp, fp, fn)
        by_type[entity_type] = ExactSpanMetrics(
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=type_prec,
            recall=type_rec,
            f1=type_f1,
            total_gold=type_gold_count.get(entity_type, 0),
            total_predicted=type_pred_count.get(entity_type, 0),
        )

    return CorpusEvaluationResult(
        overall=overall_metrics,
        by_type=by_type,
        document_count=len(gold_docs),
    )


def analyze_errors(
    gold: Sequence[EntitySpan | Detection | tuple[int, int, str]],
    predicted: Sequence[EntitySpan | Detection | tuple[int, int, str]],
) -> SpanErrorAnalysis:
    """Perform detailed error categorization for gold and predicted spans in a document.

    Categorizes discrepancies into:
    - Exact matches (TP)
    - False positives (FP)
    - False negatives (FN)
    - Boundary errors: gold and predicted spans that overlap with mismatched offsets
    - Type mismatches: identical [start:end] offset span with differing entity type

    Args:
        gold: Gold-standard entity spans.
        predicted: Predicted entity spans.

    Returns:
        SpanErrorAnalysis detailing error categories.
    """
    gold_spans = _coerce_span_list(gold)
    pred_spans = _coerce_span_list(predicted)

    exact_matches: list[EntitySpan] = []
    false_positives: list[EntitySpan] = []
    false_negatives: list[EntitySpan] = []
    boundary_errors: list[tuple[EntitySpan, EntitySpan]] = []
    type_mismatches: list[tuple[EntitySpan, EntitySpan]] = []

    matched_gold: set[EntitySpan] = set()
    matched_pred: set[EntitySpan] = set()

    # 1. Exact matches
    for g in gold_spans:
        for p in pred_spans:
            if g.start == p.start and g.end == p.end and g.type == p.type:
                exact_matches.append(g)
                matched_gold.add(g)
                matched_pred.add(p)
                break

    unmatched_gold = [g for g in gold_spans if g not in matched_gold]
    unmatched_pred = [p for p in pred_spans if p not in matched_pred]

    # 2. Type mismatches (identical span, differing type)
    for g in unmatched_gold:
        for p in unmatched_pred:
            if g.start == p.start and g.end == p.end and g.type != p.type:
                type_mismatches.append((g, p))

    # 3. Boundary errors (overlapping spans, start1 < end2 and start2 < end1)
    for g in unmatched_gold:
        for p in unmatched_pred:
            if g.start == p.start and g.end == p.end:
                continue  # already captured in type mismatch
            # Check overlap
            overlap_start = max(g.start, p.start)
            overlap_end = min(g.end, p.end)
            if overlap_start < overlap_end:
                boundary_errors.append((g, p))

    # 4. FP and FN lists
    for p in unmatched_pred:
        false_positives.append(p)
    for g in unmatched_gold:
        false_negatives.append(g)

    return SpanErrorAnalysis(
        exact_matches=sorted(exact_matches, key=lambda s: (s.start, s.end, s.type)),
        false_positives=sorted(false_positives, key=lambda s: (s.start, s.end, s.type)),
        false_negatives=sorted(false_negatives, key=lambda s: (s.start, s.end, s.type)),
        boundary_errors=boundary_errors,
        type_mismatches=type_mismatches,
    )
