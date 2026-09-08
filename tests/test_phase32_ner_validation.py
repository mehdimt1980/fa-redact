"""Tests for Phase 32 Persian NER Backend Validation & Readiness Gate.

Uses mocks, fakes, and synthetic fixtures. Zero network, zero model downloads,
and zero heavy GPU/CPU model loading during standard pytest.

Verifies:
1. Exact PERSON matching metrics
2. FP/FN calculation
3. Leakage calculation
4. Negative-document FP calculation and None/null representation when count == 0
5. Offset integrity detection
6. Mismatched Detection.value vs source slice is an offset/integrity failure
7. Adapter exception recorded as type-only metadata (no text leakage)
8. Deterministic comparison across multiple runs
9. Gate PASS calculation when all gates met
10. Gate FAIL on quality regression
11. Gate FAIL on offset failure
12. Gate FAIL on adapter error
13. Gate FAIL on nondeterminism
14. Gate FAIL on long-document failure
15. Non-invasive ModelCallTracker restores original model/session even on error
16. Tokenizer token count distinct from whitespace word count
17. Long document sliding-window requirement and multiple calls verification
18. Long document nondeterminism causes long-document gate to fail
19. Observed model input length bounds enforcement
20. Result JSON contains no raw text, PERSON values, or absolute model paths
21. Phase 29 thresholds and baselines are locked constants
22. Core package invariants remain intact (dependencies = [], version = 0.3.0)
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from research.evaluation import EntitySpan
from research.phase29_challenge_set import ChallengeDocument
from research.phase32_ner_validation import (
    LOCKED_BASELINES,
    LOCKED_QUALITY_GATES,
    PEYMA_BACKEND_CLASS,
    PEYMA_LICENSE,
    PEYMA_MODEL_ID,
    PEYMA_REVISION,
    TOOKABERT_BACKEND_CLASS,
    TOOKABERT_LICENSE,
    TOOKABERT_MODEL_ID,
    TOOKABERT_REVISION,
    DatasetEvaluationMetrics,
    compute_gate_decisions,
    evaluate_detector_on_corpus,
    evaluate_determinism,
    evaluate_long_documents,
    generate_recommendation,
    get_full_token_count,
    track_model_calls,
)
from research.phase32_ner_validation_cases import (
    ValidationDocument,
    build_long_documents,
    build_targeted_normalization_cases,
)

from fa_redact import __version__
from fa_redact.models import Detection


@dataclass(frozen=True, slots=True)
class FakeDetection:
    """Duck-typed detection for testing boundary edge cases."""

    type: str
    start: int
    end: int
    value: str
    normalized_value: str


class MockDetector:
    """Mock detector returning configurable predictions or raising errors."""

    def __init__(
        self,
        prediction_map: dict[str, list[Any]] | None = None,
        exception_map: dict[str, Exception] | None = None,
        default_detections: list[Any] | None = None,
        tokenizer: Any = None,
        max_length: int = 512,
    ) -> None:
        self.prediction_map = prediction_map or {}
        self.exception_map = exception_map or {}
        self.default_detections = default_detections or []
        self._tokenizer = tokenizer
        self._max_length = max_length

    def detect(self, original_text: str, normalized_text: str) -> list[Any]:
        if original_text in self.exception_map:
            raise self.exception_map[original_text]
        return self.prediction_map.get(original_text, self.default_detections)


def test_package_metadata_and_zero_runtime_dependencies() -> None:
    """Verify package version is 0.4.0 and base dependencies remain empty."""
    assert __version__ == "0.4.0"

    pyproject_path = Path("pyproject.toml")
    assert pyproject_path.exists()
    content = pyproject_path.read_text(encoding="utf-8")

    assert "dependencies = []" in content
    assert 'version = "0.4.0"' in content


def test_production_src_unmodified_and_isolated() -> None:
    """Verify production src/ does not import research modules."""
    src_dir = Path("src/fa_redact")
    forbidden_modules = {"research"}

    for py_file in src_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    assert root_mod not in forbidden_modules, (
                        f"Production file {py_file} imports forbidden "
                        f"module: {root_mod}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_mod = node.module.split(".")[0]
                assert root_mod not in forbidden_modules, (
                    f"Production file {py_file} imports from forbidden "
                    f"module: {root_mod}"
                )


def test_exact_person_matching_metrics() -> None:
    """Verify exact PERSON span matching produces accurate TP, FP, FN, P, R, F1."""
    text = "بیمار علی رضایی توسط دکتر مریم احمدی ویزیت شد."
    # Gold: "علی رضایی" [6:15], "مریم احمدی" [27:37]
    gold_spans = (
        EntitySpan(start=6, end=15, type="PERSON"),
        EntitySpan(start=27, end=37, type="PERSON"),
    )
    doc = ChallengeDocument(
        doc_id="TEST_01",
        dataset="test",
        category="test",
        description="test",
        text=text,
        gold_spans=gold_spans,
    )

    # Detector predicts exact "علی رضایی" and extra "دکتر" as PERSON
    preds = [
        Detection(
            type="PERSON",
            start=6,
            end=15,
            value="علی رضایی",
            normalized_value="علی رضایی",
        ),
        Detection(
            type="PERSON",
            start=21,
            end=25,
            value="دکتر",
            normalized_value="دکتر",
        ),  # FP
    ]
    det = MockDetector(prediction_map={text: preds})

    metrics = evaluate_detector_on_corpus(det, [doc], "TestDataset")
    assert metrics.true_positives == 1
    assert metrics.false_positives == 1
    assert metrics.false_negatives == 1
    assert metrics.total_gold == 2
    assert metrics.total_predicted == 2
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.f1 == 0.5
    assert metrics.entity_leakage_rate == 0.5
    assert metrics.offset_failures == 0
    assert metrics.adapter_error_count == 0


def test_fp_fn_and_leakage_calculation() -> None:
    """Verify entity leakage rate matches FN / total_gold."""
    text = "علی رضایی و سارا محمدی و رضا نوری"
    # Gold: 3 PERSON entities
    gold = (
        EntitySpan(start=0, end=9, type="PERSON"),
        EntitySpan(start=12, end=22, type="PERSON"),
        EntitySpan(start=25, end=33, type="PERSON"),
    )
    doc = ChallengeDocument(
        doc_id="TEST_LEAK",
        dataset="test",
        category="test",
        description="test",
        text=text,
        gold_spans=gold,
    )

    # Predict only 1 of 3
    preds = [
        Detection(
            type="PERSON",
            start=0,
            end=9,
            value="علی رضایی",
            normalized_value="علی رضایی",
        )
    ]
    det = MockDetector(prediction_map={text: preds})

    metrics = evaluate_detector_on_corpus(det, [doc], "LeakDataset")
    assert metrics.true_positives == 1
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 2
    assert metrics.entity_leakage_rate == pytest.approx(2 / 3, 0.001)


def test_negative_document_fp_calculation() -> None:
    """Verify negative-document false positive rate and count calculation."""
    neg1_text = "آب و هوای امروز تهران بارانی و خنک است."
    neg2_text = "میزان قند خون ناشتای بیمار ۹۵ گزارش شد."
    pos_text = "دکتر علی رضایی ویزیت نمودند."

    doc_neg1 = ChallengeDocument(
        doc_id="NEG_01",
        dataset="test",
        category="neg",
        description="neg",
        text=neg1_text,
        gold_spans=(),
    )
    doc_neg2 = ChallengeDocument(
        doc_id="NEG_02",
        dataset="test",
        category="neg",
        description="neg",
        text=neg2_text,
        gold_spans=(),
    )
    doc_pos = ChallengeDocument(
        doc_id="POS_01",
        dataset="test",
        category="pos",
        description="pos",
        text=pos_text,
        gold_spans=(EntitySpan(start=5, end=14, type="PERSON"),),
    )

    pred_neg1 = [
        Detection(
            type="PERSON",
            start=0,
            end=9,
            value="آب و هوای",
            normalized_value="آب و هوای",
        )
    ]
    pred_pos = [
        Detection(
            type="PERSON",
            start=5,
            end=14,
            value="علی رضایی",
            normalized_value="علی رضایی",
        )
    ]

    det = MockDetector(
        prediction_map={
            neg1_text: pred_neg1,
            neg2_text: [],
            pos_text: pred_pos,
        }
    )

    metrics = evaluate_detector_on_corpus(det, [doc_neg1, doc_neg2, doc_pos], "NegTest")
    assert metrics.negative_document_count == 2
    assert metrics.negative_documents_with_fp == 1
    assert metrics.negative_document_fp_rate == 0.5
    assert metrics.total_fp_in_negative_docs == 1


def test_undefined_negative_doc_fp_rate_represented_as_none_and_null() -> None:
    """Verify negative_document_fp_rate is None when negative_document_count is 0."""
    pos_text = "دکتر علی رضایی ویزیت نمودند."
    doc_pos = ChallengeDocument(
        doc_id="POS_ONLY",
        dataset="test",
        category="pos",
        description="pos",
        text=pos_text,
        gold_spans=(EntitySpan(start=5, end=14, type="PERSON"),),
    )
    pred_pos = [
        Detection(
            type="PERSON",
            start=5,
            end=14,
            value="علی رضایی",
            normalized_value="علی رضایی",
        )
    ]
    det = MockDetector(prediction_map={pos_text: pred_pos})

    metrics = evaluate_detector_on_corpus(det, [doc_pos], "DatasetC_Mock")
    assert metrics.negative_document_count == 0
    assert metrics.negative_documents_with_fp == 0
    assert metrics.negative_document_fp_rate is None

    # Test serialization to dictionary and JSON
    metrics_dict = metrics.to_dict()
    assert metrics_dict["negative_document_count"] == 0
    assert metrics_dict["negative_document_fp_rate"] is None

    serialized_json = json.dumps(metrics_dict)
    assert '"negative_document_fp_rate": null' in serialized_json


def test_offset_integrity_detection_out_of_bounds() -> None:
    """Verify offset bounds violations are recorded as offset_failures."""
    text = "بیمار علی رضایی ویزیت شد."
    doc = ChallengeDocument(
        doc_id="TEST_BOUNDS",
        dataset="test",
        category="test",
        description="test",
        text=text,
        gold_spans=(),
    )

    # Out-of-bounds start/end via FakeDetection
    preds = [
        FakeDetection(
            type="PERSON",
            start=-1,
            end=5,
            value="بیمار",
            normalized_value="بیمار",
        )
    ]
    det = MockDetector(prediction_map={text: preds})

    metrics = evaluate_detector_on_corpus(det, [doc], "OffsetTest")
    assert metrics.offset_failures == 1


def test_mismatched_detection_value_vs_source_slice_is_offset_failure() -> None:
    """Verify original_text[start:end] != Detection.value flags offset failure."""
    text = "بیمار علی رضایی ویزیت شد."
    doc = ChallengeDocument(
        doc_id="TEST_MISMATCH",
        dataset="test",
        category="test",
        description="test",
        text=text,
        gold_spans=(),
    )

    # Offset [6:15] is "علی رضایی", but detection claims "مریم احمدی"
    preds = [
        FakeDetection(
            type="PERSON",
            start=6,
            end=15,
            value="مریم احمدی",
            normalized_value="مریم احمدی",
        )
    ]
    det = MockDetector(prediction_map={text: preds})

    metrics = evaluate_detector_on_corpus(det, [doc], "MismatchTest")
    assert metrics.offset_failures == 1


def test_adapter_exception_recorded_as_type_only_metadata() -> None:
    """Verify backend exceptions are recorded as TYPE only without text leakage."""
    secret_text = " محرمانه شخصی ۱۲۳۴۵ "
    doc = ChallengeDocument(
        doc_id="TEST_ERR",
        dataset="test",
        category="test",
        description="test",
        text=secret_text,
        gold_spans=(),
    )

    det = MockDetector(
        exception_map={secret_text: RuntimeError("Secret payload leaked in exception")}
    )

    metrics = evaluate_detector_on_corpus(det, [doc], "ErrorTest")
    assert metrics.adapter_error_count == 1
    assert "RuntimeError" in metrics.exception_type_counts
    assert metrics.exception_type_counts["RuntimeError"] == 1
    # Check that error text is not in exception_type_counts
    assert "Secret" not in str(metrics.exception_type_counts)
    assert secret_text not in str(metrics.exception_type_counts)


def test_deterministic_comparison_across_runs() -> None:
    """Verify determinism evaluation detects consistent vs non-deterministic outputs."""
    text_b = "آقای علی رضایی"
    text_c = "خانم سارا محمدی"
    doc_b = ChallengeDocument(
        doc_id="B_01",
        dataset="b",
        category="b",
        description="b",
        text=text_b,
        gold_spans=(EntitySpan(start=5, end=14, type="PERSON"),),
    )
    doc_c = ChallengeDocument(
        doc_id="C_01",
        dataset="c",
        category="c",
        description="c",
        text=text_c,
        gold_spans=(EntitySpan(start=5, end=15, type="PERSON"),),
    )

    det_good = MockDetector(
        prediction_map={
            text_b: [
                Detection(
                    type="PERSON",
                    start=5,
                    end=14,
                    value="علی رضایی",
                    normalized_value="علی رضایی",
                )
            ],
            text_c: [
                Detection(
                    type="PERSON",
                    start=5,
                    end=15,
                    value="سارا محمدی",
                    normalized_value="سارا محمدی",
                )
            ],
        }
    )
    res_good = evaluate_determinism(
        det_good, [doc_b], [doc_c], subset_size_per_dataset=1, runs=3
    )
    assert res_good["is_deterministic"] is True

    # Flaky detector
    call_count = 0

    class FlakyDetector:
        def detect(self, original_text: str, normalized_text: str) -> list[Detection]:
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return [
                    Detection(
                        type="PERSON",
                        start=5,
                        end=14,
                        value="علی رضایی",
                        normalized_value="علی رضایی",
                    )
                ]
            return []

    res_flaky = evaluate_determinism(
        FlakyDetector(), [doc_b], [doc_c], subset_size_per_dataset=1, runs=3
    )
    assert res_flaky["is_deterministic"] is False


def test_gate_pass_calculation_when_all_gates_met() -> None:
    """Verify compute_gate_decisions returns overall PASS when all 8 gates pass."""

    def _make_metrics(
        p: float, r: float, f1: float, off: int = 0, err: int = 0
    ) -> DatasetEvaluationMetrics:
        return DatasetEvaluationMetrics(
            dataset_name="dummy",
            document_count=10,
            total_gold=10,
            total_predicted=10,
            true_positives=10,
            false_positives=0,
            false_negatives=0,
            precision=p,
            recall=r,
            f1=f1,
            entity_leakage_rate=0.0,
            negative_document_count=0,
            negative_documents_with_fp=0,
            negative_document_fp_rate=None,
            total_fp_in_negative_docs=0,
            offset_failures=off,
            adapter_error_count=err,
            exception_type_counts={},
            quality_gate_passed=True,
        )

    peyma_b = _make_metrics(1.0, 1.0, 1.0)
    peyma_c = _make_metrics(1.0, 1.0, 1.0)
    onnx_b = _make_metrics(0.85, 0.90, 0.87)
    onnx_c = _make_metrics(0.99, 0.99, 0.99)
    peyma_det = {"is_deterministic": True}
    onnx_det = {"is_deterministic": True}
    peyma_long = {
        "all_passed": True,
        "total_offset_failures": 0,
        "total_adapter_errors": 0,
    }
    onnx_long = {
        "all_passed": True,
        "total_offset_failures": 0,
        "total_adapter_errors": 0,
    }

    gates = compute_gate_decisions(
        peyma_b,
        peyma_c,
        onnx_b,
        onnx_c,
        peyma_det,
        onnx_det,
        peyma_long,
        onnx_long,
    )
    assert gates["overall_decision"] == "PASS"
    rec = generate_recommendation(True, gates)
    assert "remains the validated reference" in rec


def test_gate_fail_on_quality_regression() -> None:
    """Verify compute_gate_decisions returns overall FAIL on quality gate failure."""

    def _make_metrics(passed: bool) -> DatasetEvaluationMetrics:
        return DatasetEvaluationMetrics(
            dataset_name="dummy",
            document_count=10,
            total_gold=10,
            total_predicted=10,
            true_positives=5,
            false_positives=5,
            false_negatives=5,
            precision=0.5,
            recall=0.5,
            f1=0.5,
            entity_leakage_rate=0.5,
            negative_document_count=0,
            negative_documents_with_fp=0,
            negative_document_fp_rate=None,
            total_fp_in_negative_docs=0,
            offset_failures=0,
            adapter_error_count=0,
            exception_type_counts={},
            quality_gate_passed=passed,
        )

    peyma_b = _make_metrics(True)
    peyma_c = _make_metrics(True)
    onnx_b = _make_metrics(False)  # Regression in ONNX B
    onnx_c = _make_metrics(True)
    peyma_det = {"is_deterministic": True}
    onnx_det = {"is_deterministic": True}
    peyma_long = {
        "all_passed": True,
        "total_offset_failures": 0,
        "total_adapter_errors": 0,
    }
    onnx_long = {
        "all_passed": True,
        "total_offset_failures": 0,
        "total_adapter_errors": 0,
    }

    gates = compute_gate_decisions(
        peyma_b,
        peyma_c,
        onnx_b,
        onnx_c,
        peyma_det,
        onnx_det,
        peyma_long,
        onnx_long,
    )
    assert gates["overall_decision"] == "FAIL"
    assert gates["onnx_quality_gate_dataset_b"] is False
    rec = generate_recommendation(False, gates)
    assert "Validation gate FAILED" in rec


def test_gate_fail_on_offset_failure() -> None:
    """Verify compute_gate_decisions returns overall FAIL on any offset failure."""

    def _make_metrics(off: int) -> DatasetEvaluationMetrics:
        return DatasetEvaluationMetrics(
            dataset_name="dummy",
            document_count=10,
            total_gold=10,
            total_predicted=10,
            true_positives=10,
            false_positives=0,
            false_negatives=0,
            precision=1.0,
            recall=1.0,
            f1=1.0,
            entity_leakage_rate=0.0,
            negative_document_count=0,
            negative_documents_with_fp=0,
            negative_document_fp_rate=None,
            total_fp_in_negative_docs=0,
            offset_failures=off,
            adapter_error_count=0,
            exception_type_counts={},
            quality_gate_passed=True,
        )

    peyma_b = _make_metrics(1)  # 1 offset failure
    peyma_c = _make_metrics(0)
    onnx_b = _make_metrics(0)
    onnx_c = _make_metrics(0)
    peyma_det = {"is_deterministic": True}
    onnx_det = {"is_deterministic": True}
    peyma_long = {
        "all_passed": True,
        "total_offset_failures": 0,
        "total_adapter_errors": 0,
    }
    onnx_long = {
        "all_passed": True,
        "total_offset_failures": 0,
        "total_adapter_errors": 0,
    }

    gates = compute_gate_decisions(
        peyma_b,
        peyma_c,
        onnx_b,
        onnx_c,
        peyma_det,
        onnx_det,
        peyma_long,
        onnx_long,
    )
    assert gates["overall_decision"] == "FAIL"
    assert gates["offset_integrity_zero_failures"] is False


def test_gate_fail_on_adapter_error() -> None:
    """Verify compute_gate_decisions returns overall FAIL on any adapter error."""

    def _make_metrics(err: int) -> DatasetEvaluationMetrics:
        return DatasetEvaluationMetrics(
            dataset_name="dummy",
            document_count=10,
            total_gold=10,
            total_predicted=10,
            true_positives=10,
            false_positives=0,
            false_negatives=0,
            precision=1.0,
            recall=1.0,
            f1=1.0,
            entity_leakage_rate=0.0,
            negative_document_count=0,
            negative_documents_with_fp=0,
            negative_document_fp_rate=None,
            total_fp_in_negative_docs=0,
            offset_failures=0,
            adapter_error_count=err,
            exception_type_counts={"RuntimeError": err} if err else {},
            quality_gate_passed=True,
        )

    peyma_b = _make_metrics(0)
    peyma_c = _make_metrics(0)
    onnx_b = _make_metrics(1)  # 1 adapter error
    onnx_c = _make_metrics(0)
    peyma_det = {"is_deterministic": True}
    onnx_det = {"is_deterministic": True}
    peyma_long = {
        "all_passed": True,
        "total_offset_failures": 0,
        "total_adapter_errors": 0,
    }
    onnx_long = {
        "all_passed": True,
        "total_offset_failures": 0,
        "total_adapter_errors": 0,
    }

    gates = compute_gate_decisions(
        peyma_b,
        peyma_c,
        onnx_b,
        onnx_c,
        peyma_det,
        onnx_det,
        peyma_long,
        onnx_long,
    )
    assert gates["overall_decision"] == "FAIL"
    assert gates["runtime_integrity_zero_errors"] is False


def test_gate_fail_on_nondeterminism() -> None:
    """Verify compute_gate_decisions returns overall FAIL if nondeterministic."""

    def _make_metrics() -> DatasetEvaluationMetrics:
        return DatasetEvaluationMetrics(
            dataset_name="dummy",
            document_count=10,
            total_gold=10,
            total_predicted=10,
            true_positives=10,
            false_positives=0,
            false_negatives=0,
            precision=1.0,
            recall=1.0,
            f1=1.0,
            entity_leakage_rate=0.0,
            negative_document_count=0,
            negative_documents_with_fp=0,
            negative_document_fp_rate=None,
            total_fp_in_negative_docs=0,
            offset_failures=0,
            adapter_error_count=0,
            exception_type_counts={},
            quality_gate_passed=True,
        )

    peyma_b = _make_metrics()
    peyma_c = _make_metrics()
    onnx_b = _make_metrics()
    onnx_c = _make_metrics()
    peyma_det = {"is_deterministic": False}  # Nondeterministic
    onnx_det = {"is_deterministic": True}
    peyma_long = {
        "all_passed": True,
        "total_offset_failures": 0,
        "total_adapter_errors": 0,
    }
    onnx_long = {
        "all_passed": True,
        "total_offset_failures": 0,
        "total_adapter_errors": 0,
    }

    gates = compute_gate_decisions(
        peyma_b,
        peyma_c,
        onnx_b,
        onnx_c,
        peyma_det,
        onnx_det,
        peyma_long,
        onnx_long,
    )
    assert gates["overall_decision"] == "FAIL"
    assert gates["determinism_gate_passed"] is False


def test_gate_fail_on_long_document_failure() -> None:
    """Verify compute_gate_decisions returns FAIL if long doc validation fails."""

    def _make_metrics() -> DatasetEvaluationMetrics:
        return DatasetEvaluationMetrics(
            dataset_name="dummy",
            document_count=10,
            total_gold=10,
            total_predicted=10,
            true_positives=10,
            false_positives=0,
            false_negatives=0,
            precision=1.0,
            recall=1.0,
            f1=1.0,
            entity_leakage_rate=0.0,
            negative_document_count=0,
            negative_documents_with_fp=0,
            negative_document_fp_rate=None,
            total_fp_in_negative_docs=0,
            offset_failures=0,
            adapter_error_count=0,
            exception_type_counts={},
            quality_gate_passed=True,
        )

    peyma_b = _make_metrics()
    peyma_c = _make_metrics()
    onnx_b = _make_metrics()
    onnx_c = _make_metrics()
    peyma_det = {"is_deterministic": True}
    onnx_det = {"is_deterministic": True}
    peyma_long = {
        "all_passed": True,
        "total_offset_failures": 0,
        "total_adapter_errors": 0,
    }
    onnx_long = {
        "all_passed": False,
        "total_offset_failures": 0,
        "total_adapter_errors": 1,
    }

    gates = compute_gate_decisions(
        peyma_b,
        peyma_c,
        onnx_b,
        onnx_c,
        peyma_det,
        onnx_det,
        peyma_long,
        onnx_long,
    )
    assert gates["overall_decision"] == "FAIL"
    assert gates["long_document_gate_passed"] is False


def test_instrumentation_restores_original_model_and_session() -> None:
    """Verify track_model_calls restores original forward and run methods."""

    class FakePyTorchModel:
        def forward(self, input_ids: Any, **kwargs: Any) -> str:
            return "original_model_result"

    class FakePyTorchDetector:
        def __init__(self) -> None:
            self._model = FakePyTorchModel()

    py_det = FakePyTorchDetector()
    orig_forward = py_det._model.forward

    with track_model_calls(py_det) as tracker:
        res = py_det._model.forward(input_ids=[[101, 200, 102]])
        assert res == "original_model_result"
        assert tracker.call_count == 1
    assert py_det._model.forward == orig_forward
    assert "forward" not in py_det._model.__dict__

    # Test restoration even on exception
    with pytest.raises(ZeroDivisionError):
        with track_model_calls(py_det):
            _ = 1 / 0
    assert py_det._model.forward == orig_forward
    assert "forward" not in py_det._model.__dict__

    class FakeONNXSession:
        def run(self, output_names: Any, input_feed: dict[str, Any]) -> str:
            return "original_session_result"

    class FakeONNXDetector:
        def __init__(self) -> None:
            self._session = FakeONNXSession()

    onnx_det = FakeONNXDetector()
    orig_run = onnx_det._session.run

    with track_model_calls(onnx_det) as tracker:
        res = onnx_det._session.run(None, {"input_ids": [[101, 102, 103, 104]]})
        assert res == "original_session_result"
        assert tracker.call_count == 1
        assert tracker.input_lengths == [4]

    assert onnx_det._session.run == orig_run
    assert "run" not in onnx_det._session.__dict__

    with pytest.raises(ValueError):
        with track_model_calls(onnx_det):
            raise ValueError("test error")
    assert onnx_det._session.run == orig_run
    assert "run" not in onnx_det._session.__dict__


def test_tokenizer_token_count_distinct_from_whitespace_word_count() -> None:
    """Verify actual tokenizer token count is distinct from whitespace word count."""
    text = "بیمار علی رضایی در بیمارستان امام خمینی بستری شد."
    whitespace_count = len(text.split())

    class DummyTokenizer:
        def __call__(
            self, text_input: str, add_special_tokens: bool = True
        ) -> dict[str, list[int]]:
            # Subwords produce more tokens than whitespace words
            return {"input_ids": [101] + list(range(20)) + [102]}

    class DummyDetector:
        def __init__(self) -> None:
            self._tokenizer = DummyTokenizer()

    det = DummyDetector()
    token_count = get_full_token_count(det, text)
    assert whitespace_count == 9
    assert token_count == 22
    assert token_count != whitespace_count


def test_sliding_window_required_and_inference_call_count_verification() -> None:
    """Verify evaluate_long_documents verifies sliding-window execution rules."""
    text_short = "علی رضایی"
    text_long = "علی رضایی " * 100

    doc_short = ValidationDocument(
        doc_id="VAL_SHORT",
        category="short",
        description="short",
        text=text_short,
        gold_spans=(EntitySpan(start=0, end=9, type="PERSON"),),
        whitespace_word_count=len(text_short.split()),
    )
    doc_long = ValidationDocument(
        doc_id="VAL_LONG",
        category="long",
        description="long",
        text=text_long,
        gold_spans=(EntitySpan(start=0, end=9, type="PERSON"),),
        whitespace_word_count=len(text_long.split()),
    )

    class DummyTokenizer:
        def __call__(
            self, text_input: str, add_special_tokens: bool = True
        ) -> dict[str, list[int]]:
            if len(text_input) < 20:
                return {"input_ids": [101, 1, 2, 102]}  # 4 tokens <= 10
            return {"input_ids": list(range(50))}  # 50 tokens > 10

    # Detector that properly uses sliding window (2 calls for long, 1 for short)
    class ProperSlidingWindowDetector:
        def __init__(self) -> None:
            self._tokenizer = DummyTokenizer()
            self._max_length = 10
            self._session = self

        def run(self, output_names: Any, input_feed: dict[str, Any]) -> Any:
            return []

        def detect(self, original_text: str, normalized_text: str) -> list[Detection]:
            if len(original_text) < 20:
                # Single pass
                self.run(None, {"input_ids": [[101, 1, 2, 102]]})
            else:
                # Multi pass
                self.run(None, {"input_ids": [[101, 1, 2, 3, 4, 5, 6, 7, 8, 102]]})
                self.run(None, {"input_ids": [[101, 9, 10, 11, 12, 102]]})
            return [
                Detection(
                    type="PERSON",
                    start=0,
                    end=9,
                    value="علی رضایی",
                    normalized_value="علی رضایی",
                )
            ]

    res = evaluate_long_documents(ProperSlidingWindowDetector(), [doc_short, doc_long])
    assert res["all_passed"] is True
    assert res["document_details"][0]["requires_sliding_window"] is False
    assert res["document_details"][0]["inference_call_count"] == 1
    assert res["document_details"][1]["requires_sliding_window"] is True
    assert res["document_details"][1]["inference_call_count"] == 2

    # Detector that fails to use sliding window when required
    class BrokenSlidingWindowDetector:
        def __init__(self) -> None:
            self._tokenizer = DummyTokenizer()
            self._max_length = 10
            self._session = self

        def run(self, output_names: Any, input_feed: dict[str, Any]) -> Any:
            return []

        def detect(self, original_text: str, normalized_text: str) -> list[Detection]:
            # Only runs 1 call even for long
            self.run(None, {"input_ids": [[101, 1, 2, 3, 4, 5, 6, 7, 8, 102]]})
            return [
                Detection(
                    type="PERSON",
                    start=0,
                    end=9,
                    value="علی رضایی",
                    normalized_value="علی رضایی",
                )
            ]

    res_broken = evaluate_long_documents(BrokenSlidingWindowDetector(), [doc_long])
    assert res_broken["all_passed"] is False
    assert res_broken["document_details"][0]["passed"] is False


def test_observed_max_model_input_never_exceeds_max_length() -> None:
    """Verify that if model input exceeds configured_max_length, gate fails."""
    text_long = "علی رضایی " * 100
    doc_long = ValidationDocument(
        doc_id="VAL_LONG",
        category="long",
        description="long",
        text=text_long,
        gold_spans=(EntitySpan(start=0, end=9, type="PERSON"),),
        whitespace_word_count=len(text_long.split()),
    )

    class OversizedInputDetector:
        def __init__(self) -> None:
            self._tokenizer = lambda text, add_special_tokens=True: {
                "input_ids": list(range(50))
            }
            self._max_length = 10
            self._session = self

        def run(self, output_names: Any, input_feed: dict[str, Any]) -> Any:
            return []

        def detect(self, original_text: str, normalized_text: str) -> list[Detection]:
            # Feeds 20 tokens which exceeds max_length of 10
            self.run(None, {"input_ids": [list(range(20))]})
            self.run(None, {"input_ids": [list(range(20))]})
            return [
                Detection(
                    type="PERSON",
                    start=0,
                    end=9,
                    value="علی رضایی",
                    normalized_value="علی رضایی",
                )
            ]

    res = evaluate_long_documents(OversizedInputDetector(), [doc_long])
    assert res["all_passed"] is False
    assert res["document_details"][0]["passed"] is False
    assert res["document_details"][0]["max_model_input_tokens"] == 20


def test_long_document_nondeterminism_causes_fail() -> None:
    """Verify long document validation fails if repeated runs are nondeterministic."""
    text_long = "علی رضایی " * 10
    doc_long = ValidationDocument(
        doc_id="VAL_LONG",
        category="long",
        description="long",
        text=text_long,
        gold_spans=(EntitySpan(start=0, end=9, type="PERSON"),),
        whitespace_word_count=len(text_long.split()),
    )

    call_num = 0

    class NonDetLongDetector:
        def __init__(self) -> None:
            self._tokenizer = lambda text, add_special_tokens=True: {
                "input_ids": [101, 1, 102]
            }
            self._max_length = 512
            self._session = self

        def run(self, output_names: Any, input_feed: dict[str, Any]) -> Any:
            return []

        def detect(self, original_text: str, normalized_text: str) -> list[Detection]:
            nonlocal call_num
            call_num += 1
            self.run(None, {"input_ids": [[101, 1, 102]]})
            if call_num == 1:
                return [
                    Detection(
                        type="PERSON",
                        start=0,
                        end=9,
                        value="علی رضایی",
                        normalized_value="علی رضایی",
                    )
                ]
            return []  # Nondeterministic on run 2

    res = evaluate_long_documents(NonDetLongDetector(), [doc_long], repeat_runs=3)
    assert res["all_passed"] is False
    assert res["document_details"][0]["deterministic"] is False
    assert res["document_details"][0]["passed"] is False


def test_locked_baselines_and_thresholds_constants() -> None:
    """Verify locked Phase 29 baselines and quality gate thresholds."""
    assert LOCKED_BASELINES["peyma"]["dataset_b"]["precision"] == 1.0000
    assert LOCKED_BASELINES["peyma"]["dataset_b"]["recall"] == 1.0000
    assert LOCKED_BASELINES["peyma"]["dataset_b"]["f1"] == 1.0000
    assert LOCKED_BASELINES["peyma"]["dataset_c"]["f1"] == 1.0000

    assert LOCKED_BASELINES["tookabert_wrapper"]["dataset_b"]["precision"] == 0.8438
    assert LOCKED_BASELINES["tookabert_wrapper"]["dataset_b"]["recall"] == 0.9000
    assert LOCKED_BASELINES["tookabert_wrapper"]["dataset_b"]["f1"] == 0.8710
    assert LOCKED_BASELINES["tookabert_wrapper"]["dataset_c"]["f1"] == 1.0000

    assert LOCKED_QUALITY_GATES["peyma"]["dataset_b"]["min_precision"] == 0.98
    assert LOCKED_QUALITY_GATES["peyma"]["dataset_b"]["min_recall"] == 0.98
    assert LOCKED_QUALITY_GATES["peyma"]["dataset_b"]["min_f1"] == 0.98
    assert LOCKED_QUALITY_GATES["peyma"]["dataset_c"]["min_precision"] == 0.98

    assert LOCKED_QUALITY_GATES["onnx"]["dataset_b"]["min_precision"] == 0.81
    assert LOCKED_QUALITY_GATES["onnx"]["dataset_b"]["min_recall"] == 0.87
    assert LOCKED_QUALITY_GATES["onnx"]["dataset_b"]["min_f1"] == 0.84
    assert LOCKED_QUALITY_GATES["onnx"]["dataset_c"]["min_precision"] == 0.97

    assert PEYMA_MODEL_ID == "HooshvareLab/bert-fa-base-uncased-ner-peyma"
    assert PEYMA_REVISION == "8b7b63371aa8f1fdad62c0f82d462a22b91b37ab"
    assert PEYMA_LICENSE == "Apache-2.0"
    assert PEYMA_BACKEND_CLASS == "fa_redact.detectors.persian_ner.PersianNERDetector"

    assert TOOKABERT_MODEL_ID == "Reza2kn/openmed-persian-pii-tookabert-large-onnx-int4"
    assert TOOKABERT_REVISION == "27dc2a6eacea263ae325dcb18e6751cfabbbfe74"
    assert TOOKABERT_LICENSE == "CC-BY-4.0"
    assert (
        TOOKABERT_BACKEND_CLASS
        == "fa_redact.detectors.onnx_persian_ner.ONNXPersianNERDetector"
    )


def test_long_documents_and_normalization_cases_structure() -> None:
    """Verify synthetic long documents and targeted normalization structure."""
    long_docs = build_long_documents()
    assert len(long_docs) == 3
    for doc in long_docs:
        assert len(doc.gold_spans) >= 4
        for span in doc.gold_spans:
            assert span.type == "PERSON"
            assert 0 <= span.start < span.end <= len(doc.text)
            assert doc.text[span.start : span.end] != ""

    norm_cases = build_targeted_normalization_cases()
    assert len(norm_cases) == 4
    for doc in norm_cases:
        assert len(doc.gold_spans) >= 1
        for span in doc.gold_spans:
            assert span.type == "PERSON"
            assert 0 <= span.start < span.end <= len(doc.text)


def test_result_json_privacy_and_path_invariants() -> None:
    """Verify result artifact schema and privacy invariants."""
    result_path = Path("research/results/phase32_ner_validation.json")
    if not result_path.exists():
        pytest.skip("Result JSON artifact not yet generated")

    content = result_path.read_text(encoding="utf-8")
    data = json.loads(content)

    # Privacy checks
    assert "benchmark_name" in data
    assert "gate_summary" in data
    assert "results" in data

    forbidden_terms = [
        "Users",
        "AppData",
        "cache",
        "snapshots",
        "علیرضا",
        "سارا محمدی",
        "مریم احمدی",
        "سید‌علی",
    ]
    for term in forbidden_terms:
        assert term not in content, f"Forbidden term {term!r} found in result JSON"
