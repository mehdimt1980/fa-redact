"""Unit tests for the research evaluation harness and synthetic challenge fixtures."""

from __future__ import annotations

import pytest
from research.evaluation import (
    EntitySpan,
    ExactSpanMetrics,
    analyze_errors,
    calculate_metrics,
    evaluate_corpus,
    evaluate_exact_spans,
)
from research.synthetic_fixtures import SYNTHETIC_CHALLENGE_FIXTURES

from fa_redact.models import Detection


class TestCalculateMetrics:
    """Tests for raw calculate_metrics function."""

    def test_all_zeros_returns_perfect(self) -> None:
        p, r, f1 = calculate_metrics(0, 0, 0)
        assert p == 1.0
        assert r == 1.0
        assert f1 == 1.0

    def test_perfect_matches(self) -> None:
        p, r, f1 = calculate_metrics(10, 0, 0)
        assert p == 1.0
        assert r == 1.0
        assert f1 == 1.0

    def test_zero_precision_when_all_fp(self) -> None:
        p, r, f1 = calculate_metrics(0, 5, 0)
        assert p == 0.0
        assert r == 0.0
        assert f1 == 0.0

    def test_zero_recall_when_all_fn(self) -> None:
        p, r, f1 = calculate_metrics(0, 0, 5)
        assert p == 0.0
        assert r == 0.0
        assert f1 == 0.0

    def test_mixed_precision_and_recall(self) -> None:
        # TP=4, FP=1, FN=1 -> Prec = 4/5 = 0.8, Rec = 4/5 = 0.8, F1 = 0.8
        p, r, f1 = calculate_metrics(4, 1, 1)
        assert p == pytest.approx(0.8)
        assert r == pytest.approx(0.8)
        assert f1 == pytest.approx(0.8)


class TestEntitySpanModel:
    """Tests for EntitySpan construction and validation."""

    def test_valid_span(self) -> None:
        span = EntitySpan(start=0, end=10, type="PERSON")
        assert span.start == 0
        assert span.end == 10
        assert span.type == "PERSON"

    def test_invalid_negative_start(self) -> None:
        with pytest.raises(ValueError, match="start must be >= 0"):
            EntitySpan(start=-1, end=5, type="PERSON")

    def test_invalid_end_before_start(self) -> None:
        with pytest.raises(ValueError, match="end .* strictly greater"):
            EntitySpan(start=5, end=5, type="PERSON")
        with pytest.raises(ValueError, match="end .* strictly greater"):
            EntitySpan(start=6, end=5, type="PERSON")

    def test_invalid_empty_type(self) -> None:
        with pytest.raises(ValueError, match="type must be a non-empty"):
            EntitySpan(start=0, end=5, type="")
        with pytest.raises(ValueError, match="type must be a non-empty"):
            EntitySpan(start=0, end=5, type="   ")

    def test_from_detection(self) -> None:
        det = Detection(
            type="PERSON",
            start=2,
            end=7,
            value="احمدی",
            normalized_value="احمدی",
        )
        span = EntitySpan.from_detection(det)
        assert span.start == 2
        assert span.end == 7
        assert span.type == "PERSON"

    def test_from_tuple(self) -> None:
        span = EntitySpan.from_tuple((3, 7, "ORG"))
        assert span.start == 3
        assert span.end == 7
        assert span.type == "ORG"


class TestEvaluateExactSpans:
    """Tests for evaluate_exact_spans."""

    def test_perfect_match(self) -> None:
        gold = [EntitySpan(0, 10, "PERSON"), EntitySpan(15, 25, "ORG")]
        pred = [EntitySpan(0, 10, "PERSON"), EntitySpan(15, 25, "ORG")]
        metrics = evaluate_exact_spans(gold, pred)

        assert metrics.true_positives == 2
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0
        assert metrics.total_gold == 2
        assert metrics.total_predicted == 2

    def test_zero_predictions(self) -> None:
        gold = [EntitySpan(0, 10, "PERSON"), EntitySpan(15, 25, "ORG")]
        pred: list[EntitySpan] = []
        metrics = evaluate_exact_spans(gold, pred)

        assert metrics.true_positives == 0
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 2
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0
        assert metrics.total_gold == 2
        assert metrics.total_predicted == 0

    def test_empty_gold_empty_pred(self) -> None:
        empty: list[EntitySpan] = []
        metrics = evaluate_exact_spans(empty, empty)
        assert metrics.true_positives == 0
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0
        assert metrics.total_gold == 0
        assert metrics.total_predicted == 0

    def test_empty_gold_with_predictions(self) -> None:
        empty: list[EntitySpan] = []
        pred = [EntitySpan(0, 5, "PERSON")]
        metrics = evaluate_exact_spans(empty, pred)
        assert metrics.true_positives == 0
        assert metrics.false_positives == 1
        assert metrics.false_negatives == 0
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0

    def test_exact_span_boundary_mismatch_penalty(self) -> None:
        # Off-by-one span is strictly 1 FP and 1 FN (no partial score)
        gold = [(0, 10, "PERSON")]
        pred = [(0, 11, "PERSON")]
        metrics = evaluate_exact_spans(gold, pred)

        assert metrics.true_positives == 0
        assert metrics.false_positives == 1
        assert metrics.false_negatives == 1
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0

    def test_entity_type_mismatch_penalty(self) -> None:
        gold = [(5, 15, "PERSON")]
        pred = [(5, 15, "ORG")]
        metrics = evaluate_exact_spans(gold, pred)

        assert metrics.true_positives == 0
        assert metrics.false_positives == 1
        assert metrics.false_negatives == 1
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0

    def test_duplicate_prediction_deduplication(self) -> None:
        gold = [(0, 10, "PERSON")]
        pred = [(0, 10, "PERSON"), (0, 10, "PERSON"), (0, 10, "PERSON")]
        metrics = evaluate_exact_spans(gold, pred)

        assert metrics.true_positives == 1
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0
        assert metrics.total_predicted == 1

    def test_mixed_span_input_types(self) -> None:
        # Mix of EntitySpan, Detection, and tuple
        gold: list[EntitySpan | tuple[int, int, str]] = [
            EntitySpan(0, 4, "PERSON"),
            (10, 15, "ORG"),
        ]
        det = Detection(
            type="PERSON",
            start=0,
            end=4,
            value="سارا",
            normalized_value="سارا",
        )
        pred: list[Detection | tuple[int, int, str]] = [det, (10, 15, "ORG")]
        metrics = evaluate_exact_spans(gold, pred)

        assert metrics.true_positives == 2
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0

    def test_unsupported_span_type_raises_error(self) -> None:
        with pytest.raises(TypeError, match="Unsupported span item type"):
            evaluate_exact_spans(["invalid_string"], [])  # type: ignore[list-item]


class TestEvaluateCorpus:
    """Tests for multi-document corpus evaluation."""

    def test_corpus_micro_averaging(self) -> None:
        doc1_gold = [(0, 5, "PERSON"), (10, 20, "ORG")]
        doc1_pred = [(0, 5, "PERSON")]  # 1 TP, 1 FN

        doc2_gold = [(0, 10, "PERSON")]
        doc2_pred = [(0, 10, "PERSON"), (15, 20, "LOC")]  # 1 TP, 1 FP

        result = evaluate_corpus([doc1_gold, doc2_gold], [doc1_pred, doc2_pred])

        assert result.document_count == 2
        assert result.overall.true_positives == 2
        assert result.overall.false_positives == 1
        assert result.overall.false_negatives == 1
        assert result.overall.total_gold == 3
        assert result.overall.total_predicted == 3

        # Precision = 2/3, Recall = 2/3, F1 = 2/3
        assert result.overall.precision == pytest.approx(2 / 3)
        assert result.overall.recall == pytest.approx(2 / 3)
        assert result.overall.f1 == pytest.approx(2 / 3)

        # Per-type breakdown
        assert "PERSON" in result.by_type
        person_metrics: ExactSpanMetrics = result.by_type["PERSON"]
        assert person_metrics.true_positives == 2
        assert person_metrics.false_positives == 0
        assert person_metrics.false_negatives == 0
        assert person_metrics.precision == 1.0
        assert person_metrics.recall == 1.0
        assert person_metrics.f1 == 1.0

        org_metrics: ExactSpanMetrics = result.by_type["ORG"]
        assert org_metrics.true_positives == 0
        assert org_metrics.false_negatives == 1
        assert org_metrics.precision == 0.0

        loc_metrics: ExactSpanMetrics = result.by_type["LOC"]
        assert loc_metrics.true_positives == 0
        assert loc_metrics.false_positives == 1
        assert loc_metrics.precision == 0.0

    def test_corpus_mismatched_doc_count_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Document count mismatch"):
            evaluate_corpus([[(0, 5, "PERSON")]], [])


class TestAnalyzeErrors:
    """Tests for detailed error categorization."""

    def test_boundary_error_identification(self) -> None:
        gold = [(0, 10, "PERSON")]
        pred = [(0, 8, "PERSON")]
        analysis = analyze_errors(gold, pred)

        assert len(analysis.exact_matches) == 0
        assert len(analysis.false_positives) == 1
        assert len(analysis.false_negatives) == 1
        assert len(analysis.boundary_errors) == 1
        g_err, p_err = analysis.boundary_errors[0]
        assert g_err == EntitySpan(0, 10, "PERSON")
        assert p_err == EntitySpan(0, 8, "PERSON")
        assert len(analysis.type_mismatches) == 0

    def test_type_mismatch_identification(self) -> None:
        gold = [(0, 10, "PERSON")]
        pred = [(0, 10, "ORG")]
        analysis = analyze_errors(gold, pred)

        assert len(analysis.exact_matches) == 0
        assert len(analysis.type_mismatches) == 1
        g_err, p_err = analysis.type_mismatches[0]
        assert g_err.type == "PERSON"
        assert p_err.type == "ORG"
        assert len(analysis.boundary_errors) == 0


class TestSyntheticChallengeFixtures:
    """Verification of all synthetic challenge fixtures."""

    def test_fixtures_count_and_categories(self) -> None:
        assert len(SYNTHETIC_CHALLENGE_FIXTURES) >= 12
        categories = {f.category for f in SYNTHETIC_CHALLENGE_FIXTURES}
        assert "standard_name" in categories
        assert "compound_surname" in categories
        assert "honorific_prefix" in categories
        assert "common_noun_ambiguity" in categories
        assert "zwnj_variant" in categories
        assert "arabic_char_variants" in categories
        assert "punctuation_boundary" in categories
        assert "adjacent_identifier" in categories
        assert "repeated_name" in categories
        assert "clinical_context" in categories
        assert "negative_control" in categories

    def test_all_fixture_offsets_slice_valid_substrings(self) -> None:
        for fixture in SYNTHETIC_CHALLENGE_FIXTURES:
            fixture.verify_spans()
            for span in fixture.gold_spans:
                sub = fixture.text[span.start : span.end]
                assert len(sub) == span.end - span.start
                assert len(sub) > 0

    def test_fixture_evaluation_roundtrip(self) -> None:
        # Evaluating gold against gold on all fixtures should yield 100% metrics
        gold_docs = [f.gold_spans for f in SYNTHETIC_CHALLENGE_FIXTURES]
        pred_docs = [f.gold_spans for f in SYNTHETIC_CHALLENGE_FIXTURES]

        result = evaluate_corpus(gold_docs, pred_docs)
        assert result.document_count == len(SYNTHETIC_CHALLENGE_FIXTURES)
        assert result.overall.precision == 1.0
        assert result.overall.recall == 1.0
        assert result.overall.f1 == 1.0
        assert result.overall.false_positives == 0
        assert result.overall.false_negatives == 0
