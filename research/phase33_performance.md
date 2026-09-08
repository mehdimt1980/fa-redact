# Phase 33 — Performance Profiling & Evidence-Based Optimization Report

> **Authoritative Deliverable:** Phase 33 Research & Empirical Profiling  
> **Status:** `COMPLETED`  
> **Outcome:** `NO PRODUCTION OPTIMIZATION JUSTIFIED`  
> **Date:** September 2026  
> **Branch:** `research/phase33-performance`  
> **Base Version:** `0.3.0` (`dependencies = []`)  
> **Authoritative Result Artifact:** `research/results/phase33_performance.json`

---

## 1. Executive Summary

Phase 33 profiled the CPU performance, latency, throughput, long-document sliding-window scaling, model initialization, and process memory (RSS) footprints across all `fa-redact` execution paths:
1. **Zero-Dependency Deterministic Core:** `fa_redact.detect()` with default identifiers (`IR_NATIONAL_ID`, `IR_MOBILE`, `IR_IBAN`).
2. **PEYMA Reference Model:** `fa_redact.PersianNERDetector` (`HooshvareLab/bert-fa-base-uncased-ner-peyma` @ `8b7b633`).
3. **TookaBERT ONNX Alternative:** `fa_redact.ONNXPersianNERDetector` (`Reza2kn/openmed-persian-pii-tookabert-large-onnx-int4` @ `27dc2a6`).
4. **Sliding-Window Long-Document Processing:** Documents from ~250 to ~1000 tokens.
5. **Streaming Batch Processing Helper:** `fa_redact.detect_many()` vs explicit Python loops with counterbalanced execution order.

### Key Empirical Findings

| Workload | PEYMA (PyTorch) | TookaBERT (ONNX INT4) | Deterministic Core | Unit |
| :--- | :--- | :--- | :--- | :--- |
| **Cold Constructor Time** | **6,412.9 ms** (~6.4s) | **7,768.9 ms** (~7.8s) | Not measured | Median ms |
| **Baseline Interpreter RSS** | 19.32 MiB | 19.28 MiB | ~19.1 MiB | MiB |
| **Post-Load RSS** | **348.04 MiB** | **728.85 MiB** | — | MiB |
| **Post-Inference RSS** | **714.75 MiB** | **885.00 MiB** | — | MiB |
| **Process Peak RSS** | **714.76 MiB** | **887.91 MiB** | ~19.1 MiB | MiB |
| **Model Load Delta** | **328.71 MiB** | **709.57 MiB** | 0.0 MiB | MiB |
| **Inference Delta from Post-Load** | **366.71 MiB** | **156.16 MiB** | — | MiB |
| **Dataset B Median Latency (150 docs)** | **69.56 ms** | **91.22 ms** | 0.18 ms | ms / doc |
| **Dataset B Throughput** | **12.50 docs/s** (215.9 tok/s) | **9.61 docs/s** (222.8 tok/s) | 1,747.8 docs/s | docs / sec |
| **Dataset C Median Latency (120 docs)** | **124.08 ms** | **370.60 ms** | 0.18 ms | ms / doc |
| **Dataset C Throughput** | **7.43 docs/s** (497.0 tok/s) | **2.64 docs/s** (247.6 tok/s) | 1,747.8 docs/s | docs / sec |
| **Long-Doc (~1000 tok, 3–4 windows)** | **2,125.5 ms** (2,123 ms/1k) | **7,592.2 ms** (7,082 ms/1k) | 1.64 ms | ms / doc |
| **Batch Helper Overhead** | N/A | N/A | **-8.59%** (6 reps) | % vs loop |

> **Tokenizer Token-Throughput Note:** PEYMA and TookaBERT use different tokenizers and produce different token counts for the same documents, so cross-backend `tokens/sec` is not a direct apples-to-apples speed comparison. For cross-backend comparisons, prefer median document latency, p95 document latency, docs/sec, and memory.

### Optimization Decision Gate
- **Decision:** `NO PRODUCTION OPTIMIZATION JUSTIFIED`.
- **Rationale:** No fa-redact-owned bottleneck was independently demonstrated, so the Phase 33 optimization eligibility gate was not satisfied. Production `src/fa_redact/**` remains strictly unmodified.

---

## 2. Privacy & Security Assurance

In accordance with Phase 33 security rules:
- **No Private Metadata:** Result artifacts contain zero hostnames, usernames, workstation paths, environment variables, or platform secrets.
- **No Raw Text or PII:** Zero raw text strings, snippets, gold labels, predictions, or PII hashes are written to committed JSON artifacts.
- **Allowed Environment Metadata Only:** Python version (`3.10.11`), OS platform family (`Windows 10`), CPU logical count (`8`), CPU architecture (`Intel64 AMD64`), package version (`0.3.0`), model identifiers and revisions, `max_length` (`512`), and ONNX execution provider (`CPUExecutionProvider`).

---

## 3. Benchmark Methodology & Measurement Details

### Warm-up & Repetitions
- **Warm-up:** 3 full warm-up iterations executed prior to timing data collection.
- **Repetitions:** 5 complete passes measured for NER workloads; 6 counterbalanced repetitions for batch processing.
- **Monotonic Timing:** Measured using high-resolution monotonic timer `time.perf_counter_ns()`.
- **Reported Aggregates:** Statistical median, 95th percentile (p95), and arithmetic mean computed across individual document passes and full corpus passes.

### Memory Profiling Across Lifecycle
- **Platform Measurement:** Process working set size (`WorkingSetSize`) and peak working set size (`PeakWorkingSetSize`) measured via Windows Win32 API (`K32GetProcessMemoryInfo` via standard library `ctypes`).
- **Lifecycle Measurement:** In isolated child processes, memory is recorded at baseline interpreter startup, post-model load, post-inference (after warm-up and representative long-document `VAL_LONG_1000` execution), and peak observed RSS across 3 repetitions.

---

## 4. Detailed Workload Analysis

### Workload A — Deterministic Core (`fa_redact.detect`)

Workload A evaluated production `detect()` using default detectors (`IR_NATIONAL_ID`, `IR_MOBILE`, `IR_IBAN`) with zero ML dependencies.

| Document Tier | Doc Count | Total Chars | Median Latency (ms) | p95 Latency (ms) | Throughput (docs/s) | Throughput (chars/s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Short (~100 chars)** | 10 | 870 | **0.0321 ms** (32.1 $\mu$s) | 0.0478 ms | **26,171.2** | 2,276,890.9 |
| **Medium (~1,000 chars)** | 10 | 7,300 | **0.1830 ms** (183.0 $\mu$s) | 0.2384 ms | **5,291.6** | 3,862,842.6 |
| **Long (~10,000 chars)** | 5 | 31,970 | **1.6441 ms** (1.64 ms) | 3.1687 ms | **534.7** | 3,419,141.6 |
| **Overall Corpus Aggregate** | 25 | 40,140 | **0.1817 ms** | 2.6331 ms | **1,747.8** | 2,806,188.4 |

> **Insight:** The pure-Python zero-dependency deterministic core achieved approximately 2.8 million characters/sec on the measured synthetic workload with full checksum validation, making it well-suited for high-throughput stream processing and high-volume batch workloads.

---

### Workloads B & C — Named Entity Recognition (PEYMA vs TookaBERT ONNX)

Evaluated steady-state inference on synthetic Challenge Sets B (150 general documents) and C (120 clinical-style documents).

#### Dataset B (150 Documents, 11,046 Chars)
- **PEYMA (`PersianNERDetector`):**
  - Median Latency: **69.56 ms**
  - p95 Latency: **133.68 ms**
  - Mean Latency: **82.60 ms**
  - Document Throughput: **12.50 docs/sec**
  - Token Throughput: **215.88 tokens/sec** (2,591 tokens)
- **TookaBERT ONNX (`ONNXPersianNERDetector`):**
  - Median Latency: **91.22 ms** (ONNX used ~1.31x PEYMA's median latency; ONNX median latency is ~31.1% higher than PEYMA)
  - p95 Latency: **232.12 ms**
  - Mean Latency: **108.12 ms**
  - Document Throughput: **9.61 docs/sec**
  - Token Throughput: **222.82 tokens/sec** (3,478 tokens)

#### Dataset C (120 Clinical Documents, 33,675 Chars)
- **PEYMA (`PersianNERDetector`):**
  - Median Latency: **124.08 ms**
  - p95 Latency: **180.72 ms**
  - Mean Latency: **133.60 ms**
  - Document Throughput: **7.43 docs/sec**
  - Token Throughput: **497.03 tokens/sec** (8,025 tokens)
- **TookaBERT ONNX (`ONNXPersianNERDetector`):**
  - Median Latency: **370.60 ms** (ONNX used ~2.99x PEYMA's median latency; ONNX median latency is ~198.7% higher than PEYMA)
  - p95 Latency: **590.21 ms**
  - Mean Latency: **390.00 ms**
  - Document Throughput: **2.64 docs/sec**
  - Token Throughput: **247.56 tokens/sec** (11,272 tokens)

> **Architectural Analysis:** TookaBERT is a 24-layer Transformer architecture (`tooka-bert-large`), whereas PEYMA is a 12-layer Transformer (`bert-fa-base`). On Dataset C (which features longer clinical sentences), TookaBERT ONNX required ~2.99x the median document latency of PEYMA under the measured environment.

---

### Workload D — Sliding-Window Long Document Scaling

Evaluated on 3 synthetic validation documents of increasing length (~250, ~550, and ~1000 tokens):

| Document | Actual Tokens (PEYMA / ONNX) | Windows (PEYMA / ONNX) | PEYMA Latency (ms) | ONNX Latency (ms) | PEYMA Cost (ms/1k tok) | ONNX Cost (ms/1k tok) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`VAL_LONG_256`** | 245 / 254 | 1 / 1 (Single) | **395.89 ms** | **1,026.40 ms** | 1,615.9 ms | 4,041.0 ms |
| **`VAL_LONG_512`** | 543 / 595 | 2 / 2 (Sliding) | **1,212.26 ms** | **3,705.97 ms** | 2,232.5 ms | 6,228.5 ms |
| **`VAL_LONG_1000`**| 1001 / 1072 | 3 / 4 (Sliding) | **2,125.51 ms** | **7,592.16 ms** | 2,123.4 ms | 7,082.2 ms |

---

### Workload E — Batch Processing Helper Overhead

Evaluated `fa_redact.detect_many(docs)` vs `[detect(d) for d in docs]` on 150 deterministic documents across 6 counterbalanced repetitions:
- **Explicit Python Loop Median:** **6.91 ms**
- **Lazy `detect_many()` Generator Median:** **6.32 ms**
- **Observed Difference:** **-8.59%**
- **Conclusion:** No material orchestration penalty was demonstrated on this synthetic benchmark.

---

## 5. Model Initialization & Memory Footprint Across Lifecycle

Measured in isolated subprocesses using platform working set counters across 3 repetitions:

| Metric | PEYMA PyTorch | TookaBERT ONNX | Difference |
| :--- | :--- | :--- | :--- |
| **Cold Constructor Time** | **6,412.9 ms** (~6.4s) | **7,768.9 ms** (~7.8s) | ONNX takes +21.1% longer |
| **Baseline Interpreter RSS**| 19.32 MiB | 19.28 MiB | — |
| **Post-Load RSS** | **348.04 MiB** | **728.85 MiB** | ONNX consumes +380.8 MiB |
| **Post-Inference RSS** | **714.75 MiB** | **885.00 MiB** | ONNX consumes +170.2 MiB |
| **Peak Resident Memory (RSS)**| **714.76 MiB** | **887.91 MiB** | ONNX is 1.24x larger |
| **Model Load Delta** | **328.71 MiB** | **709.57 MiB** | ONNX load delta is 2.16x larger |
| **Inference Delta from Post-Load** | **366.71 MiB** | **156.16 MiB** | PEYMA post-inference RSS increased by 366.71 MiB from post-load |

---

## 6. Performance Recommendation Rubric

According to the Phase 33 recommendation rubric, ONNX TookaBERT would be recommended as the CPU-performance winner only if:
1. Median latency is $\ge 20\%$ lower (or throughput is $\ge 25\%$ higher) on Dataset B. *(Result: Not passed, ONNX latency is 31.1% higher)*
2. Median latency is $\ge 20\%$ lower (or throughput is $\ge 25\%$ higher) on Dataset C. *(Result: Not passed, ONNX latency is 198.7% higher)*
3. Peak RSS is $\le 1.25\times$ PEYMA peak RSS. *(Result: Passed, ratio is 1.24x)*

### Rubric Outcome: `NO UNIVERSAL CPU PERFORMANCE WINNER`

### Official Deployment Recommendations:
- **On the measured Windows CPU environment and synthetic workloads, PEYMA had lower document latency and lower measured process memory than the TookaBERT ONNX backend.**
- **Reference PERSON NER Quality & CPU Speed:** Recommend **PEYMA (`PersianNERDetector`, `fa-redact[ner]`)**. It delivers validated 1.0000 precision/recall across challenge benchmarks, lower document latency on CPU, and lower peak resident memory than TookaBERT-large.
- **Lightweight High-Throughput Direct Identifiers:** Recommend **Deterministic Core (`fa_redact.detect()`)**. Operates with zero external dependencies (`dependencies = []`), no model initialization requirement, and throughput $>1,700\text{ to }26,000\text{ docs/sec}$.
- **ONNX-Only Deployment Environments:** Recommend **`ONNXPersianNERDetector` (`fa-redact[onnx]`)** when runtime constraints require ONNX Runtime without installing PyTorch.

---

## 7. Evidence-Based Optimization Decision

Under the Phase 33 optimization eligibility gate, production code changes in `src/fa_redact/` require:
1. Identification of an `fa-redact`-owned Python bottleneck.
2. The bottleneck accounting for a meaningful portion of measured execution time.
3. A local, semantics-preserving fix yielding $\ge 10\%$ target improvement with $\le 5\%$ collateral regression.
4. Exact output equality `(start, end, type)` on all benchmark documents.

**Conclusion:** `NO PRODUCTION OPTIMIZATION JUSTIFIED`. No fa-redact-owned bottleneck was independently demonstrated, so the Phase 33 optimization eligibility gate was not satisfied. The Phase 33 deliverables remain strictly research, profiling, and test code, preserving 100% architectural stability for the upcoming v0.4.0 release.
