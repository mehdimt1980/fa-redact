"""Tests for Phase 33 Performance Profiling & Optimization logic.

All tests in this module execute 100% offline with zero ML model loading,
using lightweight mocks and standard library testing fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from research.phase33_performance import (
    BatchOverheadResult,
    DeterministicTierResult,
    LongDocumentScalingResult,
    NERCorpusPerformanceResult,
    ProcessMemoryInfo,
    benchmark_batch_overhead,
    compute_mean,
    compute_median,
    compute_percentile,
    compute_throughput,
    evaluate_onnx_cpu_recommendation,
    evaluate_optimization_decision,
    get_process_memory_mib,
    validate_privacy_and_security,
)

from fa_redact.clinical import (
    ClinicalRedactionProfile,
    clinical_profile,
)
from fa_redact.detectors import (
    IranianIBANDetector,
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
)
from fa_redact.models import Detection


class FakeMockDetector:
    """Mock detector for testing performance harness without model weights."""

    def __init__(self, detections: list[Detection] | None = None) -> None:
        self.detections = detections or []
        self._tokenizer = None

    def detect(
        self, original_text: str, normalized_text: str | None = None
    ) -> list[Detection]:
        return list(self.detections)


# -----------------------------------------------------------------------------
# 1. Statistical Calculations
# -----------------------------------------------------------------------------


def test_percentile_and_median_calculation() -> None:
    """Test median and percentile calculations on odd, even, and edge collections."""
    assert compute_median([]) == 0.0
    assert compute_percentile([], 50.0) == 0.0
    assert compute_mean([]) == 0.0

    # Single item
    assert compute_median([10.0]) == 10.0
    assert compute_percentile([10.0], 95.0) == 10.0
    assert compute_mean([10.0]) == 10.0

    # Odd length: [1, 2, 3, 4, 5] -> median = 3.0
    values_odd = [5.0, 1.0, 3.0, 2.0, 4.0]
    assert compute_median(values_odd) == 3.0
    assert compute_mean(values_odd) == 3.0

    # Even length: [1, 2, 3, 4] -> median = 2.5
    values_even = [4.0, 1.0, 3.0, 2.0]
    assert compute_median(values_even) == 2.5

    # Percentiles: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    seq = [float(x) for x in range(10, 110, 10)]
    assert compute_percentile(seq, 0.0) == 10.0
    assert compute_percentile(seq, 100.0) == 100.0
    assert compute_percentile(seq, 50.0) == 55.0
    assert compute_percentile(seq, 95.0) == 95.5


def test_throughput_calculation() -> None:
    """Test throughput calculations with normal and fractional durations."""
    assert compute_throughput(100, 2.0) == 50.0
    assert compute_throughput(150, 0.5) == 300.0
    assert compute_throughput(0, 10.0) == 0.0


def test_zero_or_invalid_duration_handling() -> None:
    """Test zero or negative durations safely return 0.0 without ZeroDivisionError."""
    assert compute_throughput(100, 0.0) == 0.0
    assert compute_throughput(100, -1.5) == 0.0


# -----------------------------------------------------------------------------
# 2. Timing and Performance Serialization
# -----------------------------------------------------------------------------


def test_timing_result_serialization() -> None:
    """Test JSON-safe serialization of performance result dataclasses."""
    tier_res = DeterministicTierResult(
        tier="short",
        doc_count=10,
        total_chars=1000,
        median_latency_ms=0.123456,
        p95_latency_ms=0.234567,
        mean_latency_ms=0.150000,
        docs_per_sec=8102.345,
        chars_per_sec=810234.56,
    )
    d = tier_res.to_dict()
    assert d["tier"] == "short"
    assert d["median_latency_ms"] == 0.1235
    assert d["p95_latency_ms"] == 0.2346
    assert d["docs_per_sec"] == 8102.35

    ner_res = NERCorpusPerformanceResult(
        dataset_name="Dataset B",
        backend_name="PEYMA",
        document_count=150,
        total_chars=15000,
        total_tokens=3000,
        median_latency_ms=50.1234,
        p95_latency_ms=70.5678,
        mean_latency_ms=52.0,
        docs_per_sec=19.95,
        tokens_per_sec=399.0,
    )
    d_ner = ner_res.to_dict()
    assert d_ner["backend_name"] == "PEYMA"
    assert d_ner["median_latency_ms"] == 50.1234

    batch_res = BatchOverheadResult(
        document_count=100,
        loop_total_ms=10.5,
        detect_many_total_ms=10.8,
        overhead_percentage=2.857,
        repetition_count=6,
    )
    d_batch = batch_res.to_dict()
    assert d_batch["overhead_percentage"] == 2.86
    assert d_batch["repetition_count"] == 6

    long_res = LongDocumentScalingResult(
        doc_id="long_doc_1",
        token_count=500,
        char_count=2000,
        inference_call_count=2,
        max_input_length=512,
        median_latency_ms=120.456,
        latency_ms_per_1k_tokens=240.912,
    )
    d_long = long_res.to_dict()
    assert d_long["doc_id"] == "long_doc_1"
    assert d_long["latency_ms_per_1k_tokens"] == 240.912


def test_batch_benchmark_counterbalanced_order() -> None:
    """Verify batch benchmark runs with counterbalanced ordering."""
    res = benchmark_batch_overhead(doc_count=10, warmup_runs=1, repetitions=6)
    assert res.document_count == 10
    assert res.repetition_count == 6
    assert res.loop_total_ms > 0.0
    assert res.detect_many_total_ms > 0.0


# -----------------------------------------------------------------------------
# 3. Privacy, Path, and Security Validations
# -----------------------------------------------------------------------------


def test_no_raw_text_in_result_json() -> None:
    """Verify that sample result dictionaries pass privacy verification."""
    clean_dict: dict[str, Any] = {
        "benchmark_name": "Phase 33 Performance Profiling",
        "doc_count": 150,
        "metrics": {"median_ms": 12.3},
    }
    # Should not raise
    validate_privacy_and_security(clean_dict)


def test_rejection_of_forbidden_keys_or_paths() -> None:
    """Verify that forbidden keys or workstation paths raise ValueError."""
    bad_dict_1 = {"username": "developer", "metrics": 12}
    with pytest.raises(ValueError, match="Forbidden key 'username'"):
        validate_privacy_and_security(bad_dict_1)

    bad_dict_2 = {"path_ref": "C:\\Users\\dev\\models\\peyma", "metrics": 12}
    with pytest.raises(ValueError, match="Workstation absolute path"):
        validate_privacy_and_security(bad_dict_2)


def test_environment_metadata_allowlist() -> None:
    """Verify environment metadata allowlist fields."""
    allowed_keys = {
        "python_version",
        "platform_system",
        "platform_release",
        "cpu_count",
        "cpu_architecture",
        "machine_architecture",
        "package_version",
        "max_length",
        "onnx_execution_provider",
        "benchmark_timestamp",
    }
    sample_env = {
        "python_version": "3.10.11",
        "platform_system": "Windows",
        "platform_release": "10",
        "cpu_count": 8,
        "cpu_architecture": "AMD64",
        "machine_architecture": "AMD64",
        "package_version": "0.3.0",
        "max_length": 512,
        "onnx_execution_provider": "CPUExecutionProvider",
        "benchmark_timestamp": "2026-09-08T12:00:00Z",
    }
    assert set(sample_env.keys()) == allowed_keys
    validate_privacy_and_security(sample_env)


# -----------------------------------------------------------------------------
# 4. Memory Profiling & Conversions
# -----------------------------------------------------------------------------


def test_memory_unit_conversion_and_struct() -> None:
    """Test ProcessMemoryInfo serialization."""
    mem = ProcessMemoryInfo(current_rss_mib=124.567, peak_rss_mib=250.891)
    d = mem.to_dict()
    assert d["current_rss_mib"] == 124.57
    assert d["peak_rss_mib"] == 250.89


def test_memory_unavailable_represented_as_null() -> None:
    """Test that unavailable memory measurements serialize to None / null."""
    mem = ProcessMemoryInfo(current_rss_mib=None, peak_rss_mib=None)
    d = mem.to_dict()
    assert d["current_rss_mib"] is None
    assert d["peak_rss_mib"] is None


def test_get_process_memory_mib_on_active_system() -> None:
    """Test that get_process_memory_mib executes on the active system without error."""
    mem = get_process_memory_mib()
    assert isinstance(mem, ProcessMemoryInfo)
    # On Windows/Linux/Darwin, either values are floats > 0 or None if sandboxed
    if mem.peak_rss_mib is not None:
        assert mem.peak_rss_mib > 0.0


# -----------------------------------------------------------------------------
# 5. Optimization Eligibility Logic & Gates
# -----------------------------------------------------------------------------


def test_optimization_eligibility_logic_no_optimization() -> None:
    """Test default NO_OPTIMIZATION_JUSTIFIED status and N/A exact output equality."""
    decision = evaluate_optimization_decision(
        optimization_attempted=False,
        is_fa_redact_owned=False,
        target_improvement_pct=0.0,
        max_regression_pct=0.0,
        exact_output_equality=None,
    )
    assert decision.status == "NO_OPTIMIZATION_JUSTIFIED"
    assert not decision.optimization_attempted
    assert not decision.is_fa_redact_owned_bottleneck
    assert decision.exact_output_equality_preserved is None


def test_less_than_10_percent_improvement_rejects_optimization() -> None:
    """Verify that improvement < 10% rejects the optimization."""
    decision = evaluate_optimization_decision(
        optimization_attempted=True,
        is_fa_redact_owned=True,
        target_improvement_pct=8.5,  # < 10%
        max_regression_pct=1.0,
        exact_output_equality=True,
    )
    assert decision.status == "OPTIMIZATION_REVERTED"


def test_greater_than_5_percent_regression_rejects_optimization() -> None:
    """Verify that collateral regression > 5% rejects the optimization."""
    decision = evaluate_optimization_decision(
        optimization_attempted=True,
        is_fa_redact_owned=True,
        target_improvement_pct=15.0,
        max_regression_pct=6.5,  # > 5%
        exact_output_equality=True,
    )
    assert decision.status == "OPTIMIZATION_REVERTED"


def test_exact_output_mismatch_rejects_optimization() -> None:
    """Verify that exact output mismatch rejects the optimization."""
    decision = evaluate_optimization_decision(
        optimization_attempted=True,
        is_fa_redact_owned=True,
        target_improvement_pct=25.0,
        max_regression_pct=0.0,
        exact_output_equality=False,  # Mismatch!
    )
    assert decision.status == "OPTIMIZATION_REVERTED"


def test_successful_optimization_decision_when_all_rules_pass() -> None:
    """Verify that optimization is retained when all 8 criteria and thresholds pass."""
    decision = evaluate_optimization_decision(
        optimization_attempted=True,
        is_fa_redact_owned=True,
        target_improvement_pct=18.5,
        max_regression_pct=2.0,
        exact_output_equality=True,
        zero_dependencies=True,
        zero_api_changes=True,
        defaults_unchanged=True,
        ner_labels_unchanged=True,
    )
    assert decision.status == "OPTIMIZATION_RETAINED"
    assert decision.exact_output_equality_preserved is True
    assert decision.zero_new_runtime_dependencies


# -----------------------------------------------------------------------------
# 6. Performance Recommendation Rubric
# -----------------------------------------------------------------------------


def test_onnx_performance_recommendation_rubric_pass() -> None:
    """Test ONNX qualification when latency reduction is >= 20% on both sets."""
    peyma_b = NERCorpusPerformanceResult(
        "B", "PEYMA", 150, 1000, 200, 100.0, 120.0, 105.0, 10.0, 20.0
    )
    onnx_b = NERCorpusPerformanceResult(
        "B", "ONNX", 150, 1000, 200, 75.0, 90.0, 78.0, 13.33, 26.66
    )  # 25% lower latency

    peyma_c = NERCorpusPerformanceResult(
        "C", "PEYMA", 120, 1000, 200, 100.0, 120.0, 105.0, 10.0, 20.0
    )
    onnx_c = NERCorpusPerformanceResult(
        "C", "ONNX", 120, 1000, 200, 70.0, 85.0, 72.0, 14.28, 28.56
    )  # 30% lower latency

    rec = evaluate_onnx_cpu_recommendation(
        peyma_b=peyma_b,
        onnx_b=onnx_b,
        peyma_c=peyma_c,
        onnx_c=onnx_c,
        peyma_peak_rss_mib=200.0,
        onnx_peak_rss_mib=210.0,  # 1.05x memory (< 1.25x)
    )
    assert rec["recommend_onnx_cpu"] is True
    assert rec["dataset_b_passed"] is True
    assert rec["dataset_c_passed"] is True
    assert rec["memory_gate_passed"] is True


def test_onnx_performance_recommendation_rubric_fail_latency_or_memory() -> None:
    """Test ONNX disqualification when threshold is missed on one dataset."""
    peyma_b = NERCorpusPerformanceResult(
        "B", "PEYMA", 150, 1000, 200, 100.0, 120.0, 105.0, 10.0, 20.0
    )
    onnx_b = NERCorpusPerformanceResult(
        "B", "ONNX", 150, 1000, 200, 95.0, 110.0, 98.0, 10.5, 21.0
    )  # Only 5% lower

    peyma_c = NERCorpusPerformanceResult(
        "C", "PEYMA", 120, 1000, 200, 100.0, 120.0, 105.0, 10.0, 20.0
    )
    onnx_c = NERCorpusPerformanceResult(
        "C", "ONNX", 120, 1000, 200, 70.0, 85.0, 72.0, 14.28, 28.56
    )

    rec = evaluate_onnx_cpu_recommendation(
        peyma_b=peyma_b,
        onnx_b=onnx_b,
        peyma_c=peyma_c,
        onnx_c=onnx_c,
        peyma_peak_rss_mib=200.0,
        onnx_peak_rss_mib=210.0,
    )
    assert rec["recommend_onnx_cpu"] is False
    assert rec["dataset_b_passed"] is False
    assert rec["dataset_c_passed"] is True


# -----------------------------------------------------------------------------
# 7. Package Invariants & Behavior
# -----------------------------------------------------------------------------


def test_core_dependencies_remain_empty() -> None:
    """Verify package base dependencies remain empty in pyproject.toml."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")
    assert "dependencies = []" in content


def test_package_version_remains_0_3_0() -> None:
    """Verify package version remains 0.3.0."""
    import fa_redact

    assert fa_redact.__version__ == "0.3.0"


def test_defaults_unchanged() -> None:
    """Verify default detectors in detect() remain exactly the 3 direct identifiers."""
    from fa_redact.pipeline import _DEFAULT_DETECTORS

    assert len(_DEFAULT_DETECTORS) == 3
    detector_types = tuple(type(d) for d in _DEFAULT_DETECTORS)
    assert detector_types == (
        IranianNationalIDDetector,
        IranianMobileNumberDetector,
        IranianIBANDetector,
    )


def test_clinical_defaults_unchanged() -> None:
    """Verify clinical default detectors and profiles remain unchanged."""
    profile = clinical_profile(template="discharge_summary")
    assert isinstance(profile, ClinicalRedactionProfile)
    detector_types = [type(d) for d in profile.detectors]
    assert IranianNationalIDDetector in detector_types
    assert IranianMobileNumberDetector in detector_types
    assert IranianIBANDetector in detector_types


# -----------------------------------------------------------------------------
# 8. Report & JSON Quality / Wording Guardrails
# -----------------------------------------------------------------------------


def test_unsupported_claims_absent_from_artifacts() -> None:
    """Verify unsupported claims are absent from report and artifacts."""
    root = Path(__file__).resolve().parent.parent
    report_path = root / "research" / "phase33_performance.md"
    json_path = root / "research" / "results" / "phase33_performance.json"
    changelog_path = root / "CHANGELOG.md"

    report_content = report_path.read_text(encoding="utf-8")
    json_content = json_path.read_text(encoding="utf-8")
    changelog_content = changelog_path.read_text(encoding="utf-8")

    forbidden_patterns = [
        ">98%",
        "<0.5 ms",
        "<0.5ms",
        "<1 ms",
        "<1ms",
        "< 0.01 ms",
        "2.8 MB/sec",
        "2.8MB/sec",
        "198.7% faster",
        "Instantaneous",
        "instant initialization",
        "PyTorch allocates runtime workspace",
    ]

    for p in forbidden_patterns:
        assert p not in report_content, f"Forbidden claim '{p}' found in report"
        assert p not in json_content, f"Forbidden claim '{p}' found in JSON"
        assert p not in changelog_content, f"Forbidden claim '{p}' found in CHANGELOG"


def test_tokenizer_tokens_per_sec_limitation_documented() -> None:
    """Verify tokenizer tokens/sec limitation is explicitly documented."""
    root = Path(__file__).resolve().parent.parent
    report_path = root / "research" / "phase33_performance.md"
    json_path = root / "research" / "results" / "phase33_performance.json"

    report_content = report_path.read_text(encoding="utf-8")
    json_data = json.loads(json_path.read_text(encoding="utf-8"))

    assert "different tokenizers" in report_content
    assert "tokens/sec" in json_data["measurement_notes"]["tokenizer_tokens_per_sec"]
    assert (
        "different tokenizers"
        in json_data["measurement_notes"]["tokenizer_tokens_per_sec"]
    )
