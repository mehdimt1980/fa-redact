# Phase 21.1 — Persian NER Empirical Benchmark & Prototype Report

> **Authoritative Phase Deliverable**
>
> **Project:** `fa-redact`
> **Phase:** 21.1 — Persian NER Empirical Benchmark & Prototype
> **Date:** September 2026
> **Status:** Completed Research Deliverable

---

## 1. Objective

Phase 21 established the mathematical evaluation foundation, licensing assessment, error taxonomy, and synthetic challenge fixture suite for Persian Named Entity Recognition (NER), but explicitly deferred executing real machine learning model checkpoints against real held-out evaluation corpora.

The primary objective of **Phase 21.1** is to execute a real, reproducible, empirical exact-span `PERSON` benchmark on a held-out Persian corpus using a candidate model with verified permissive licensing, quantify exact character offset fidelity without text distortion, perform reproducible aggregate error analysis, maintain the zero-dependency runtime guarantee for core `fa-redact`, and provide an evidence-based recommendation for future implementation phases.

---

## 2. Phase 21 Decision Context

Phase 21 concluded with a **CONDITIONAL GO ONLY FOR A DEDICATED EMPIRICAL BENCHMARK / PROTOTYPE SUB-PHASE** (Section 15 of `research/phase21_persian_ner.md`). It established four binding requirements for subsequent work:
1. **Zero-Dependency Core Invariant:** Mandatory base runtime dependencies must remain `dependencies = []`. Any ML frameworks or tokenizers must remain research-only or future optional extras.
2. **Exact-Span Offset Evaluation:** All metrics must be computed strictly at the entity level requiring exact triple equality `(start, end, type)` against unmodified source character slices. Token-level accuracy was rejected as misleading.
3. **Conservative Licensing Assessment:** Models and corpora must have their provenance, licenses, and redistribution terms clearly documented and distinguished.
4. **Separation of Concerns:** Model/dataset acquisition must be separated from inference, and inference must operate 100% offline.

---

## 3. Selected Model(s)

The primary candidate evaluated in this phase is:
- **Model Identifier:** `HooshvareLab/bert-fa-base-uncased-ner-peyma`
- **Architecture:** 12-layer Transformer (BERT-base architecture, ParsBERT Persian pre-training, 110M parameters, fine-tuned for token classification on PEYMA).
- **Framework:** PyTorch / Hugging Face Transformers.
- **Output Labels:** 15 token classes representing 7 entity categories in BIO format (`B_DAT`, `B_LOC`, `B_MON`, `B_ORG`, `B_PCT`, `B_PER`, `B_TIM`, `I_DAT`, `I_LOC`, `I_MON`, `I_ORG`, `I_PCT`, `I_PER`, `I_TIM`, `O`).
- **Runtime Validation:** The benchmark runner dynamically queries `model.config.id2label` at startup and verifies the presence of required `B_PER` and `I_PER` target classes.

---

## 4. Model License Verification

- **Stated License:** **Apache-2.0**
- **Verification Evidence:**
  - Hugging Face repository metadata tags: `license:apache-2.0`
  - Model Card README explicitly declares Apache-2.0 terms.
  - Base foundation model (`HooshvareLab/bert-fa-base-uncased`) is licensed under Apache-2.0 (Farahani et al., 2021).
- **Redistribution & Packaging Assessment:** Permissive Apache-2.0 license allows local downloading, execution, and potential optional extra integration by end users. Model weights will not be vendored in the core package wheel.

---

## 5. Dataset Selection & Provenance

The benchmark evaluated the held-out test split from the pinned community redistribution:
- **Dataset Identifier:** `ParsiAI/PEYMA` (community Hugging Face mirror)
- **Original Dataset & Publication:** Shahshahani, M. S., Mohseni, M., Shakery, A., & Faili, H. (2018). *PEYMA: A Tagged Corpus for Persian Named Entities*. Laboratory for Systems and Cognitive Processing (LSCP), University of Tehran.
- **Evaluated Redistribution:** `https://huggingface.co/datasets/ParsiAI/PEYMA` at revision `c9995786945706010f000d4196b0a9ecbd6b96c5`.
- **Evaluated File:** `data/test.txt` (SHA-256: `59a5f7f2bc2f6d89965a8b832a371293df23976eb7552a41916976d3a7dd7c96`).
- **Domain:** Persian news prose from major news agencies.
- **Selected Split:** **`test` split**, comprising 1,026 sentences and 434 human-annotated gold `PERSON` entities.

---

## 6. Dataset Terms / Licensing Nuances

A strict legal and provenance distinction is maintained:
1. **Original Author Terms:** The original authors (Shahshahani et al., 2018; University of Tehran LSCP Lab) released the PEYMA corpus freely for academic and research evaluation purposes.
2. **Mirror Metadata:** The community repository `ParsiAI/PEYMA` declares `license: apache-2.0` in its Hugging Face metadata.
3. **License Authority:** The mirror maintainer's legal authority to relicense the underlying PEYMA corpus under Apache-2.0 has not been independently established.
4. **Benchmark Usage:** The corpus is used strictly for offline research evaluation.
5. **Redistribution / Commercial / Package Integration:** Package redistribution rights are not established by mirror metadata alone and **require separate verification**. Corpus files are strictly excluded from the `fa-redact` Git repository and Python packages.

---

## 7. Investigation of the 7,145 vs 9,979 Example Count

An analysis was conducted regarding the discrepancy between canonical descriptions and mirror metadata:
- **Canonical PEYMA Description:** HooshvareLab ParsBERT documentation and original papers describe PEYMA as containing **7,145 sentences** and 302,530 tokens.
- **ParsiAI Metadata Description:** The Hugging Face dataset card for `ParsiAI/PEYMA` reports:
  - `train`: 8,028 examples
  - `test`: 1,026 examples
  - `validation`: 925 examples
  - Total: **9,979 examples**
- **Findings:**
  - In the pinned CoNLL file `data/test.txt`, sentences are demarcated by empty lines, totaling exactly 1,026 sentences and 33,202 tokens.
  - The reason for the 7,145-vs-9,979 discrepancy was not established in Phase 21.1.
  - *Hypotheses (unproven):* Possible explanations include different preprocessing, sentence segmentation, split construction, or mirror metadata differences.
  - Therefore, this benchmark scope remains strictly designated as an **"evaluation on the pinned ParsiAI/PEYMA test redistribution"** (1,026 sentences) rather than a proven identical reproduction of the 2018 canonical split.

---

## 8. Independent Provenance Sanity Check

An independent Persian NLP benchmark (Mofid-AI Persian NLP evaluation suite) evaluated on its PEYMA test split reports:
- **Test sentences:** 1,026
- **Entity occurrences:** $B\_\text{PER} = 434$, $I\_\text{PER} = 297$

The Phase 21.1 evaluated test file similarly contains:
- **Test sentences:** 1,026
- **Gold PERSON entities:** 434 (with 297 $I\_\text{PER}$ continuations)

This provides evidence that the pinned `ParsiAI/PEYMA` test split is strongly consistent with a commonly used PEYMA test split based on matching sentence and PERSON-tag counts. Matching aggregate counts do not prove byte-for-byte corpus identity.

---

## 9. Immutable Revisions

All evaluated assets are pinned to immutable commit hashes:
- **Model Checkpoint:** `HooshvareLab/bert-fa-base-uncased-ner-peyma`
  - **Commit SHA:** `8b7b63371aa8f1fdad62c0f82d462a22b91b37ab`
  - *Note:* Commit `8b7b633` represents a subsequent repository state that uploaded Flax weights while retaining the PyTorch checkpoint (`pytorch_model.bin`) introduced in earlier commits.
- **Dataset Repository:** `ParsiAI/PEYMA`
  - **Commit SHA:** `c9995786945706010f000d4196b0a9ecbd6b96c5`
  - **Test File SHA-256:** `59a5f7f2bc2f6d89965a8b832a371293df23976eb7552a41916976d3a7dd7c96`

---

## 10. Environment

The empirical benchmark was executed under the following environment:
- **Operating System / Platform:** `Windows-10-10.0.26200-SP0` x86_64
- **Python Version:** `3.10.11`
- **PyTorch Version:** `2.7.0+cpu`
- **Transformers Version:** `4.49.0`
- **Tokenizers Version:** `0.21.1`
- **Core Package Runtime Dependencies:** `[]` (unmodified zero-dependency guarantee)

*Note on cross-version testing:* Pure benchmark utilities pass CI across Python 3.10–3.13. The real model benchmark was executed on Python 3.10.11 only.

---

## 11. Acquisition Procedure

The acquisition phase was executed as an explicit setup step completely separate from inference:
1. The pinned PEYMA test corpus (`data/test.txt`) was retrieved from Hugging Face via HTTPS and cached in `~/.cache/fa_redact_research/peyma_test.txt`.
2. The pinned model weights were cached in `~/.cache/huggingface/hub/models--HooshvareLab--bert-fa-base-uncased-ner-peyma/`.
3. No dataset or model files were placed in or committed to the repository working tree.

---

## 12. Offline Inference Procedure

Inference-time local execution was configured as follows:
- The environment variable `HF_HUB_OFFLINE=1` was set during execution.
- The benchmark runner uses `local_files_only=True` and contains no explicit inference-time network request path.
- The model operated in `eval()` mode with `torch.no_grad()`.

---

## 13. Gold Annotation Conversion & Offset Scope

The PEYMA test split is distributed in CoNLL format (`token|tag` lines separated by blank lines).
1. **Canonical Evaluation String Reconstruction:** Tokens are joined with single spaces:
   $$\text{reconstructed\_text} = \text{" ".join}(\text{tokens})$$
2. **Offset Tracking:** Each token is mapped to Unicode code-point character start/end offsets in `reconstructed_text`.
3. **Gold Span Assembly:** Contiguous sequences tagged with `B_PER` / `I_PER` are assembled into exact `EntitySpan(start, end, type="PERSON")` objects using strict BIO parsing.
4. **Scope Note:** All reported character offsets represent exact spans on the deterministically reconstructed PEYMA evaluation string (`" ".join(tokens)`), rather than byte-for-byte positions in original raw news feeds.

---

## 14. Token/Subword-to-Span Mapping & Structural Fast-Tokenizer Offset Audit

The benchmark runner implements strict subword-to-span mapping and a structural fast-tokenizer offset audit:
1. Fast tokenizer extracts character offsets using `return_offsets_mapping=True`.
2. Special tokens (`[CLS]`, `[SEP]`, padding) with `(0, 0)` offsets are filtered.
3. Every non-special token offset is checked for:
   - Bounds validity: $0 \le \text{start} \le \text{end} \le \text{len}(\text{text})$
   - Monotonicity: $\text{start} \ge \text{previous\_end}$
   - Character slice validity: $\text{text}[\text{start}:\text{end}]$ matches expected non-empty length.
4. `B_PER` triggers a new active entity span `[start, end]`.
5. Subsequent `I_PER` subwords extend `end = token_offset[1]`.
6. Leading `I_PER` tokens without preceding `B_PER` are counted and recovered.
7. `O` or non-PERSON tags close active spans.

---

## 15. Truncation & Structural Offset Audit Results

- **Basic Offset Validation Failures:** **0** (verifies non-empty string slices within text bounds)
- **Tokenizer Alignment Failures:** **0** (verifies monotonic, non-overlapping subword offset sequences; zero structural offset violations observed)
- **Maximum Tokenized Sequence Length:** **153 tokens** (well below the 512 max length limit)
- **Truncated Sentences:** **0** (100% of corpus tokens were presented to the model without truncation)
- **Leading-I Recoveries:** **0**
- **Duplicate Predictions:** **0** (measured by counting exact $(s, e, t)$ duplicate predictions per sentence)

---

## 16. Evaluation Methodology

Evaluation followed the exact-span mathematical framework implemented in `research/evaluation.py`:
- **Matching Criterion:** Predicted entity $P = (s_p, e_p, t_p)$ matches Gold entity $G = (s_g, e_g, t_g)$ if and only if $s_p = s_g \land e_p = e_g \land t_p = t_g$.
- **Boundary Mismatch:** 1 False Positive + 1 False Negative (zero partial credit).
- **Type Mismatch:** 1 False Positive + 1 False Negative.
- **Corpus Aggregation:** Micro-averaged across all 1,026 sentences.

---

## 17. Reproduced Metrics

The empirical benchmark produced the following exact results on the held-out PEYMA test split:

| Metric Category | Value |
| :--- | :--- |
| **Evaluated Sentences** | **1,026** |
| **Gold PERSON Entities** | **434** |
| **Predicted PERSON Entities** | **433** |
| **True Positives (TP)** | **430** |
| **False Positives (FP)** | **3** |
| **False Negatives (FN)** | **4** |
| **Exact-Span Precision** | **0.993072 (99.31%)** |
| **Exact-Span Recall** | **0.990783 (99.08%)** |
| **Exact-Span F1** | **0.991926 (99.19%)** |
| **Boundary Errors** | **3** |
| **Pure False Positives** | **0** |
| **Pure False Negatives** | **1** |
| **Duplicate Predictions** | **0** |
| **Basic Offset Failures** | **0** |
| **Tokenizer Alignment Failures** | **0** |
| **Truncated Sentences** | **0** |

---

## 18. Metric Separation: Published vs. Mofid vs. Phase 21.1

It is critical to clearly separate the three distinct result families:

| Benchmark / Source | Evaluation Protocol | Scope | Reported F1 |
| :--- | :--- | :--- | :--- |
| **Published HooshvareLab Model Card** | Published HooshvareLab overall PEYMA F1 | Overall PEYMA test split | **93.40%** |
| **Published HooshvareLab Model Card** | Isolated PERSON class | *Not reported in table* | *N/A* |
| **Mofid-AI Benchmark** | Multi-class token classification metrics (accuracy, weighted/micro/macro P/R/F1) | Token-level classification across all classes | **75.83% - 77.60%** |
| **Phase 21.1 Empirical Benchmark** | **PERSON-only exact-span entity matching** | Exact $(s, e, \text{PERSON})$ triples on reconstructed text | **99.19%** |

*Protocol Note:* Published HooshvareLab overall PEYMA F1: 93.40%. Exact scoring protocol is not fully specified in the model-card result table, so it must not be treated as directly comparable with Phase 21.1's PERSON-only exact-span entity metric. Token classification metrics (such as Mofid-AI's) evaluate individual token label predictions, whereas Phase 21.1 evaluates strict entity-level exact boundary matching specifically for personal names.

---

## 19. Reproducible Error Analysis

To maintain privacy, no sensitive strings, personal names, or raw text snippets are committed to Git. The committed runner deterministically computes privacy-safe aggregate error categories:
- **Boundary Errors:** **3** (where the model detected a name but offsets differed from gold by one subword or prefix).
- **Pure False Positives:** **0** (the model did not hallucinate personal names on non-name tokens).
- **Pure False Negatives:** **1** (a single gold entity was missed completely).

---

## 20. Persian Unicode / ZWNJ Empirical Coverage

- **Corpus Findings:** In the evaluated 1,026 test sentences, gold PERSON entities in news prose predominantly used standard Persian characters.
- **Corpus Counts:**
  - Sentences with ZWNJ: `0`
  - Gold PERSON entities with ZWNJ: `0`
  - Sentences with Arabic letter variants (`ي`/`ك`): `0`
  - Gold PERSON entities with Arabic variants: `0`
- **Synthetic Coverage:** Comprehensive Unicode tests (ZWNJ within compound names like *علی‌رضا* and Arabic letter variants like *على*) are verified separately via deterministic unit tests in `tests/test_persian_ner_benchmark.py` and `tests/test_normalization.py`.

---

## 21. Recursive Privacy Gating

The benchmark serialization function (`serialize_benchmark_result`) implements recursive privacy validation across all nested mappings, lists, and sequences. It rejects any forbidden sensitive keys (`text`, `tokens`, `names`, `entities`, `snippets`, `raw_predictions`, `pii`) at any depth without leaking values in error messages.

---

## 22. Exact Reproducibility Command

The benchmark can be reproduced directly from repository code using:

```bash
python -m research.persian_ner_benchmark \
  --dataset-file ~/.cache/fa_redact_research/peyma_test.txt \
  --model HooshvareLab/bert-fa-base-uncased-ner-peyma \
  --model-revision 8b7b63371aa8f1fdad62c0f82d462a22b91b37ab \
  --output research/results/phase21_1_persian_ner_benchmark.json \
  --offline
```

---

## 23. Domain Limitations

- **News vs. Clinical Domain Shift:** PEYMA consists of formal news prose. Sentences are structured and grammatically complete.
- **Clinical EHR Characteristics:** Real clinical free text contains colloquialisms, Latin pharmaceutical terms, abbreviations, and informal doctor/patient notes.
- **Warning:** A 99.19% F1 on news text **does not** imply clinical de-identification readiness. Substantial domain degradation is expected on uncurated medical records.

---

## 24. Production Readiness Decision

### Decision: **CONDITIONAL GO FOR AN OPT-IN NER IMPLEMENTATION PROTOTYPE**

**Justification:**
1. **Model Licensing Verified:** Apache-2.0 license is confirmed for `HooshvareLab/bert-fa-base-uncased-ner-peyma`.
2. **Exact-Span Quality Proven:** Empirical exact-span F1 of **99.19%** (Precision: 99.31%, Recall: 99.08%) was reproduced on the held-out benchmark.
3. **Offset Integrity Validated:** 0 offset mapping failures across 1,026 sentences; 0 alignment violations.
4. **Zero Core Dependency Impact:** Core `fa-redact` maintains `dependencies = []`. Future NER integration can be implemented as an opt-in detector with optional extras.

*Scope Boundary:* This decision authorizes designing an opt-in `PersianNERDetector` prototype in a dedicated future implementation phase. It does NOT authorize modifying core default detectors, altering `detect()`/`redact()` defaults, or claiming clinical de-identification guarantees.

---

## 25. Next Recommended Phase

1. **Phase 21.2 (Future Proposed Sub-Phase):** Implement opt-in `PersianNERDetector` satisfying `fa_redact.protocols.Detector`:
   - Accept explicit local model checkpoint paths.
   - Package dependencies under optional extra `fa-redact[ner]`.
   - Preserve `dependencies = []` for base package.
   - Guard integration tests with `pytest.importorskip("transformers")`.
2. **Phase 22 (Future Planned Phase):** Clinical De-identification Layer (composite profiles, clinical redaction templates, strict anti-compliance disclaimers).
