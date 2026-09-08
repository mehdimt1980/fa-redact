# Phase 32 — Persian NER Backend Validation & Production Readiness Gate

**Date:** 2026-09-08  
**Status:** VALIDATION GATE COMPLETED — **OVERALL DECISION: PASS**  
**Repository:** `mehdimt1980/fa-redact`  
**Base Commit:** `bebf8b1e4795f60e653a8e4ea7cadf3ae7ffa141`

---

## 1. Executive Summary

Phase 32 establishes an independent validation gate for the **two production PERSON backends** in `fa-redact`:
1. `fa_redact.PersianNERDetector` (PEYMA-compatible transformers backend)
2. `fa_redact.ONNXPersianNERDetector` (generic local ONNX backend evaluated against the TookaBERT INT4 candidate)

This phase answers the critical production readiness questions:
- **Did production behavior regress relative to Phase 29?** PEYMA matched its Phase 29 PERSON reference results. The production ONNX backend met the locked gate and scored above the Phase 29 wrapper reference on Dataset B while matching Dataset C.
- **Are exact source offsets still correct?** Yes. Both backends achieved **0 offset failures** across all benchmark runs, sliding-window chunk boundaries, and normalization variants.
- **Are both backends deterministic?** Yes. 100% of tested documents yielded identical prediction tuples `(start, end, type)` across 3 independent runs.
- **Do both safely handle long documents?** Yes. Both backends safely processed synthetic documents across sliding-window boundaries, detecting 100% of planted synthetic PERSON entities with zero offset failures, bounded model input lengths (<= 512 tokens), and verified multi-chunk inference execution.
- **Is either backend exhibiting meaningful over-redaction?** On negative control documents in Dataset B, PEYMA achieved a 0.0% false-positive rate, while ONNX achieved a 1.67% negative-document false-positive rate (2 documents out of 120). Negative-document false-positive rate on Dataset C: N/A (no PERSON-negative documents in Dataset C; total PERSON false positives across Dataset C: 0).

**Overall Gate Decision: PASS.**

---

## 2. Evaluated Production Backends & Model Identities

Both backends were evaluated using their actual production classes from `fa_redact.detectors`, strictly offline from local pinned cache snapshots with zero network access:

| Backend Key | Production Class | Model Repository / Artifact | Pinned Revision | License |
| :--- | :--- | :--- | :--- | :--- |
| **PEYMA** | `fa_redact.PersianNERDetector` | `HooshvareLab/bert-fa-base-uncased-ner-peyma` | `8b7b63371aa8f1fdad62c0f82d462a22b91b37ab` | Apache-2.0 |
| **ONNX** | `fa_redact.ONNXPersianNERDetector` | `Reza2kn/openmed-persian-pii-tookabert-large-onnx-int4` | `27dc2a6eacea263ae325dcb18e6751cfabbbfe74` | CC-BY-4.0 |

---

## 3. Benchmark Datasets & Locked Reference Baselines

Evaluation was performed exclusively on the standard synthetic challenge sets from `research/phase29_challenge_set.py` focusing strictly on exact character-span `PERSON` entities:
- **Dataset B (Independent Persian Challenge):** 150 documents, 30 gold PERSON entities, 120 negative control documents.
- **Dataset C (Iranian Clinical Challenge):** 120 documents, 255 gold PERSON entities.

### Pre-Declared Locked Phase 29 Baselines

| Backend | Dataset B Precision | Dataset B Recall | Dataset B F1 | Dataset C Precision | Dataset C Recall | Dataset C F1 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **PEYMA Reference** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| **TookaBERT Phase 29 Wrapper** | 0.8438 | 0.9000 | 0.8710 | 1.0000 | 1.0000 | 1.0000 |

---

## 4. Locked Quality & Integrity Gates

Thresholds were pre-declared prior to benchmark execution and strictly locked:

| Quality Gate | Dataset B Threshold | Dataset C Threshold | Outcome |
| :--- | :--- | :--- | :---: |
| **PEYMA Gate** | Precision >= 0.98, Recall >= 0.98, F1 >= 0.98 | Precision >= 0.98, Recall >= 0.98, F1 >= 0.98 | **PASS** |
| **ONNX Gate** | Precision >= 0.81, Recall >= 0.87, F1 >= 0.84 | Precision >= 0.97, Recall >= 0.97, F1 >= 0.97 | **PASS** |

### Mandatory Integrity Gates

1. **Offset Integrity:** `offset_failures == 0` (for all predictions, `0 <= start < end <= len(text)` and `text[start:end] == d.value`).
2. **Runtime Errors:** `adapter_error_count == 0` across all datasets.
3. **Determinism:** `is_deterministic == True` across 3 independent runs on 24 sample documents and all long documents.
4. **Long-Document Production Handling:** 100% detection of planted PERSON entities in long synthetic documents with verified multi-chunk sliding-window execution, bounded model input sequence lengths (`<= max_length`), valid offsets, and zero uncaught exceptions.

---

## 5. Empirical Validation Results

### A. Dataset B (Independent Persian Challenge — 150 Documents, 30 Gold PERSON)

| Evaluated System | Precision | Recall | F1 | TP | FP | FN | Leakage Rate | Offset Failures | Adapter Errors | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **PersianNERDetector (PEYMA)** | **1.0000** | **1.0000** | **1.0000** | 30 | 0 | 0 | **0.0000** | **0** | **0** | **PASS** |
| **ONNXPersianNERDetector (TookaBERT)** | **0.8485** | **0.9333** | **0.8889** | 28 | 5 | 2 | **0.0667** | **0** | **0** | **PASS** |

*Note on ONNX Dataset B:* The production ONNX backend produced a higher Dataset B F1 than the Phase 29 research wrapper reference (0.8889 vs. 0.8710). The implementations/post-processing paths differ, so Phase 32 does not attribute the difference to a single cause.

### B. Dataset C (Iranian Clinical Challenge — 120 Documents, 255 Gold PERSON)

| Evaluated System | Precision | Recall | F1 | TP | FP | FN | Leakage Rate | Offset Failures | Adapter Errors | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **PersianNERDetector (PEYMA)** | **1.0000** | **1.0000** | **1.0000** | 255 | 0 | 0 | **0.0000** | **0** | **0** | **PASS** |
| **ONNXPersianNERDetector (TookaBERT)** | **1.0000** | **1.0000** | **1.0000** | 255 | 0 | 0 | **0.0000** | **0** | **0** | **PASS** |

Both backends detected 100% of patient and physician personal names without a single false positive or leakage incident.

---

## 6. Over-Redaction / False-Positive Analysis

Analysis of negative control documents:

| Backend | Dataset B Negative Docs | Neg Docs with FP | Neg Doc FP Rate | Total FP in Neg Docs | Dataset C Negative Docs | Neg Docs with FP | Dataset C Neg Doc FP Rate | Total FP in Dataset C |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **PEYMA** | 120 | 0 | **0.0000** (0.0%) | 0 | 0 | 0 | **N/A** | 0 |
| **ONNX** | 120 | 2 | **0.0167** (1.67%) | 2 | 0 | 0 | **N/A** | 0 |

- **PEYMA:** Zero over-redaction observed on general text, weather reports, stock market updates, and non-PII numerical records.
- **ONNX:** Exhibits mild over-redaction on 2 of 120 negative documents in out-of-distribution texts, fully within the pre-declared quality tolerance gate (Precision >= 0.81).
- **Dataset C:** Negative-document false-positive rate: N/A (no PERSON-negative documents in Dataset C). Total PERSON false positives across Dataset C: 0.

---

## 7. Long-Document & Sliding-Window Validation

Evaluated on 3 deterministic fully synthetic clinical progress notes using real tokenizer token counts:

### Long-Document Fixture & Execution Characteristics

| Document ID | Whitespace Word Count | PEYMA Token Count | ONNX Token Count | Configured Max Length | Requires Sliding Window | Planted Gold PERSON |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **VAL_LONG_256** | 207 | 245 | 254 | 512 | No | 4 |
| **VAL_LONG_512** | 478 | 543 | 595 | 512 | Yes | 5 |
| **VAL_LONG_1000** | 895 | 1,001 | 1,072 | 512 | Yes | 7 |

### Empirical Verification Evidence

| Backend | Doc ID | Inference Calls | Max Model Input | Deterministic | Planted Detected | Offset Failures | Gate Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **PEYMA** | VAL_LONG_256 | 1 | 245 | Yes | 4 / 4 | 0 | **PASS** |
| **PEYMA** | VAL_LONG_512 | 2 | 512 | Yes | 5 / 5 | 0 | **PASS** |
| **PEYMA** | VAL_LONG_1000 | 3 | 512 | Yes | 7 / 7 | 0 | **PASS** |
| **ONNX** | VAL_LONG_256 | 1 | 254 | Yes | 4 / 4 | 0 | **PASS** |
| **ONNX** | VAL_LONG_512 | 2 | 512 | Yes | 5 / 5 | 0 | **PASS** |
| **ONNX** | VAL_LONG_1000 | 4 | 512 | Yes | 7 / 7 | 0 | **PASS** |

Both backends satisfied all six mandatory long-document criteria:
1. Exact planted PERSON recall (16 / 16 across all fixtures).
2. Zero offset failures (`0 <= start < end <= len(text)` and `text[start:end] == d.value`).
3. Zero backend errors or exceptions.
4. Deterministic ordered `(start, end, type)` output across 3 repeated runs.
5. Documents whose `full_token_count > max_length` executed multiple inference calls (`calls > 1`).
6. Every observed model/session input length was `<= configured_max_length` (512 tokens).

---

## 8. Normalization & Offset Preservation Cases

Targeted validation cases evaluated position-preserving normalization and exact offset mapping:
- **Arabic Yeh (`ي` vs `ی`):** Exact source character offsets preserved without drift.
- **Arabic Kaf (`ك` vs `ک`):** Exact source character offsets preserved without drift.
- **ZWNJ inside PERSON (`\u200c` in `"سید‌علی"`):** Internal ZWNJ preserved in detected span.
- **Surrounding Whitespace:** Leading and trailing Unicode whitespace properly trimmed while preserving original slice alignment.

Both backends passed 4 of 4 targeted normalization cases with 0 offset failures.

---

## 9. Gate Summary & Verdict

| Gate Criterion | Target / Constraint | Result | Verdict |
| :--- | :--- | :---: | :---: |
| 1. PEYMA Dataset B Quality Gate | Precision >= 0.98, Recall >= 0.98, F1 >= 0.98 | P: 1.0000, R: 1.0000, F1: 1.0000 | **PASS** |
| 2. PEYMA Dataset C Quality Gate | Precision >= 0.98, Recall >= 0.98, F1 >= 0.98 | P: 1.0000, R: 1.0000, F1: 1.0000 | **PASS** |
| 3. ONNX Dataset B Quality Gate | Precision >= 0.81, Recall >= 0.87, F1 >= 0.84 | P: 0.8485, R: 0.9333, F1: 0.8889 | **PASS** |
| 4. ONNX Dataset C Quality Gate | Precision >= 0.97, Recall >= 0.97, F1 >= 0.97 | P: 1.0000, R: 1.0000, F1: 1.0000 | **PASS** |
| 5. Offset Integrity Gate | `offset_failures == 0` | 0 failures (both backends) | **PASS** |
| 6. Runtime Reliability Gate | `adapter_error_count == 0` | 0 errors (both backends) | **PASS** |
| 7. Determinism Gate | 100% reproducible across 3 runs | 24 / 24 docs + 3 / 3 long docs identical | **PASS** |
| 8. Long-Document Gate | 100% planted entity recall, bounded tokens, verified calls | 16 / 16 planted entities detected | **PASS** |
| **OVERALL GATE DECISION** | **All 8 gates must PASS** | **8 / 8 Gates Passed** | **PASS** |

---

## 10. Production Guidance & Recommendations

Based on Phase 32 validation findings:
1. **Reference Backend:** `PersianNERDetector` (PEYMA) remains the validated reference PERSON backend for `fa-redact`.
2. **Optional Alternative Backend:** `ONNXPersianNERDetector` (TookaBERT ONNX candidate) is a validated optional alternative for environments requiring ONNX Runtime execution.
3. **Runtime & Performance Recommendations:** Formal throughput, latency, and memory profiling will be conducted in **Phase 33 (Performance Profiling & Optimization)** before formulating final deployment recommendations in README and release notes.
