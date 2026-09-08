"""Independent Persian NER Backend Validation & Readiness Gate (Phase 32).

===============================================================================
DISCLAIMER & PRIVACY NOTICE:
THIS MODULE EVALUATES PRODUCTION NER BACKENDS AGAINST SYNTHETIC CHALLENGE
DATASETS. ALL BENCHMARK OUTPUTS AND COMMITTED RESULTS CONTAIN ONLY AGGREGATE
METADATA AND METRICS. ZERO RAW PII, SOURCE TEXT SNIPPETS, OR ABSOLUTE LOCAL
WORKSTATION PATHS ARE STORED IN ARTIFACTS.
===============================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fa_redact.normalization import normalize_text
from research.evaluation import calculate_metrics
from research.phase29_challenge_set import (
    ChallengeDocument,
    build_dataset_b,
    build_dataset_c,
)
from research.phase32_ner_validation_cases import (
    ValidationDocument,
    build_long_documents,
    build_targeted_normalization_cases,
)

# Pinned Model Constants
PEYMA_MODEL_ID = "HooshvareLab/bert-fa-base-uncased-ner-peyma"
PEYMA_REVISION = "8b7b63371aa8f1fdad62c0f82d462a22b91b37ab"
PEYMA_LICENSE = "Apache-2.0"
PEYMA_BACKEND_CLASS = "fa_redact.detectors.persian_ner.PersianNERDetector"

TOOKABERT_MODEL_ID = "Reza2kn/openmed-persian-pii-tookabert-large-onnx-int4"
TOOKABERT_REVISION = "27dc2a6eacea263ae325dcb18e6751cfabbbfe74"
TOOKABERT_LICENSE = "CC-BY-4.0"
TOOKABERT_BACKEND_CLASS = "fa_redact.detectors.onnx_persian_ner.ONNXPersianNERDetector"

# Locked Phase 29 Reference Baselines
LOCKED_BASELINES = {
    "peyma": {
        "dataset_b": {"precision": 1.0000, "recall": 1.0000, "f1": 1.0000},
        "dataset_c": {"precision": 1.0000, "recall": 1.0000, "f1": 1.0000},
    },
    "tookabert_wrapper": {
        "dataset_b": {"precision": 0.8438, "recall": 0.9000, "f1": 0.8710},
        "dataset_c": {"precision": 1.0000, "recall": 1.0000, "f1": 1.0000},
    },
}

# Locked Quality Gate Thresholds
LOCKED_QUALITY_GATES = {
    "peyma": {
        "dataset_b": {
            "min_precision": 0.98,
            "min_recall": 0.98,
            "min_f1": 0.98,
        },
        "dataset_c": {
            "min_precision": 0.98,
            "min_recall": 0.98,
            "min_f1": 0.98,
        },
    },
    "onnx": {
        "dataset_b": {
            "min_precision": 0.81,
            "min_recall": 0.87,
            "min_f1": 0.84,
        },
        "dataset_c": {
            "min_precision": 0.97,
            "min_recall": 0.97,
            "min_f1": 0.97,
        },
    },
}


def resolve_local_model_dir(
    model_id: str,
    revision: str,
    cli_dir: str | None = None,
) -> Path | None:
    """Resolve local model directory from CLI path or Hugging Face cache."""
    if cli_dir:
        p = Path(cli_dir).expanduser().resolve()
        if p.exists() and p.is_dir():
            return p

    hf_home_env = os.environ.get("HF_HOME")
    if hf_home_env:
        hub_root = Path(hf_home_env).expanduser().resolve()
        model_dir_name = f"models--{model_id.replace('/', '--')}"
        if not (hub_root / "hub").exists() and (hub_root / model_dir_name).exists():
            cache_root = hub_root
        else:
            cache_root = hub_root / "hub"
    else:
        cache_root = Path.home() / ".cache" / "huggingface" / "hub"

    model_dir_name = f"models--{model_id.replace('/', '--')}"
    snapshot_dir = cache_root / model_dir_name / "snapshots" / revision
    if snapshot_dir.exists() and snapshot_dir.is_dir():
        return snapshot_dir

    return None


@dataclass
class ModelCallInfo:
    """Record of model/session execution calls and input sequence lengths."""

    call_count: int = 0
    input_lengths: list[int] = field(default_factory=list)


@contextmanager
def track_model_calls(detector: Any) -> Generator[ModelCallInfo, None, None]:
    """Safely instrument model/session calls to record sequence lengths.

    Restores original model or session state unconditionally in a finally block.
    Does NOT modify or persist model input contents, token IDs, or tensors.
    """
    info = ModelCallInfo()

    # Case 1: PEYMA / PyTorch model (PersianNERDetector)
    if hasattr(detector, "_model") and detector._model is not None:
        model = detector._model
        had_instance_attr = "forward" in getattr(model, "__dict__", {})
        original_forward = model.forward

        def instrumented_forward(*args: Any, **kwargs: Any) -> Any:
            info.call_count += 1
            seq_len: int | None = None
            if "input_ids" in kwargs:
                input_ids = kwargs["input_ids"]
                if hasattr(input_ids, "shape") and len(input_ids.shape) >= 2:
                    seq_len = int(input_ids.shape[-1])
                elif isinstance(input_ids, (list, tuple)) and input_ids:
                    first = input_ids[0]
                    seq_len = (
                        len(first)
                        if isinstance(first, (list, tuple))
                        else len(input_ids)
                    )
            elif args:
                first_arg = args[0]
                if hasattr(first_arg, "shape") and len(first_arg.shape) >= 2:
                    seq_len = int(first_arg.shape[-1])
            if seq_len is not None:
                info.input_lengths.append(seq_len)
            return original_forward(*args, **kwargs)

        model.forward = instrumented_forward
        try:
            yield info
        finally:
            if had_instance_attr:
                model.forward = original_forward
            elif hasattr(model, "__dict__"):
                model.__dict__.pop("forward", None)
            else:
                model.forward = original_forward

    # Case 2: ONNX Runtime InferenceSession (ONNXPersianNERDetector)
    elif hasattr(detector, "_session") and detector._session is not None:
        session = detector._session
        had_instance_attr = "run" in getattr(session, "__dict__", {})
        original_run = session.run

        def instrumented_run(
            output_names: Any,
            input_feed: dict[str, Any],
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            info.call_count += 1
            if isinstance(input_feed, dict) and "input_ids" in input_feed:
                input_ids = input_feed["input_ids"]
                if hasattr(input_ids, "shape") and len(input_ids.shape) >= 2:
                    info.input_lengths.append(int(input_ids.shape[-1]))
                elif isinstance(input_ids, (list, tuple)) and input_ids:
                    first = input_ids[0]
                    seq_len = (
                        len(first)
                        if isinstance(first, (list, tuple))
                        else len(input_ids)
                    )
                    info.input_lengths.append(seq_len)
            return original_run(output_names, input_feed, *args, **kwargs)

        session.run = instrumented_run
        try:
            yield info
        finally:
            if had_instance_attr:
                session.run = original_run
            elif hasattr(session, "__dict__"):
                session.__dict__.pop("run", None)
            else:
                session.run = original_run

    else:
        # Fallback / mock detector without _model or _session
        yield info


def get_full_token_count(detector: Any, text: str) -> int:
    """Compute the actual full-sequence token count from the detector's tokenizer."""
    if hasattr(detector, "_tokenizer") and detector._tokenizer is not None:
        norm = normalize_text(text)
        encoding = detector._tokenizer(norm, add_special_tokens=True)
        if isinstance(encoding, dict) and "input_ids" in encoding:
            return len(encoding["input_ids"])
        if hasattr(encoding, "input_ids"):
            return len(encoding.input_ids)
    return len(text.split()) + 2


@dataclass(frozen=True, slots=True)
class DatasetEvaluationMetrics:
    """Evaluation metrics for a single dataset run."""

    dataset_name: str
    document_count: int
    total_gold: int
    total_predicted: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    entity_leakage_rate: float
    negative_document_count: int
    negative_documents_with_fp: int
    negative_document_fp_rate: float | None
    total_fp_in_negative_docs: int
    offset_failures: int
    adapter_error_count: int
    exception_type_counts: dict[str, int]
    quality_gate_passed: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to aggregate JSON-safe dict."""
        return {
            "dataset_name": self.dataset_name,
            "document_count": self.document_count,
            "total_gold": self.total_gold,
            "total_predicted": self.total_predicted,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "entity_leakage_rate": round(self.entity_leakage_rate, 4),
            "negative_document_count": self.negative_document_count,
            "negative_documents_with_fp": self.negative_documents_with_fp,
            "negative_document_fp_rate": (
                round(self.negative_document_fp_rate, 4)
                if self.negative_document_fp_rate is not None
                else None
            ),
            "total_fp_in_negative_docs": self.total_fp_in_negative_docs,
            "offset_failures": self.offset_failures,
            "adapter_error_count": self.adapter_error_count,
            "exception_type_counts": self.exception_type_counts,
            "quality_gate_passed": self.quality_gate_passed,
        }


def evaluate_detector_on_corpus(
    detector: Any,
    dataset: Sequence[ChallengeDocument | ValidationDocument],
    dataset_name: str,
    quality_thresholds: dict[str, float] | None = None,
) -> DatasetEvaluationMetrics:
    """Evaluate detector on a dataset using exact PERSON span matching."""
    tp = 0
    fp = 0
    fn = 0
    total_gold = 0
    total_pred = 0

    offset_failures = 0
    adapter_error_count = 0
    exception_type_counts: dict[str, int] = {}

    negative_doc_count = 0
    negative_docs_with_fp = 0
    total_fp_in_neg_docs = 0

    for doc in dataset:
        original_text = doc.text
        text_len = len(original_text)
        gold_spans = {
            (s.start, s.end, s.type) for s in doc.gold_spans if s.type == "PERSON"
        }
        total_gold += len(gold_spans)
        is_negative = len(gold_spans) == 0
        if is_negative:
            negative_doc_count += 1

        doc_pred_spans: set[tuple[int, int, str]] = set()
        try:
            norm_text = normalize_text(original_text)
            detections = detector.detect(original_text, norm_text)
            for d in detections:
                if d.type == "PERSON":
                    if not (0 <= d.start < d.end <= text_len):
                        offset_failures += 1
                    elif original_text[d.start : d.end] != d.value:
                        offset_failures += 1

                    doc_pred_spans.add((d.start, d.end, d.type))
        except Exception as e:
            adapter_error_count += 1
            exc_name = type(e).__name__
            exception_type_counts[exc_name] = exception_type_counts.get(exc_name, 0) + 1

        total_pred += len(doc_pred_spans)

        doc_tp = len(gold_spans & doc_pred_spans)
        doc_fp = len(doc_pred_spans - gold_spans)
        doc_fn = len(gold_spans - doc_pred_spans)

        tp += doc_tp
        fp += doc_fp
        fn += doc_fn

        if is_negative and doc_fp > 0:
            negative_docs_with_fp += 1
            total_fp_in_neg_docs += doc_fp

    precision, recall, f1 = calculate_metrics(tp, fp, fn)
    leakage = (fn / total_gold) if total_gold > 0 else 0.0
    neg_doc_fp_rate: float | None = (
        (negative_docs_with_fp / negative_doc_count) if negative_doc_count > 0 else None
    )

    gate_passed = True
    if quality_thresholds is not None:
        min_p = quality_thresholds.get("min_precision", 0.0)
        min_r = quality_thresholds.get("min_recall", 0.0)
        min_f1 = quality_thresholds.get("min_f1", 0.0)
        if precision < min_p or recall < min_r or f1 < min_f1:
            gate_passed = False

    return DatasetEvaluationMetrics(
        dataset_name=dataset_name,
        document_count=len(dataset),
        total_gold=total_gold,
        total_predicted=total_pred,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        entity_leakage_rate=leakage,
        negative_document_count=negative_doc_count,
        negative_documents_with_fp=negative_docs_with_fp,
        negative_document_fp_rate=neg_doc_fp_rate,
        total_fp_in_negative_docs=total_fp_in_neg_docs,
        offset_failures=offset_failures,
        adapter_error_count=adapter_error_count,
        exception_type_counts=exception_type_counts,
        quality_gate_passed=gate_passed,
    )


def evaluate_determinism(
    detector: Any,
    dataset_b: Sequence[ChallengeDocument],
    dataset_c: Sequence[ChallengeDocument],
    subset_size_per_dataset: int = 12,
    runs: int = 3,
) -> dict[str, Any]:
    """Evaluate detector determinism on a fixed subset of documents."""
    subset_b = [d for d in dataset_b if any(s.type == "PERSON" for s in d.gold_spans)][
        :subset_size_per_dataset
    ]
    subset_c = [d for d in dataset_c if any(s.type == "PERSON" for s in d.gold_spans)][
        :subset_size_per_dataset
    ]
    eval_docs = subset_b + subset_c

    is_deterministic = True
    for doc in eval_docs:
        run_results: list[tuple[tuple[int, int, str], ...]] = []
        for _ in range(runs):
            norm = normalize_text(doc.text)
            detections = detector.detect(doc.text, norm)
            preds = tuple(
                sorted(
                    (d.start, d.end, d.type) for d in detections if d.type == "PERSON"
                )
            )
            run_results.append(preds)

        for r_idx in range(1, len(run_results)):
            if run_results[r_idx] != run_results[0]:
                is_deterministic = False
                break
        if not is_deterministic:
            break

    return {
        "sample_document_count": len(eval_docs),
        "subset_b_count": len(subset_b),
        "subset_c_count": len(subset_c),
        "runs_per_document": runs,
        "is_deterministic": is_deterministic,
    }


def evaluate_long_documents(
    detector: Any,
    long_docs: Sequence[ValidationDocument],
    repeat_runs: int = 3,
) -> dict[str, Any]:
    """Evaluate sliding-window behavior, offsets, and recall on long docs."""
    results: list[dict[str, Any]] = []
    all_passed = True
    total_offset_failures = 0
    total_adapter_errors = 0

    configured_max_length = int(getattr(detector, "_max_length", 512))

    for doc in long_docs:
        planted_gold = {
            (s.start, s.end, s.type) for s in doc.gold_spans if s.type == "PERSON"
        }
        full_token_count = get_full_token_count(detector, doc.text)
        requires_sliding_window = full_token_count > configured_max_length

        offset_failures = 0
        error_type: str | None = None
        preds: set[tuple[int, int, str]] = set()
        inference_call_count = 0
        max_model_input_tokens = 0

        # Primary instrumented run
        try:
            with track_model_calls(detector) as tracker:
                norm = normalize_text(doc.text)
                detections = detector.detect(doc.text, norm)
                inference_call_count = tracker.call_count
                if tracker.input_lengths:
                    max_model_input_tokens = max(tracker.input_lengths)

            for d in detections:
                if d.type == "PERSON":
                    if not (0 <= d.start < d.end <= len(doc.text)):
                        offset_failures += 1
                    elif doc.text[d.start : d.end] != d.value:
                        offset_failures += 1
                    preds.add((d.start, d.end, d.type))
        except Exception as e:
            error_type = type(e).__name__
            total_adapter_errors += 1

        total_offset_failures += offset_failures
        planted_detected = len(planted_gold & preds)
        all_planted_detected = (
            planted_detected == len(planted_gold) and error_type is None
        )

        # Determinism check across repeated runs
        is_deterministic = True
        if error_type is None:
            first_run_sorted = sorted(preds)
            for _ in range(repeat_runs - 1):
                try:
                    norm = normalize_text(doc.text)
                    rep_detections = detector.detect(doc.text, norm)
                    rep_preds = sorted(
                        (d.start, d.end, d.type)
                        for d in rep_detections
                        if d.type == "PERSON"
                    )
                    if rep_preds != first_run_sorted:
                        is_deterministic = False
                        break
                except Exception:
                    is_deterministic = False
                    break

        # Verification of windowing execution:
        # 1. If requires_sliding_window is True, inference_call_count must be > 1
        # 2. If requires_sliding_window is False, inference_call_count must be == 1
        # 3. Every observed model input length must be <= configured_max_length
        windowing_verified = True
        if requires_sliding_window and inference_call_count <= 1:
            windowing_verified = False
        if not requires_sliding_window and inference_call_count > 1:
            windowing_verified = False
        if max_model_input_tokens > configured_max_length:
            windowing_verified = False

        doc_passed = bool(
            error_type is None
            and offset_failures == 0
            and all_planted_detected
            and is_deterministic
            and windowing_verified
        )
        if not doc_passed:
            all_passed = False

        results.append(
            {
                "doc_id": doc.doc_id,
                "whitespace_word_count": doc.whitespace_word_count,
                "full_token_count": full_token_count,
                "configured_max_length": configured_max_length,
                "requires_sliding_window": requires_sliding_window,
                "inference_call_count": inference_call_count,
                "max_model_input_tokens": max_model_input_tokens,
                "deterministic": is_deterministic,
                "planted_gold_count": len(planted_gold),
                "planted_detected_count": planted_detected,
                "total_predicted_person": len(preds),
                "offset_failures": offset_failures,
                "error_type": error_type,
                "passed": doc_passed,
            }
        )

    return {
        "document_count": len(long_docs),
        "all_passed": all_passed,
        "total_offset_failures": total_offset_failures,
        "total_adapter_errors": total_adapter_errors,
        "document_details": results,
    }


def evaluate_targeted_normalization(
    detector: Any,
    norm_cases: Sequence[ValidationDocument],
) -> dict[str, Any]:
    """Evaluate targeted normalization cases for exact offset preservation."""
    cases_evaluated = len(norm_cases)
    cases_passed = 0
    total_offset_failures = 0

    for doc in norm_cases:
        gold = {(s.start, s.end, s.type) for s in doc.gold_spans if s.type == "PERSON"}
        offset_failures = 0
        preds: set[tuple[int, int, str]] = set()

        try:
            norm = normalize_text(doc.text)
            detections = detector.detect(doc.text, norm)
            for d in detections:
                if d.type == "PERSON":
                    if not (0 <= d.start < d.end <= len(doc.text)):
                        offset_failures += 1
                    elif doc.text[d.start : d.end] != d.value:
                        offset_failures += 1
                    preds.add((d.start, d.end, d.type))
        except Exception:
            offset_failures += 1

        total_offset_failures += offset_failures
        if offset_failures == 0 and (gold <= preds):
            cases_passed += 1

    return {
        "cases_count": cases_evaluated,
        "cases_passed": cases_passed,
        "all_passed": (cases_passed == cases_evaluated and total_offset_failures == 0),
        "total_offset_failures": total_offset_failures,
    }


def compute_gate_decisions(
    peyma_b: DatasetEvaluationMetrics,
    peyma_c: DatasetEvaluationMetrics,
    onnx_b: DatasetEvaluationMetrics,
    onnx_c: DatasetEvaluationMetrics,
    peyma_det: dict[str, Any],
    onnx_det: dict[str, Any],
    peyma_long: dict[str, Any],
    onnx_long: dict[str, Any],
) -> dict[str, Any]:
    """Compute individual gate pass/fail decisions and the overall verdict."""
    peyma_b_pass = bool(peyma_b.quality_gate_passed)
    peyma_c_pass = bool(peyma_c.quality_gate_passed)
    onnx_b_pass = bool(onnx_b.quality_gate_passed)
    onnx_c_pass = bool(onnx_c.quality_gate_passed)

    total_offset_failures = (
        peyma_b.offset_failures
        + peyma_c.offset_failures
        + onnx_b.offset_failures
        + onnx_c.offset_failures
        + peyma_long["total_offset_failures"]
        + onnx_long["total_offset_failures"]
    )
    offset_gate_pass = total_offset_failures == 0

    total_adapter_errors = (
        peyma_b.adapter_error_count
        + peyma_c.adapter_error_count
        + onnx_b.adapter_error_count
        + onnx_c.adapter_error_count
        + peyma_long["total_adapter_errors"]
        + onnx_long["total_adapter_errors"]
    )
    runtime_gate_pass = total_adapter_errors == 0

    determinism_gate_pass = bool(
        peyma_det["is_deterministic"] and onnx_det["is_deterministic"]
    )
    long_doc_gate_pass = bool(peyma_long["all_passed"] and onnx_long["all_passed"])

    all_gates_pass = (
        peyma_b_pass
        and peyma_c_pass
        and onnx_b_pass
        and onnx_c_pass
        and offset_gate_pass
        and runtime_gate_pass
        and determinism_gate_pass
        and long_doc_gate_pass
    )

    return {
        "peyma_quality_gate_dataset_b": peyma_b_pass,
        "peyma_quality_gate_dataset_c": peyma_c_pass,
        "onnx_quality_gate_dataset_b": onnx_b_pass,
        "onnx_quality_gate_dataset_c": onnx_c_pass,
        "offset_integrity_zero_failures": offset_gate_pass,
        "runtime_integrity_zero_errors": runtime_gate_pass,
        "determinism_gate_passed": determinism_gate_pass,
        "long_document_gate_passed": long_doc_gate_pass,
        "total_offset_failures": total_offset_failures,
        "total_adapter_errors": total_adapter_errors,
        "overall_decision": "PASS" if all_gates_pass else "FAIL",
    }


def generate_recommendation(overall_passed: bool, gate_summary: dict[str, Any]) -> str:
    """Generate recommendation string adhering strictly to Phase 32 rules."""
    if overall_passed:
        return (
            "Both production backends meet all locked quality and "
            "integrity gates. PersianNERDetector (PEYMA) remains the "
            "validated reference PERSON backend. ONNXPersianNERDetector "
            "(TookaBERT ONNX candidate) is a validated optional alternative. "
            "Final runtime and performance recommendations are deferred to "
            "Phase 33 performance profiling."
        )
    failed_reasons: list[str] = []
    ignored = {
        "total_offset_failures",
        "total_adapter_errors",
        "overall_decision",
    }
    for k, v in gate_summary.items():
        if k not in ignored and not v:
            failed_reasons.append(k)
    return (
        f"Validation gate FAILED on criteria: {', '.join(failed_reasons)}. "
        "Production readiness for v0.4.0 is blocked pending review."
    )


def run_phase32_validation(
    peyma_model_dir: str | Path | None = None,
    onnx_model_dir: str | Path | None = None,
    output_json_path: str | Path = ("research/results/phase32_ner_validation.json"),
) -> dict[str, Any]:
    """Execute complete Phase 32 Persian NER Validation Suite."""
    print("=" * 70)
    print("Phase 32 — Persian NER Backend Validation & Production Readiness Gate")
    print("=" * 70)

    # 1. Resolve model directories
    peyma_path = resolve_local_model_dir(
        PEYMA_MODEL_ID,
        PEYMA_REVISION,
        str(peyma_model_dir) if peyma_model_dir else None,
    )
    onnx_path = resolve_local_model_dir(
        TOOKABERT_MODEL_ID,
        TOOKABERT_REVISION,
        str(onnx_model_dir) if onnx_model_dir else None,
    )

    if peyma_path is None or not peyma_path.exists():
        raise FileNotFoundError(
            f"PEYMA model directory not found locally for {PEYMA_MODEL_ID}."
        )
    if onnx_path is None or not onnx_path.exists():
        raise FileNotFoundError(
            f"ONNX model directory not found locally for {TOOKABERT_MODEL_ID}."
        )

    print(f"PEYMA model available: {PEYMA_MODEL_ID} ({PEYMA_REVISION[:7]})")
    print(f"ONNX model available: {TOOKABERT_MODEL_ID} ({TOOKABERT_REVISION[:7]})")

    # 2. Instantiate actual production classes
    from fa_redact.detectors import ONNXPersianNERDetector, PersianNERDetector

    print("\nInitializing production detectors...")
    peyma_detector = PersianNERDetector(peyma_path)
    onnx_detector = ONNXPersianNERDetector(onnx_path)
    print("Detectors successfully initialized.")

    # 3. Load datasets
    print("\nLoading Challenge Sets...")
    dataset_b = build_dataset_b()
    dataset_c = build_dataset_c()
    long_docs = build_long_documents()
    norm_cases = build_targeted_normalization_cases()

    n_gold_b = sum(1 for d in dataset_b for s in d.gold_spans if s.type == "PERSON")
    n_gold_c = sum(1 for d in dataset_c for s in d.gold_spans if s.type == "PERSON")
    print(f"Dataset B: {len(dataset_b)} docs, {n_gold_b} gold PERSON entities")
    print(f"Dataset C: {len(dataset_c)} docs, {n_gold_c} gold PERSON entities")
    print(f"Long Docs: {len(long_docs)} docs")
    print(f"Targeted Cases: {len(norm_cases)} cases")

    # 4. Evaluate PEYMA Detector
    print("\nEvaluating Backend A: PersianNERDetector (PEYMA)...")
    peyma_b = evaluate_detector_on_corpus(
        peyma_detector,
        dataset_b,
        "Dataset B (Independent)",
        LOCKED_QUALITY_GATES["peyma"]["dataset_b"],
    )
    peyma_c = evaluate_detector_on_corpus(
        peyma_detector,
        dataset_c,
        "Dataset C (Clinical)",
        LOCKED_QUALITY_GATES["peyma"]["dataset_c"],
    )
    peyma_det = evaluate_determinism(peyma_detector, dataset_b, dataset_c)
    peyma_long = evaluate_long_documents(peyma_detector, long_docs)
    peyma_norm = evaluate_targeted_normalization(peyma_detector, norm_cases)

    print(
        f"  Dataset B -> P: {peyma_b.precision:.4f}, R: {peyma_b.recall:.4f}, "
        f"F1: {peyma_b.f1:.4f} "
        f"[Gate: {'PASS' if peyma_b.quality_gate_passed else 'FAIL'}]"
    )
    print(
        f"  Dataset C -> P: {peyma_c.precision:.4f}, R: {peyma_c.recall:.4f}, "
        f"F1: {peyma_c.f1:.4f} "
        f"[Gate: {'PASS' if peyma_c.quality_gate_passed else 'FAIL'}]"
    )
    print(f"  Determinism -> {'YES' if peyma_det['is_deterministic'] else 'NO'}")
    print(f"  Long Docs -> {'PASS' if peyma_long['all_passed'] else 'FAIL'}")

    # 5. Evaluate ONNX Detector
    print("\nEvaluating Backend B: ONNXPersianNERDetector (TookaBERT ONNX)...")
    onnx_b = evaluate_detector_on_corpus(
        onnx_detector,
        dataset_b,
        "Dataset B (Independent)",
        LOCKED_QUALITY_GATES["onnx"]["dataset_b"],
    )
    onnx_c = evaluate_detector_on_corpus(
        onnx_detector,
        dataset_c,
        "Dataset C (Clinical)",
        LOCKED_QUALITY_GATES["onnx"]["dataset_c"],
    )
    onnx_det = evaluate_determinism(onnx_detector, dataset_b, dataset_c)
    onnx_long = evaluate_long_documents(onnx_detector, long_docs)
    onnx_norm = evaluate_targeted_normalization(onnx_detector, norm_cases)

    print(
        f"  Dataset B -> P: {onnx_b.precision:.4f}, R: {onnx_b.recall:.4f}, "
        f"F1: {onnx_b.f1:.4f} "
        f"[Gate: {'PASS' if onnx_b.quality_gate_passed else 'FAIL'}]"
    )
    print(
        f"  Dataset C -> P: {onnx_c.precision:.4f}, R: {onnx_c.recall:.4f}, "
        f"F1: {onnx_c.f1:.4f} "
        f"[Gate: {'PASS' if onnx_c.quality_gate_passed else 'FAIL'}]"
    )
    print(f"  Determinism -> {'YES' if onnx_det['is_deterministic'] else 'NO'}")
    print(f"  Long Docs -> {'PASS' if onnx_long['all_passed'] else 'FAIL'}")

    # 6. Compute Gate Decisions
    gate_summary = compute_gate_decisions(
        peyma_b=peyma_b,
        peyma_c=peyma_c,
        onnx_b=onnx_b,
        onnx_c=onnx_c,
        peyma_det=peyma_det,
        onnx_det=onnx_det,
        peyma_long=peyma_long,
        onnx_long=onnx_long,
    )
    overall_decision = gate_summary["overall_decision"]
    recommendation = generate_recommendation(overall_decision == "PASS", gate_summary)

    print("\n" + "=" * 70)
    print(f"OVERALL VALIDATION GATE DECISION: {overall_decision}")
    print("=" * 70)
    print(f"Recommendation: {recommendation}\n")

    # 7. Construct privacy-guaranteed result artifact
    result_dict: dict[str, Any] = {
        "benchmark_name": (
            "Phase 32 Persian NER Backend Validation & Production Readiness Gate"
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python_version": platform.python_version(),
            "platform_family": platform.system(),
            "platform_release": platform.release(),
        },
        "models": {
            "peyma": {
                "model_id": PEYMA_MODEL_ID,
                "revision": PEYMA_REVISION,
                "license": PEYMA_LICENSE,
                "backend_class": PEYMA_BACKEND_CLASS,
            },
            "onnx_tookabert": {
                "model_id": TOOKABERT_MODEL_ID,
                "revision": TOOKABERT_REVISION,
                "license": TOOKABERT_LICENSE,
                "backend_class": TOOKABERT_BACKEND_CLASS,
            },
        },
        "locked_phase29_baselines": LOCKED_BASELINES,
        "locked_quality_gate_thresholds": LOCKED_QUALITY_GATES,
        "results": {
            "peyma": {
                "dataset_b": peyma_b.to_dict(),
                "dataset_c": peyma_c.to_dict(),
                "determinism": peyma_det,
                "long_document_validation": peyma_long,
                "targeted_normalization": peyma_norm,
                "total_offset_failures": (
                    peyma_b.offset_failures
                    + peyma_c.offset_failures
                    + peyma_long["total_offset_failures"]
                ),
                "total_adapter_errors": (
                    peyma_b.adapter_error_count
                    + peyma_c.adapter_error_count
                    + peyma_long["total_adapter_errors"]
                ),
            },
            "onnx_tookabert": {
                "dataset_b": onnx_b.to_dict(),
                "dataset_c": onnx_c.to_dict(),
                "determinism": onnx_det,
                "long_document_validation": onnx_long,
                "targeted_normalization": onnx_norm,
                "total_offset_failures": (
                    onnx_b.offset_failures
                    + onnx_c.offset_failures
                    + onnx_long["total_offset_failures"]
                ),
                "total_adapter_errors": (
                    onnx_b.adapter_error_count
                    + onnx_c.adapter_error_count
                    + onnx_long["total_adapter_errors"]
                ),
            },
        },
        "gate_summary": gate_summary,
        "recommendation": recommendation,
    }

    out_path = Path(output_json_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result_dict, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved aggregate validation results to {out_path}")

    return result_dict


def main() -> None:
    """CLI runner for Phase 32 validation."""
    parser = argparse.ArgumentParser(description="Phase 32 Persian NER Validation Gate")
    parser.add_argument(
        "--peyma-model-dir",
        type=str,
        default=None,
        help="Local directory for PEYMA model",
    )
    parser.add_argument(
        "--onnx-model-dir",
        type=str,
        default=None,
        help="Local directory for TookaBERT ONNX model",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="research/results/phase32_ner_validation.json",
        help="Path for aggregate output JSON artifact",
    )
    args = parser.parse_args()

    try:
        run_phase32_validation(
            peyma_model_dir=args.peyma_model_dir,
            onnx_model_dir=args.onnx_model_dir,
            output_json_path=args.output_json,
        )
    except Exception as e:
        print(
            f"Validation failed with exception: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
