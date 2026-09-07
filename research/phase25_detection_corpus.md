# Phase 25 — Synthetic Benchmark & Evaluation Corpus Tooling

## Executive Summary

Phase 25 establishes an offline, deterministic, standard-library-only synthetic regression corpus and evaluation runner for `fa-redact`'s detection capabilities.

This tooling answers the foundational regression question:
> *"Given a controlled synthetic corpus with exact gold entity spans, does the current detector configuration emit the expected entity types and exact source offsets without spurious false positives or missed entities?"*

All tooling is strictly quarantined within the `research/` package. It introduces **zero runtime changes**, adds **zero dependencies**, requires **no machine learning frameworks or model downloads**, and operates **100% offline**.

---

## Privacy & Safety Boundary

> [!CAUTION]
> ### 100% Artificial Synthetic Corpus Notice
> - **Zero Real Patient Data:** No hospital notes, clinical summaries, or medical histories were used.
> - **Zero Real Customer Data:** No actual personal records, phone directories, or CRM profiles were used.
> - **Zero Leaked / Scraped Data:** All identifiers and prose were artificially constructed.
> - **Value-Free Evaluation Output:** Serialized benchmark results contain aggregate metadata and counts only; source text, detected values, normalized values, and snippets are never persisted.

---

## Architecture & Existing Harness Reuse

Phase 25 builds directly upon the exact-span evaluation primitives established in Phase 21 (`research/evaluation.py`):
- `EntitySpan`: Immutable entity span representation `(start, end, type)`.
- `ExactSpanMetrics`: Micro-averaged true positive, false positive, false negative, precision, recall, and F1 calculations.
- `CorpusEvaluationResult`: Aggregate corpus metrics broken down overall and per-type.
- `evaluate_exact_spans()` & `evaluate_corpus()`: 1-to-1 exact span matching under strict duplicate prediction policies.

No competing precision/recall/F1 implementation was introduced. The existing Phase 21 PERSON-oriented synthetic challenge fixtures (`research/synthetic_fixtures.py`) remain completely separate and unmodified.

---

## Corpus Design & Suites

The synthetic detection corpus (`SYNTHETIC_DETECTION_CORPUS` in `research/detection_corpus.py`) comprises **62 curated synthetic documents** organized into four detector suites:

### 1. Default Suite (`suite="default"`)
Evaluated against `detect(text, detectors=None)`:
- **`IR_NATIONAL_ID`**:
  - Positive: ASCII 10-digit modulo-11 valid numbers, leading-zero representations, Persian digits (`۰-۹`), Arabic-Indic digits (`٠-٩`), colon/prose boundaries.
  - Negative Controls: Modulo-11 checksum corruptions, 10-digit repeated numbers (`1111111111`), invalid lengths (9-digit, 11-digit), ordinary transactional numbers.
- **`IR_MOBILE`**:
  - Positive: Domestic numbers across all 2026 CRA National Numbering Plan NDC prefix families (MCI `0912`, `0990`, `0991`; MTN Irancell `0935`, `0902`; RighTel `0921`; Shatel Mobile `0998`).
  - Script Variants: Persian Unicode digits (`۰۹۱۲...`), Arabic-Indic digits (`٠٩١٢...`).
  - Negative Controls: Unallocated CRA prefixes (`0950`), malformed lengths (10-digit, 12-digit), landline phone numbers (`021...`), non-09 tracking numbers.
- **`IR_IBAN`**:
  - Positive: 26-character MOD-97 valid Iranian IBANs in ASCII (`IR...`), Persian digits, and Arabic-Indic digits.
  - Negative Controls: MOD-97 checksum corruptions, foreign IBANs (`DE...`), truncated sequences (25 chars), alphanumeric characters in numeric BBAN.
- **`mixed_default`**:
  - Documents combining National IDs, Mobile numbers, and IBANs in mixed scripts, repeated mobile numbers in separate sentences, adjacent identifiers, and multi-ID documents.

### 2. Email Suite (`suite="email"`)
Evaluated against `detect(text, detectors=[EmailDetector()])`:
- **Positive**: Simple ASCII mailboxes, multi-level subdomains, plus-addressing (`user+tag@...`), country-code TLDs (`.co.ir`), and surrounding boundary punctuation (double quotes, parentheses, square brackets).
- **Negative Controls**: Missing `@` symbol, consecutive dots (`..`), missing TLD, non-ASCII Persian username characters.

### 3. Bank Card Suite (`suite="bank_card"`)
Evaluated against `detect(text, detectors=[BankCardDetector()])`:
- **Positive**: 16-digit payment card numbers satisfying the Luhn MOD-10 checksum across ASCII, Persian digits, Arabic-Indic digits, and bracketed contexts.
- **Negative Controls**: Luhn check digit corruptions, 16 identical digits (`1111111111111111`), 15-digit sequences.

### 4. Institutional Pattern Suite (`suite="pattern"`)
Evaluated against `detect(text, detectors=[PatternDetector(SYNTHETIC_PATTERN_RULES)])`:
- **Synthetic Pattern Rules**:
  - `MRN`: `\bMRN-[0-9]{6}\b`
  - `PATIENT_ID`: `\bPAT-[0-9]{6}\b`
  - `ENCOUNTER_ID`: `پرونده:\s*([0-9]{5})` (contextual capture group 1)
- **Positive**: Exact regex matches for `MRN` and `PATIENT_ID`, contextual extraction for `ENCOUNTER_ID`, multi-rule documents.
- **Normalized Digits**: Persian and Arabic-Indic digits matched via position-preserving normalized streams.
- **Negative Controls**: Unmatched prefixes (`ACC-...`), invalid number lengths, missing contextual prefix.

---

## Safe Substring Span-Builder

To eliminate fragile manual offset bookkeeping in synthetic annotations, the private research helper `_span_for` calculates exact character offsets directly from the source text:

```python
_span_for(text, substring, entity_type, *, occurrence=1) -> EntitySpan
```
- Locates the 1-indexed occurrence of `substring` in `text`.
- Computes `(start, start + len(substring))` character slice bounds.
- Fails loudly with `ValueError` if `occurrence < 1` or if the requested occurrence does not exist.
- Never mutates or normalizes the source text.

---

## Exact-Span Evaluation Standards

1. **Strict Exact Matching:** A prediction is a True Positive (TP) if and only if `(start, end, type)` matches a gold entity span identically.
2. **Boundary Sensitivity:** Substring overlaps, partial matches, or single-character boundary shifts count as False Positives (FP) and False Negatives (FN). Token-level relaxed matching is not permitted.
3. **Duplicate Prediction Policy:** Evaluated under `duplicate_prediction_policy="count_as_fp"`. The first emission matching gold is a TP; any redundant duplicate emission of the same span counts as an FP.
4. **Failed Case Identification:** Any case with `false_positives > 0` or `false_negatives > 0` is recorded in `failed_case_ids`.

---

## Observed Benchmark Results

Executed against `SYNTHETIC_DETECTION_CORPUS` (62 cases, 54 gold entities):

| Metric / Category | Cases | Gold Spans | Predicted Spans | TP | FP | FN | Precision | Recall | F1 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Overall** | **62** | **54** | **54** | **54** | **0** | **0** | **1.0000** | **1.0000** | **1.0000** |
| `IR_NATIONAL_ID` | — | 12 | 12 | 12 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `IR_MOBILE` | — | 16 | 16 | 16 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `IR_IBAN` | — | 7 | 7 | 7 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `EMAIL` | — | 7 | 7 | 7 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `BANK_CARD` | — | 5 | 5 | 5 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `MRN` | — | 2 | 2 | 2 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `PATIENT_ID` | — | 2 | 2 | 2 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| `ENCOUNTER_ID` | — | 3 | 3 | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |

### Failed Cases
- `failed_case_ids: []` (0 failed cases)

---

## Value-Free Machine-Readable JSON Schema

The benchmark runner outputs deterministic JSON (`research/results/phase25_detection_corpus.json`) adhering to schema version `1.0.0`:

```json
{
  "by_category": { ... },
  "by_type": { ... },
  "case_count": 62,
  "failed_case_ids": [],
  "generated_by": "fa-redact synthetic detection corpus benchmark runner",
  "gold_entity_count": 54,
  "overall": {
    "f1": 1.0,
    "false_negatives": 0,
    "false_positives": 0,
    "precision": 1.0,
    "recall": 1.0,
    "total_gold": 54,
    "total_predicted": 54,
    "true_positives": 54
  },
  "prediction_count": 54,
  "schema_version": "1.0.0"
}
```

---

## Limitations & Explicit Anti-Claims

> [!IMPORTANT]
> ### What This Synthetic Benchmark Does NOT Measure
> A perfect score (Precision=1.0, Recall=1.0, F1=1.0) on this synthetic regression corpus proves **only** that `fa-redact`'s current detector implementation matches these curated synthetic expectations.
>
> It does **NOT** measure, estimate, or guarantee:
> 1. **Clinical Sensitivity / Specificity:** Real clinical notes contain spelling errors, non-standard abbreviations, broken OCR, and unmodeled medical identifier schemas.
> 2. **Population Precision:** Real-world false positive rates in dense numeric contexts (e.g. laboratory values, doses, financial records) are not reflected in curated fixtures.
> 3. **Unseen Persian Text Accuracy:** Free-text variations and linguistic edge cases outside the synthetic corpus are not covered.
> 4. **Regulatory Compliance:** Automated redaction of synthetic identifiers does not imply GDPR, HIPAA, or Iranian data protection certification.

---

## How to Rerun

Run the offline benchmark and output the JSON report:
```bash
python -m research.detection_corpus_benchmark --output research/results/phase25_detection_corpus.json --check
```

Run the unit tests:
```bash
python -m pytest tests/test_detection_corpus.py
```
