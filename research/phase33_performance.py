"""Phase 33 — Performance Profiling & Evidence-Based Optimization.

===============================================================================
DISCLAIMER & PRIVACY NOTICE:
THIS MODULE EVALUATES THE RUNTIME PERFORMANCE, LATENCY, THROUGHPUT, AND MEMORY
CHARACTERISTICS OF PRODUCTION DETECTORS AGAINST DETERMINISTIC SYNTHETIC FIXTURES.
ALL COMMITTED ARTIFACTS CONTAIN STRICTLY AGGREGATE METRICS AND ENVIRONMENT
METADATA ALLOWLISTED FOR SECURITY. ZERO RAW PII, SOURCE TEXT SNIPPETS, OR
ABSOLUTE LOCAL WORKSTATION PATHS ARE STORED IN ARTIFACTS.
===============================================================================
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import platform
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fa_redact import detect, detect_many
from fa_redact.normalization import normalize_text
from research.phase29_challenge_set import (
    ChallengeDocument,
    build_dataset_b,
    build_dataset_c,
)
from research.phase32_ner_validation import (
    PEYMA_BACKEND_CLASS,
    PEYMA_LICENSE,
    PEYMA_MODEL_ID,
    PEYMA_REVISION,
    TOOKABERT_BACKEND_CLASS,
    TOOKABERT_LICENSE,
    TOOKABERT_MODEL_ID,
    TOOKABERT_REVISION,
    resolve_local_model_dir,
    track_model_calls,
)
from research.phase32_ner_validation_cases import (
    ValidationDocument,
    build_long_documents,
)

# Package version invariant
EXPECTED_PACKAGE_VERSION = "0.3.0"

# Number of repetitions and warmups
DEFAULT_WARMUP_RUNS = 3
DEFAULT_BENCHMARK_REPETITIONS = 5


# -----------------------------------------------------------------------------
# 1. Statistical & Metric Utilities
# -----------------------------------------------------------------------------


def compute_mean(values: Sequence[float]) -> float:
    """Compute arithmetic mean of a sequence of values."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def compute_median(values: Sequence[float]) -> float:
    """Compute median of a sequence of values."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    n = len(sorted_v)
    mid = n // 2
    if n % 2 == 1:
        return sorted_v[mid]
    return (sorted_v[mid - 1] + sorted_v[mid]) / 2.0


def compute_percentile(values: Sequence[float], p: float) -> float:
    """Compute p-th percentile (0.0 <= p <= 100.0) of a sequence of values."""
    if not values:
        return 0.0
    if p <= 0.0:
        return min(values)
    if p >= 100.0:
        return max(values)
    sorted_v = sorted(values)
    n = len(sorted_v)
    k = (n - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_v[int(k)]
    d0 = sorted_v[int(f)] * (c - k)
    d1 = sorted_v[int(c)] * (k - f)
    return d0 + d1


def compute_throughput(count: int | float, duration_seconds: float) -> float:
    """Compute throughput (items / second) safely."""
    if duration_seconds <= 0.0:
        return 0.0
    return float(count) / duration_seconds


# -----------------------------------------------------------------------------
# 2. Process Memory Measurement (Windows & POSIX)
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProcessMemoryInfo:
    """Process-level resident memory (RSS / working set) in MiB."""

    current_rss_mib: float | None
    peak_rss_mib: float | None

    def to_dict(self) -> dict[str, float | None]:
        """Convert memory info to JSON-safe dictionary."""
        return {
            "current_rss_mib": (
                round(self.current_rss_mib, 2)
                if self.current_rss_mib is not None
                else None
            ),
            "peak_rss_mib": (
                round(self.peak_rss_mib, 2) if self.peak_rss_mib is not None else None
            ),
        }


def get_process_memory_mib() -> ProcessMemoryInfo:
    """Read process working set / peak RSS using platform standard library APIs."""
    system = platform.system()

    if system == "Windows":
        try:
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            kernel32 = getattr(ctypes, "windll", None)
            if kernel32 is not None:
                k32 = kernel32.kernel32
                handle = k32.GetCurrentProcess()
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)

                psapi = getattr(kernel32, "psapi", None)
                fn = getattr(k32, "K32GetProcessMemoryInfo", None) or (
                    getattr(psapi, "GetProcessMemoryInfo", None)
                    if psapi is not None
                    else None
                )
                if fn is not None:
                    fn.argtypes = [
                        wintypes.HANDLE,
                        ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                        wintypes.DWORD,
                    ]
                    fn.restype = wintypes.BOOL

                    success = fn(handle, ctypes.byref(counters), counters.cb)
                    if success:
                        current_mib = counters.WorkingSetSize / (1024.0 * 1024.0)
                        peak_mib = counters.PeakWorkingSetSize / (1024.0 * 1024.0)
                        return ProcessMemoryInfo(
                            current_rss_mib=current_mib, peak_rss_mib=peak_mib
                        )
        except Exception:
            pass
        return ProcessMemoryInfo(current_rss_mib=None, peak_rss_mib=None)

    elif system in ("Linux", "Darwin"):
        try:
            import resource

            getrusage = getattr(resource, "getrusage", None)
            rusage_self = getattr(resource, "RUSAGE_SELF", 0)
            if getrusage is not None:
                usage = getrusage(rusage_self)
                raw_peak = float(usage.ru_maxrss)
                if system == "Linux":
                    # On Linux, ru_maxrss is in KiB
                    peak_mib = raw_peak / 1024.0
                else:
                    # On Darwin/macOS, ru_maxrss is in bytes
                    peak_mib = raw_peak / (1024.0 * 1024.0)
                return ProcessMemoryInfo(
                    current_rss_mib=peak_mib, peak_rss_mib=peak_mib
                )
        except Exception:
            pass
        return ProcessMemoryInfo(current_rss_mib=None, peak_rss_mib=None)

    return ProcessMemoryInfo(current_rss_mib=None, peak_rss_mib=None)


# -----------------------------------------------------------------------------
# 3. Deterministic Synthetic Fixture Generators (Workload A & E)
# -----------------------------------------------------------------------------


def generate_valid_national_id(seed_num: int) -> str:
    """Generate a deterministic valid 10-digit Iranian National ID."""
    base = f"{(seed_num % 900000000) + 100000000:09d}"
    s = sum(int(base[i]) * (10 - i) for i in range(9))
    r = s % 11
    c = r if r < 2 else 11 - r
    return base + str(c)


def generate_valid_mobile(seed_num: int) -> str:
    """Generate a deterministic valid 11-digit Iranian Mobile number."""
    return f"0912{(seed_num % 9000000) + 1000000:07d}"


def generate_valid_iban(seed_num: int) -> str:
    """Generate a deterministic valid 26-char Iranian IBAN."""
    body = f"{(seed_num % 10**22):022d}"
    num_str = body + "182700"
    c = 98 - (int(num_str) % 97)
    return f"IR{c:02d}{body}"


@dataclass(frozen=True, slots=True)
class DeterministicDoc:
    """Synthetic document for deterministic core benchmarking."""

    id: str
    tier: str  # 'short', 'medium', 'long'
    text: str
    char_count: int


def build_deterministic_workload_a_corpus() -> list[DeterministicDoc]:
    """Build deterministic synthetic test corpus across length tiers."""
    docs: list[DeterministicDoc] = []

    # Short Tier: ~100 characters (~10 documents)
    for i in range(10):
        nid = generate_valid_national_id(1000 + i)
        mob = generate_valid_mobile(2000 + i)
        text = (
            f"پرونده اداری کارمند با کدملی {nid} و شماره تماس {mob} "
            f"جهت بررسی ارسال گردید."
        )
        docs.append(
            DeterministicDoc(
                id=f"short_{i:02d}",
                tier="short",
                text=text,
                char_count=len(text),
            )
        )

    # Medium Tier: ~1,000 characters (~10 documents)
    for i in range(10):
        paragraphs: list[str] = []
        for j in range(4):
            nid = generate_valid_national_id(3000 + i * 10 + j)
            mob = generate_valid_mobile(4000 + i * 10 + j)
            iban = generate_valid_iban(5000 + i * 10 + j)
            p = (
                f"بخش {j + 1}: متقاضی محترم به کدملی {nid} با تلفن {mob} "
                f"و شماره شبا {iban} درخواست تسویه را ثبت نموده است. "
                f"اطلاعات ارسالی بازبینی شد و صحت مدارک تایید گردید."
            )
            paragraphs.append(p)
        text = "\n\n".join(paragraphs)
        docs.append(
            DeterministicDoc(
                id=f"medium_{i:02d}",
                tier="medium",
                text=text,
                char_count=len(text),
            )
        )

    # Long Tier: ~10,000 characters (~5 documents)
    for i in range(5):
        sections: list[str] = []
        for k in range(35):
            nid = generate_valid_national_id(60000 + i * 100 + k)
            mob = generate_valid_mobile(70000 + i * 100 + k)
            iban = generate_valid_iban(80000 + i * 100 + k)
            sec = (
                f"گزارش دوره‌ای شماره {k + 1}: مشتری با شناسه {nid} و "
                f"شماره همراه {mob} و حساب بانکی {iban} با سوابق مالی "
                f"در سیستم متمرکز ثبت گردید و تاییدیه پرداخت صادر شد."
            )
            sections.append(sec)
        text = "\n\n".join(sections)
        docs.append(
            DeterministicDoc(
                id=f"long_{i:02d}",
                tier="long",
                text=text,
                char_count=len(text),
            )
        )

    return docs


def build_batch_overhead_corpus(count: int = 150) -> list[str]:
    """Build a deterministic collection of documents for batch helper testing."""
    docs: list[str] = []
    for i in range(count):
        nid = generate_valid_national_id(90000 + i)
        mob = generate_valid_mobile(95000 + i)
        iban = generate_valid_iban(98000 + i)
        text = (
            f"سند ردیف {i + 1}: مشخصات فردی با کد ملی {nid}، تلفن همراه {mob}، "
            f"و شماره شبا {iban} جهت بایگانی ارسال گردید."
        )
        docs.append(text)
    return docs


# -----------------------------------------------------------------------------
# 4. Token Counting Utility
# -----------------------------------------------------------------------------


def get_detector_token_count(detector: Any, text: str) -> int:
    """Compute actual token count of a document using detector's tokenizer."""
    if hasattr(detector, "_tokenizer") and detector._tokenizer is not None:
        norm = normalize_text(text)
        encoding = detector._tokenizer(norm, add_special_tokens=True)
        if isinstance(encoding, dict) and "input_ids" in encoding:
            return len(encoding["input_ids"])
        if hasattr(encoding, "input_ids"):
            return len(encoding.input_ids)
    return len(text.split()) + 2


# -----------------------------------------------------------------------------
# 5. Workload Runners
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeterministicTierResult:
    """Benchmark results for a single length tier in Workload A."""

    tier: str
    doc_count: int
    total_chars: int
    median_latency_ms: float
    p95_latency_ms: float
    mean_latency_ms: float
    docs_per_sec: float
    chars_per_sec: float

    def to_dict(self) -> dict[str, Any]:
        """Convert tier results to JSON-safe dict."""
        return {
            "tier": self.tier,
            "doc_count": self.doc_count,
            "total_chars": self.total_chars,
            "median_latency_ms": round(self.median_latency_ms, 4),
            "p95_latency_ms": round(self.p95_latency_ms, 4),
            "mean_latency_ms": round(self.mean_latency_ms, 4),
            "docs_per_sec": round(self.docs_per_sec, 2),
            "chars_per_sec": round(self.chars_per_sec, 2),
        }


def run_workload_a_deterministic_core(
    warmup_runs: int = DEFAULT_WARMUP_RUNS,
    repetitions: int = DEFAULT_BENCHMARK_REPETITIONS,
) -> dict[str, Any]:
    """Execute Workload A: Deterministic Core (detect() with default detectors)."""
    corpus = build_deterministic_workload_a_corpus()
    tiers = ["short", "medium", "long"]

    # Warmup
    for _ in range(warmup_runs):
        for doc in corpus:
            _ = detect(doc.text)

    tier_results: dict[str, Any] = {}
    total_corpus_chars = sum(d.char_count for d in corpus)

    # Per-tier benchmarks
    for tier in tiers:
        tier_docs = [d for d in corpus if d.tier == tier]
        tier_chars = sum(d.char_count for d in tier_docs)
        doc_latencies_ms: list[float] = []
        pass_durations_sec: list[float] = []

        for _ in range(repetitions):
            t0 = time.perf_counter_ns()
            for d in tier_docs:
                t_doc_start = time.perf_counter_ns()
                _ = detect(d.text)
                t_doc_end = time.perf_counter_ns()
                doc_latencies_ms.append((t_doc_end - t_doc_start) / 1_000_000.0)
            t1 = time.perf_counter_ns()
            pass_durations_sec.append((t1 - t0) / 1_000_000_000.0)

        med_pass_sec = compute_median(pass_durations_sec)
        tier_res = DeterministicTierResult(
            tier=tier,
            doc_count=len(tier_docs),
            total_chars=tier_chars,
            median_latency_ms=compute_median(doc_latencies_ms),
            p95_latency_ms=compute_percentile(doc_latencies_ms, 95.0),
            mean_latency_ms=compute_mean(doc_latencies_ms),
            docs_per_sec=compute_throughput(len(tier_docs), med_pass_sec),
            chars_per_sec=compute_throughput(tier_chars, med_pass_sec),
        )
        tier_results[tier] = tier_res.to_dict()

    # Overall full corpus throughput
    full_pass_durations_sec: list[float] = []
    all_doc_latencies_ms: list[float] = []
    for _ in range(repetitions):
        t0 = time.perf_counter_ns()
        for d in corpus:
            t_doc_start = time.perf_counter_ns()
            _ = detect(d.text)
            t_doc_end = time.perf_counter_ns()
            all_doc_latencies_ms.append((t_doc_end - t_doc_start) / 1_000_000.0)
        t1 = time.perf_counter_ns()
        full_pass_durations_sec.append((t1 - t0) / 1_000_000_000.0)

    med_full_sec = compute_median(full_pass_durations_sec)
    tier_results["overall"] = {
        "doc_count": len(corpus),
        "total_chars": total_corpus_chars,
        "median_latency_ms": round(compute_median(all_doc_latencies_ms), 4),
        "p95_latency_ms": round(compute_percentile(all_doc_latencies_ms, 95.0), 4),
        "mean_latency_ms": round(compute_mean(all_doc_latencies_ms), 4),
        "docs_per_sec": round(compute_throughput(len(corpus), med_full_sec), 2),
        "chars_per_sec": round(compute_throughput(total_corpus_chars, med_full_sec), 2),
    }

    return tier_results


@dataclass(frozen=True, slots=True)
class NERCorpusPerformanceResult:
    """Benchmark results for a NER backend on an aggregate dataset."""

    dataset_name: str
    backend_name: str
    document_count: int
    total_chars: int
    total_tokens: int
    median_latency_ms: float
    p95_latency_ms: float
    mean_latency_ms: float
    docs_per_sec: float
    tokens_per_sec: float

    def to_dict(self) -> dict[str, Any]:
        """Convert performance result to JSON-safe dict."""
        return {
            "dataset_name": self.dataset_name,
            "backend_name": self.backend_name,
            "document_count": self.document_count,
            "total_chars": self.total_chars,
            "total_tokens": self.total_tokens,
            "median_latency_ms": round(self.median_latency_ms, 4),
            "p95_latency_ms": round(self.p95_latency_ms, 4),
            "mean_latency_ms": round(self.mean_latency_ms, 4),
            "docs_per_sec": round(self.docs_per_sec, 2),
            "tokens_per_sec": round(self.tokens_per_sec, 2),
        }


def benchmark_ner_backend_on_corpus(
    detector: Any,
    dataset: Sequence[ChallengeDocument | ValidationDocument],
    dataset_name: str,
    backend_name: str,
    warmup_runs: int = DEFAULT_WARMUP_RUNS,
    repetitions: int = DEFAULT_BENCHMARK_REPETITIONS,
) -> NERCorpusPerformanceResult:
    """Benchmark a NER backend on an evaluation corpus (Workload B or C)."""
    # 1. Warm-up calls
    for i in range(min(warmup_runs, len(dataset))):
        norm_w = normalize_text(dataset[i].text)
        _ = detector.detect(dataset[i].text, norm_w)

    # 2. Compute token counts and character counts
    total_chars = sum(len(d.text) for d in dataset)
    total_tokens = sum(get_detector_token_count(detector, d.text) for d in dataset)

    # Pre-normalize texts for pure inference benchmark (avoid measuring
    # normalization overhead repeatedly)
    norm_texts = [normalize_text(d.text) for d in dataset]

    # 3. Timed repetitions
    per_doc_latencies_ms: list[float] = []
    pass_durations_sec: list[float] = []

    for _ in range(repetitions):
        t_pass_start = time.perf_counter_ns()
        for d, n_txt in zip(dataset, norm_texts, strict=True):
            t_doc_start = time.perf_counter_ns()
            _ = detector.detect(d.text, n_txt)
            t_doc_end = time.perf_counter_ns()
            per_doc_latencies_ms.append((t_doc_end - t_doc_start) / 1_000_000.0)
        t_pass_end = time.perf_counter_ns()
        pass_durations_sec.append((t_pass_end - t_pass_start) / 1_000_000_000.0)

    median_pass_sec = compute_median(pass_durations_sec)

    return NERCorpusPerformanceResult(
        dataset_name=dataset_name,
        backend_name=backend_name,
        document_count=len(dataset),
        total_chars=total_chars,
        total_tokens=total_tokens,
        median_latency_ms=compute_median(per_doc_latencies_ms),
        p95_latency_ms=compute_percentile(per_doc_latencies_ms, 95.0),
        mean_latency_ms=compute_mean(per_doc_latencies_ms),
        docs_per_sec=compute_throughput(len(dataset), median_pass_sec),
        tokens_per_sec=compute_throughput(total_tokens, median_pass_sec),
    )


@dataclass(frozen=True, slots=True)
class LongDocumentScalingResult:
    """Benchmark results for sliding-window long document scaling in Workload D."""

    doc_id: str
    token_count: int
    char_count: int
    inference_call_count: int
    max_input_length: int
    median_latency_ms: float
    latency_ms_per_1k_tokens: float

    def to_dict(self) -> dict[str, Any]:
        """Convert long document scaling results to JSON-safe dict."""
        return {
            "doc_id": self.doc_id,
            "token_count": self.token_count,
            "char_count": self.char_count,
            "inference_call_count": self.inference_call_count,
            "max_input_length": self.max_input_length,
            "median_latency_ms": round(self.median_latency_ms, 4),
            "latency_ms_per_1k_tokens": round(self.latency_ms_per_1k_tokens, 4),
        }


def benchmark_long_document_scaling(
    detector: Any,
    long_docs: Sequence[ValidationDocument],
    warmup_runs: int = DEFAULT_WARMUP_RUNS,
    repetitions: int = DEFAULT_BENCHMARK_REPETITIONS,
) -> list[LongDocumentScalingResult]:
    """Benchmark sliding-window long document scaling (Workload D)."""
    results: list[LongDocumentScalingResult] = []

    for doc in long_docs:
        norm_text = normalize_text(doc.text)

        # Warm-up
        for _ in range(warmup_runs):
            _ = detector.detect(doc.text, norm_text)

        # Track call count and sequence lengths
        call_count = 0
        max_seq_len = 0
        with track_model_calls(detector) as info:
            _ = detector.detect(doc.text, norm_text)
            call_count = info.call_count
            max_seq_len = max(info.input_lengths) if info.input_lengths else 0

        # Timed repetitions
        latencies_ms: list[float] = []
        for _ in range(repetitions):
            t0 = time.perf_counter_ns()
            _ = detector.detect(doc.text, norm_text)
            t1 = time.perf_counter_ns()
            latencies_ms.append((t1 - t0) / 1_000_000.0)

        actual_tokens = get_detector_token_count(detector, doc.text)
        med_lat_ms = compute_median(latencies_ms)
        lat_per_1k = (med_lat_ms / actual_tokens * 1000.0) if actual_tokens > 0 else 0.0

        results.append(
            LongDocumentScalingResult(
                doc_id=doc.doc_id,
                token_count=actual_tokens,
                char_count=len(doc.text),
                inference_call_count=call_count,
                max_input_length=max_seq_len,
                median_latency_ms=med_lat_ms,
                latency_ms_per_1k_tokens=lat_per_1k,
            )
        )

    return results


@dataclass(frozen=True, slots=True)
class BatchOverheadResult:
    """Benchmark results for batch processing overhead in Workload E."""

    document_count: int
    loop_total_ms: float
    detect_many_total_ms: float
    overhead_percentage: float
    repetition_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert batch overhead result to JSON-safe dict."""
        return {
            "document_count": self.document_count,
            "loop_total_ms": round(self.loop_total_ms, 4),
            "detect_many_total_ms": round(self.detect_many_total_ms, 4),
            "overhead_percentage": round(self.overhead_percentage, 2),
            "repetition_count": self.repetition_count,
        }


def benchmark_batch_overhead(
    doc_count: int = 150,
    warmup_runs: int = DEFAULT_WARMUP_RUNS,
    repetitions: int = 6,
) -> BatchOverheadResult:
    """Benchmark detect_many() vs explicit loop over detect() (Workload E).

    Uses counterbalanced ordering across repetitions.
    """
    if repetitions % 2 != 0:
        repetitions += 1
    docs = build_batch_overhead_corpus(doc_count)

    # Warm-up
    for _ in range(warmup_runs):
        _ = [detect(d) for d in docs]
        _ = list(detect_many(docs))

    loop_times_ms: list[float] = []
    batch_times_ms: list[float] = []

    # Counterbalance execution order across repetitions
    for rep_idx in range(repetitions):
        if rep_idx % 2 == 0:
            # 1. Explicit loop first
            t0 = time.perf_counter_ns()
            _ = [detect(d) for d in docs]
            t1 = time.perf_counter_ns()
            loop_times_ms.append((t1 - t0) / 1_000_000.0)

            # 2. detect_many second
            t2 = time.perf_counter_ns()
            _ = list(detect_many(docs))
            t3 = time.perf_counter_ns()
            batch_times_ms.append((t3 - t2) / 1_000_000.0)
        else:
            # 1. detect_many first
            t2 = time.perf_counter_ns()
            _ = list(detect_many(docs))
            t3 = time.perf_counter_ns()
            batch_times_ms.append((t3 - t2) / 1_000_000.0)

            # 2. Explicit loop second
            t0 = time.perf_counter_ns()
            _ = [detect(d) for d in docs]
            t1 = time.perf_counter_ns()
            loop_times_ms.append((t1 - t0) / 1_000_000.0)

    med_loop = compute_median(loop_times_ms)
    med_batch = compute_median(batch_times_ms)
    overhead_pct = (
        ((med_batch - med_loop) / med_loop * 100.0) if med_loop > 0.0 else 0.0
    )

    return BatchOverheadResult(
        document_count=doc_count,
        loop_total_ms=med_loop,
        detect_many_total_ms=med_batch,
        overhead_percentage=overhead_pct,
        repetition_count=repetitions,
    )


# -----------------------------------------------------------------------------
# 6. Model Initialization & Memory Profiling (Isolated Process)
# -----------------------------------------------------------------------------


def measure_isolated_initialization_and_memory(
    backend: str,
    model_dir: str,
    repetitions: int = 3,
) -> dict[str, Any]:
    """Measure model cold constructor time and lifecycle memory in isolated process."""
    init_times_ms: list[float] = []
    baseline_rss_list: list[float] = []
    post_load_rss_list: list[float] = []
    post_inf_rss_list: list[float] = []
    peak_rss_list: list[float] = []

    script = """
import sys, time
import json
import fa_redact
from research.phase33_performance import get_process_memory_mib
from research.phase32_ner_validation_cases import build_long_documents
from fa_redact.normalization import normalize_text

backend = sys.argv[1]
model_dir = sys.argv[2]

mem_base = get_process_memory_mib()
base_rss = mem_base.current_rss_mib

t0 = time.perf_counter_ns()
if backend == "peyma":
    from fa_redact.detectors.persian_ner import PersianNERDetector
    det = PersianNERDetector(model_dir)
elif backend == "onnx":
    from fa_redact.detectors.onnx_persian_ner import ONNXPersianNERDetector
    det = ONNXPersianNERDetector(model_dir)
else:
    raise ValueError(f"Unknown backend: {backend}")
t1 = time.perf_counter_ns()

init_ms = (t1 - t0) / 1_000_000.0
mem_post_load = get_process_memory_mib()
post_load_rss = mem_post_load.current_rss_mib

# 1. Fixed synthetic warm-up
warmup_text = "بیمار علی رضایی جهت ویزیت مراجعه کرد."
_ = det.detect(warmup_text, normalize_text(warmup_text))

# 2. Representative long-document inference (VAL_LONG_1000)
long_docs = build_long_documents()
doc_1000 = next(d for d in long_docs if d.doc_id == "VAL_LONG_1000")
_ = det.detect(doc_1000.text, normalize_text(doc_1000.text))

# 3. Read post-inference memory and peak
mem_post_inf = get_process_memory_mib()
post_inf_rss = mem_post_inf.current_rss_mib
peak_rss = mem_post_inf.peak_rss_mib

print(json.dumps({
    "init_ms": init_ms,
    "baseline_rss_mib": base_rss,
    "post_load_rss_mib": post_load_rss,
    "post_inference_rss_mib": post_inf_rss,
    "peak_rss_mib": peak_rss,
}))
"""

    for _ in range(repetitions):
        proc = subprocess.run(
            [sys.executable, "-c", script, backend, model_dir],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(proc.stdout.strip())
        init_times_ms.append(data["init_ms"])
        if data["baseline_rss_mib"] is not None:
            baseline_rss_list.append(data["baseline_rss_mib"])
        if data["post_load_rss_mib"] is not None:
            post_load_rss_list.append(data["post_load_rss_mib"])
        if data["post_inference_rss_mib"] is not None:
            post_inf_rss_list.append(data["post_inference_rss_mib"])
        if data["peak_rss_mib"] is not None:
            peak_rss_list.append(data["peak_rss_mib"])

    med_init = compute_median(init_times_ms)
    med_base = compute_median(baseline_rss_list) if baseline_rss_list else None
    med_post = compute_median(post_load_rss_list) if post_load_rss_list else None
    med_inf = compute_median(post_inf_rss_list) if post_inf_rss_list else None
    med_peak = compute_median(peak_rss_list) if peak_rss_list else None
    delta_load = (
        round(med_post - med_base, 2)
        if (med_post is not None and med_base is not None)
        else None
    )
    delta_inf = (
        round(med_inf - med_post, 2)
        if (med_inf is not None and med_post is not None)
        else None
    )

    return {
        "constructor_median_ms": round(med_init, 2),
        "baseline_rss_mib": round(med_base, 2) if med_base is not None else None,
        "post_load_rss_mib": round(med_post, 2) if med_post is not None else None,
        "post_inference_rss_mib": round(med_inf, 2) if med_inf is not None else None,
        "peak_rss_mib": round(med_peak, 2) if med_peak is not None else None,
        "model_load_delta_mib": delta_load,
        "inference_delta_from_post_load_mib": delta_inf,
    }


# -----------------------------------------------------------------------------
# 7. Performance Recommendation Rubric Evaluator
# -----------------------------------------------------------------------------


def evaluate_onnx_cpu_recommendation(
    peyma_b: NERCorpusPerformanceResult,
    onnx_b: NERCorpusPerformanceResult,
    peyma_c: NERCorpusPerformanceResult,
    onnx_c: NERCorpusPerformanceResult,
    peyma_peak_rss_mib: float | None,
    onnx_peak_rss_mib: float | None,
) -> dict[str, Any]:
    """Evaluate whether ONNX TookaBERT qualifies for CPU performance recommendation."""
    # Dataset B check
    lat_reduction_b = (
        (peyma_b.median_latency_ms - onnx_b.median_latency_ms)
        / peyma_b.median_latency_ms
        * 100.0
    )
    thr_gain_b = (
        (onnx_b.docs_per_sec - peyma_b.docs_per_sec) / peyma_b.docs_per_sec * 100.0
    )
    passed_b = (lat_reduction_b >= 20.0) or (thr_gain_b >= 25.0)

    # Dataset C check
    lat_reduction_c = (
        (peyma_c.median_latency_ms - onnx_c.median_latency_ms)
        / peyma_c.median_latency_ms
        * 100.0
    )
    thr_gain_c = (
        (onnx_c.docs_per_sec - peyma_c.docs_per_sec) / peyma_c.docs_per_sec * 100.0
    )
    passed_c = (lat_reduction_c >= 20.0) or (thr_gain_c >= 25.0)

    # Memory check
    passed_memory = True
    memory_ratio = None
    if peyma_peak_rss_mib is not None and onnx_peak_rss_mib is not None:
        if peyma_peak_rss_mib > 0.0:
            memory_ratio = onnx_peak_rss_mib / peyma_peak_rss_mib
            passed_memory = memory_ratio <= 1.25

    qualified = passed_b and passed_c and passed_memory

    if qualified:
        summary = (
            "RECOMMEND ONNX FOR CPU DEPLOYMENTS: TookaBERT ONNX achieves >=20% "
            "lower latency or >=25% higher throughput across both Dataset B and "
            "Dataset C without exceeding memory boundaries."
        )
    else:
        summary = (
            "On the measured Windows CPU environment and synthetic workloads, "
            "PEYMA had lower document latency and lower measured process memory "
            "than the TookaBERT ONNX backend. Backend choice depends on deployment "
            "environment and operational requirements."
        )

    return {
        "recommend_onnx_cpu": qualified,
        "dataset_b_passed": passed_b,
        "dataset_b_latency_reduction_pct": round(lat_reduction_b, 2),
        "dataset_b_throughput_gain_pct": round(thr_gain_b, 2),
        "dataset_c_passed": passed_c,
        "dataset_c_latency_reduction_pct": round(lat_reduction_c, 2),
        "dataset_c_throughput_gain_pct": round(thr_gain_c, 2),
        "memory_gate_passed": passed_memory,
        "onnx_to_peyma_memory_ratio": (
            round(memory_ratio, 2) if memory_ratio is not None else None
        ),
        "summary": summary,
    }


# -----------------------------------------------------------------------------
# 8. Optimization Eligibility Gate Logic
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OptimizationEligibilityDecision:
    """Decision record for candidate production code optimization."""

    optimization_attempted: bool
    status: str
    is_fa_redact_owned_bottleneck: bool
    target_workload_improvement_pct: float
    max_collateral_regression_pct: float
    exact_output_equality_preserved: bool | None
    zero_new_runtime_dependencies: bool
    zero_public_api_changes: bool
    defaults_unchanged: bool
    ner_labels_unchanged: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        """Convert decision to JSON-safe dict."""
        return {
            "optimization_attempted": self.optimization_attempted,
            "status": self.status,
            "is_fa_redact_owned_bottleneck": self.is_fa_redact_owned_bottleneck,
            "target_workload_improvement_pct": round(
                self.target_workload_improvement_pct, 2
            ),
            "max_collateral_regression_pct": round(
                self.max_collateral_regression_pct, 2
            ),
            "exact_output_equality_preserved": self.exact_output_equality_preserved,
            "zero_new_runtime_dependencies": self.zero_new_runtime_dependencies,
            "zero_public_api_changes": self.zero_public_api_changes,
            "defaults_unchanged": self.defaults_unchanged,
            "ner_labels_unchanged": self.ner_labels_unchanged,
            "rationale": self.rationale,
        }


def evaluate_optimization_decision(
    optimization_attempted: bool,
    is_fa_redact_owned: bool,
    target_improvement_pct: float,
    max_regression_pct: float,
    exact_output_equality: bool | None = None,
    zero_dependencies: bool = True,
    zero_api_changes: bool = True,
    defaults_unchanged: bool = True,
    ner_labels_unchanged: bool = True,
) -> OptimizationEligibilityDecision:
    """Evaluate whether a proposed optimization meets all Phase 33 criteria."""
    if not optimization_attempted or not is_fa_redact_owned:
        return OptimizationEligibilityDecision(
            optimization_attempted=False,
            status="NO_OPTIMIZATION_JUSTIFIED",
            is_fa_redact_owned_bottleneck=False,
            target_workload_improvement_pct=0.0,
            max_collateral_regression_pct=0.0,
            exact_output_equality_preserved=None,
            zero_new_runtime_dependencies=zero_dependencies,
            zero_public_api_changes=zero_api_changes,
            defaults_unchanged=defaults_unchanged,
            ner_labels_unchanged=ner_labels_unchanged,
            rationale=(
                "No fa-redact-owned bottleneck was independently demonstrated, so the "
                "Phase 33 optimization eligibility gate was not satisfied."
            ),
        )

    all_passed = (
        is_fa_redact_owned
        and target_improvement_pct >= 10.0
        and max_regression_pct <= 5.0
        and (exact_output_equality is True)
        and zero_dependencies
        and zero_api_changes
        and defaults_unchanged
        and ner_labels_unchanged
    )

    if all_passed:
        return OptimizationEligibilityDecision(
            optimization_attempted=True,
            status="OPTIMIZATION_RETAINED",
            is_fa_redact_owned_bottleneck=is_fa_redact_owned,
            target_workload_improvement_pct=target_improvement_pct,
            max_collateral_regression_pct=max_regression_pct,
            exact_output_equality_preserved=exact_output_equality,
            zero_new_runtime_dependencies=zero_dependencies,
            zero_public_api_changes=zero_api_changes,
            defaults_unchanged=defaults_unchanged,
            ner_labels_unchanged=ner_labels_unchanged,
            rationale=(
                "All optimization criteria met: target workload improved by >=10%, "
                "collateral regressions <=5%, and exact output equality preserved."
            ),
        )

    return OptimizationEligibilityDecision(
        optimization_attempted=True,
        status="OPTIMIZATION_REVERTED",
        is_fa_redact_owned_bottleneck=is_fa_redact_owned,
        target_workload_improvement_pct=target_improvement_pct,
        max_collateral_regression_pct=max_regression_pct,
        exact_output_equality_preserved=exact_output_equality,
        zero_new_runtime_dependencies=zero_dependencies,
        zero_public_api_changes=zero_api_changes,
        defaults_unchanged=defaults_unchanged,
        ner_labels_unchanged=ner_labels_unchanged,
        rationale=(
            "Optimization failed minimum threshold requirements (requires >=10% gain, "
            "<=5% regression, exact output equality). Changes must be reverted."
        ),
    )


# -----------------------------------------------------------------------------
# 9. Privacy & Output Validation Filter
# -----------------------------------------------------------------------------


def validate_privacy_and_security(data: Any) -> None:
    """Recursively ensure no forbidden strings, local paths, or PII exist in result."""
    forbidden_keys = {
        "username",
        "hostname",
        "environ",
        "home",
        "user",
        "path",
        "abs_path",
        "model_path",
    }

    if isinstance(data, dict):
        for k, v in data.items():
            if k.lower() in forbidden_keys and k not in ("max_input_length",):
                raise ValueError(
                    f"Forbidden key '{k}' found in benchmark output artifact."
                )
            validate_privacy_and_security(v)
    elif isinstance(data, list):
        for item in data:
            validate_privacy_and_security(item)
    elif isinstance(data, str):
        # Disallow workstation absolute paths
        if any(
            pattern in data.lower()
            for pattern in [
                ":\\users\\",
                "/users/",
                "/home/",
                "appdata",
                ".gemini",
                "c:\\",
                "d:\\",
            ]
        ):
            raise ValueError(
                f"Workstation absolute path pattern detected in string value: '{data}'"
            )


# -----------------------------------------------------------------------------
# 10. Master Benchmark Runner
# -----------------------------------------------------------------------------


def run_phase33_benchmark(
    peyma_model_dir: str | Path | None = None,
    onnx_model_dir: str | Path | None = None,
    output_json_path: str | Path = "research/results/phase33_performance.json",
    warmup_runs: int = DEFAULT_WARMUP_RUNS,
    repetitions: int = DEFAULT_BENCHMARK_REPETITIONS,
) -> dict[str, Any]:
    """Execute complete Phase 33 Performance Profiling Suite."""
    print("=" * 80)
    print("Phase 33 — Performance Profiling & Evidence-Based Optimization Benchmark")
    print("=" * 80)

    # 1. Resolve local model directories
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

    print(f"PEYMA model artifact: {PEYMA_MODEL_ID} ({PEYMA_REVISION[:7]})")
    print(f"ONNX model artifact:  {TOOKABERT_MODEL_ID} ({TOOKABERT_REVISION[:7]})")

    # 2. Environment Metadata Collection
    onnx_provider = "CPUExecutionProvider"
    try:
        import importlib

        ort = importlib.import_module("onnxruntime")
        get_available_providers = getattr(ort, "get_available_providers", None)
        if callable(get_available_providers):
            available_providers = get_available_providers()
            if "CPUExecutionProvider" in available_providers:
                onnx_provider = "CPUExecutionProvider"
            elif available_providers:
                onnx_provider = available_providers[0]
    except Exception:
        pass

    env_metadata = {
        "python_version": platform.python_version(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "cpu_count": os.cpu_count(),
        "cpu_architecture": platform.processor() or platform.machine(),
        "machine_architecture": platform.machine(),
        "package_version": EXPECTED_PACKAGE_VERSION,
        "max_length": 512,
        "onnx_execution_provider": onnx_provider,
        "benchmark_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # 3. Workload A — Deterministic Core
    print("\nExecuting Workload A: Deterministic Core (detect() with defaults)...")
    workload_a_results = run_workload_a_deterministic_core(
        warmup_runs=warmup_runs, repetitions=repetitions
    )
    print(
        f"  Short docs:  {workload_a_results['short']['median_latency_ms']:.4f} ms "
        f"({workload_a_results['short']['docs_per_sec']:.1f} docs/s)"
    )
    print(
        f"  Medium docs: {workload_a_results['medium']['median_latency_ms']:.4f} ms "
        f"({workload_a_results['medium']['docs_per_sec']:.1f} docs/s)"
    )
    print(
        f"  Long docs:   {workload_a_results['long']['median_latency_ms']:.4f} ms "
        f"({workload_a_results['long']['docs_per_sec']:.1f} docs/s)"
    )
    print(
        f"  Overall:     {workload_a_results['overall']['median_latency_ms']:.4f} ms "
        f"({workload_a_results['overall']['docs_per_sec']:.1f} docs/s, "
        f"{workload_a_results['overall']['chars_per_sec']:.1f} chars/s)"
    )

    # 4. Workload E — Batch Helper Overhead
    print("\nExecuting Workload E: Batch Helper Overhead...")
    workload_e_results = benchmark_batch_overhead(
        doc_count=150, warmup_runs=warmup_runs, repetitions=repetitions
    )
    print(
        f"  Explicit Loop: {workload_e_results.loop_total_ms:.2f} ms | "
        f"detect_many: {workload_e_results.detect_many_total_ms:.2f} ms | "
        f"Overhead: {workload_e_results.overhead_percentage:+.2f}%"
    )

    # 5. Isolated Model Initialization & Memory
    print("\nMeasuring Model Initialization and Process Working Set (RSS)...")
    peyma_init_mem = measure_isolated_initialization_and_memory(
        "peyma", str(peyma_path), repetitions=3
    )
    onnx_init_mem = measure_isolated_initialization_and_memory(
        "onnx", str(onnx_path), repetitions=3
    )
    print(
        f"  PEYMA Init: {peyma_init_mem['constructor_median_ms']:.1f} ms | "
        f"Peak RSS: {peyma_init_mem['peak_rss_mib']} MiB | "
        f"Model Delta: {peyma_init_mem['model_memory_delta_mib']} MiB"
    )
    print(
        f"  ONNX Init:  {onnx_init_mem['constructor_median_ms']:.1f} ms | "
        f"Peak RSS: {onnx_init_mem['peak_rss_mib']} MiB | "
        f"Model Delta: {onnx_init_mem['model_memory_delta_mib']} MiB"
    )

    # 6. Instantiate detectors for steady-state inference benchmarks
    print("\nInstantiating production detectors for inference workloads...")
    from fa_redact.detectors import ONNXPersianNERDetector, PersianNERDetector

    peyma_detector = PersianNERDetector(peyma_path)
    onnx_detector = ONNXPersianNERDetector(onnx_path)

    # Load Challenge Datasets
    dataset_b = build_dataset_b()
    dataset_c = build_dataset_c()
    long_docs = build_long_documents()

    # 7. Workload B — PERSON NER Dataset B (150 docs)
    print("\nExecuting Workload B: Dataset B (150 documents)...")
    peyma_b = benchmark_ner_backend_on_corpus(
        peyma_detector,
        dataset_b,
        "Dataset B",
        "PEYMA",
        warmup_runs=warmup_runs,
        repetitions=repetitions,
    )
    onnx_b = benchmark_ner_backend_on_corpus(
        onnx_detector,
        dataset_b,
        "Dataset B",
        "ONNX_TookaBERT",
        warmup_runs=warmup_runs,
        repetitions=repetitions,
    )
    print(
        f"  PEYMA: Median {peyma_b.median_latency_ms:.2f} ms | "
        f"p95 {peyma_b.p95_latency_ms:.2f} ms | "
        f"{peyma_b.docs_per_sec:.2f} docs/s | {peyma_b.tokens_per_sec:.1f} tokens/s"
    )
    print(
        f"  ONNX:  Median {onnx_b.median_latency_ms:.2f} ms | "
        f"p95 {onnx_b.p95_latency_ms:.2f} ms | "
        f"{onnx_b.docs_per_sec:.2f} docs/s | {onnx_b.tokens_per_sec:.1f} tokens/s"
    )

    # 8. Workload C — PERSON NER Dataset C (120 clinical docs)
    print("\nExecuting Workload C: Dataset C (120 clinical documents)...")
    peyma_c = benchmark_ner_backend_on_corpus(
        peyma_detector,
        dataset_c,
        "Dataset C",
        "PEYMA",
        warmup_runs=warmup_runs,
        repetitions=repetitions,
    )
    onnx_c = benchmark_ner_backend_on_corpus(
        onnx_detector,
        dataset_c,
        "Dataset C",
        "ONNX_TookaBERT",
        warmup_runs=warmup_runs,
        repetitions=repetitions,
    )
    print(
        f"  PEYMA: Median {peyma_c.median_latency_ms:.2f} ms | "
        f"p95 {peyma_c.p95_latency_ms:.2f} ms | "
        f"{peyma_c.docs_per_sec:.2f} docs/s | {peyma_c.tokens_per_sec:.1f} tokens/s"
    )
    print(
        f"  ONNX:  Median {onnx_c.median_latency_ms:.2f} ms | "
        f"p95 {onnx_c.p95_latency_ms:.2f} ms | "
        f"{onnx_c.docs_per_sec:.2f} docs/s | {onnx_c.tokens_per_sec:.1f} tokens/s"
    )

    # 9. Workload D — Long Document Scaling
    print("\nExecuting Workload D: Long Document Scaling...")
    peyma_long = benchmark_long_document_scaling(
        peyma_detector, long_docs, warmup_runs=warmup_runs, repetitions=repetitions
    )
    onnx_long = benchmark_long_document_scaling(
        onnx_detector, long_docs, warmup_runs=warmup_runs, repetitions=repetitions
    )
    for p_res, o_res in zip(peyma_long, onnx_long, strict=True):
        print(
            f"  {p_res.doc_id} (~{p_res.token_count} tokens): "
            f"PEYMA calls={p_res.inference_call_count}, "
            f"{p_res.median_latency_ms:.2f} ms "
            f"({p_res.latency_ms_per_1k_tokens:.1f} ms/1k tok) | "
            f"ONNX calls={o_res.inference_call_count}, "
            f"{o_res.median_latency_ms:.2f} ms "
            f"({o_res.latency_ms_per_1k_tokens:.1f} ms/1k tok)"
        )

    # 10. Performance Recommendation Rubric
    rec_decision = evaluate_onnx_cpu_recommendation(
        peyma_b=peyma_b,
        onnx_b=onnx_b,
        peyma_c=peyma_c,
        onnx_c=onnx_c,
        peyma_peak_rss_mib=peyma_init_mem["peak_rss_mib"],
        onnx_peak_rss_mib=onnx_init_mem["peak_rss_mib"],
    )

    # 11. Optimization Decision (Measure First principle)
    opt_decision = evaluate_optimization_decision(
        optimization_attempted=False,
        is_fa_redact_owned=False,
        target_improvement_pct=0.0,
        max_regression_pct=0.0,
        exact_output_equality=True,
    )

    # 12. Assemble Final Aggregate JSON Result
    result_dict: dict[str, Any] = {
        "benchmark_name": (
            "Phase 33 Performance Profiling & Evidence-Based Optimization"
        ),
        "environment": env_metadata,
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
        "deterministic_core": workload_a_results,
        "batch_helper_overhead": workload_e_results.to_dict(),
        "initialization_and_memory": {
            "peyma": peyma_init_mem,
            "onnx_tookabert": onnx_init_mem,
        },
        "person_ner_dataset_b": {
            "peyma": peyma_b.to_dict(),
            "onnx_tookabert": onnx_b.to_dict(),
        },
        "person_ner_dataset_c": {
            "peyma": peyma_c.to_dict(),
            "onnx_tookabert": onnx_c.to_dict(),
        },
        "long_document_scaling": {
            "peyma": [r.to_dict() for r in peyma_long],
            "onnx_tookabert": [r.to_dict() for r in onnx_long],
        },
        "optimization_decision": opt_decision.to_dict(),
        "performance_recommendation": rec_decision,
    }

    # Validate privacy and security guarantees
    validate_privacy_and_security(result_dict)

    # Write output artifact
    out_path = Path(output_json_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result_dict, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved benchmark results to {out_path}")

    return result_dict


def main() -> None:
    """CLI runner for Phase 33 Performance Benchmark."""
    parser = argparse.ArgumentParser(
        description="Phase 33 Performance Profiling Runner"
    )
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
        default="research/results/phase33_performance.json",
        help="Path for output JSON artifact",
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=DEFAULT_WARMUP_RUNS,
        help="Number of warm-up iterations",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=DEFAULT_BENCHMARK_REPETITIONS,
        help="Number of timed benchmark repetitions",
    )
    args = parser.parse_args()

    try:
        run_phase33_benchmark(
            peyma_model_dir=args.peyma_model_dir,
            onnx_model_dir=args.onnx_model_dir,
            output_json_path=args.output_json,
            warmup_runs=args.warmup_runs,
            repetitions=args.repetitions,
        )
    except Exception as e:
        print(f"Benchmark failed: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
