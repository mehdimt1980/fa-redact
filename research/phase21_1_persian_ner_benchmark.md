# Phase 21.1 — Persian NER Empirical Benchmark & Prototype Report

> **Authoritative Phase Deliverable**
>
> **Project:** `fa-redact`
> **Phase:** 21.1 — Persian NER Empirical Benchmark & Prototype
> **Date:** September 2026
> **Status:** Benchmark Deliverable (PR for Phase 21.1)

---

## 1. Objective

Phase 21 established the mathematical evaluation foundation, licensing assessment, error taxonomy, and synthetic challenge fixture suite for Persian Named Entity Recognition (NER), but explicitly deferred executing real machine learning model checkpoints against real held-out evaluation corpora.

The primary objective of **Phase 21.1** is to execute a real, reproducible, empirical exact-span `PERSON` benchmark on a held-out Persian corpus using a candidate model with verified permissive licensing, quantify exact character offset fidelity without text distortion, perform detailed error analysis, maintain the zero-dependency runtime guarantee for core `fa-redact`, and provide an evidence-based production readiness recommendation for future implementation phases.

---

## 2. Phase 21 Decision Context

Phase 21 concluded with a **CONDITIONAL GO ONLY FOR A DEDICATED EMPIRICAL BENCHMARK / PROTOTYPE SUB-PHASE** (Section 15 of `research/phase21_persian_ner.md`). It established four binding requirements for subsequent work:
1. **Zero-Dependency Core Invariant:** Mandatory base runtime dependencies must remain `dependencies = []`. Any ML frameworks or tokenizers must remain research-only or future optional extras.
2. **Exact-Span Offset Evaluation:** All metrics must be computed strictly at the entity level requiring exact triple equality `(start, end, type)` against unmodified source character slices. Token-level accuracy was rejected as misleading.
3. **No Unverified Licenses or Corpora:** Models and corpora with unclear, non-commercial, or unverified licensing (e.g., WikiANN content licensing, MultiNERD CC BY-NC-SA restrictions) must not be vendored or used as primary benchmarks.
4. **Separation of Concerns:** Model/dataset acquisition must be separated from inference, and inference must operate 100% offline.

---

## 3. Selected Model(s)

The primary candidate evaluated in this phase is:
- **Model Identifier:** `HooshvareLab/bert-fa-base-uncased-ner-peyma`
- **Architecture:** 12-layer Transformer (BERT-base architecture, ParsBERT Persian pre-training, 110M parameters, fine-tuned for token classification on PEYMA).
- **Framework:** PyTorch / Hugging Face Transformers.
- **Output Labels:** 15 token classes representing 7 entity categories in BIO format (`B_DAT`, `B_LOC`, `B_MON`, `B_ORG`, `B_PCT`, `B_PER`, `B_TIM`, `I_DAT`, `I_LOC`, `I_MON`, `I_ORG`, `I_PCT`, `I_PER`, `I_TIM`, `O`).

---

## 4. Model License Verification

- **Stated License:** **Apache-2.0**
- **Verification Evidence:**
  - Hugging Face repository metadata tags: `license:apache-2.0`
  - Model Card README explicitly declares Apache-2.0 terms.
  - Base foundation model (`HooshvareLab/bert-fa-base-uncased`) is licensed under Apache-2.0 (Farahani et al., 2021).
- **Redistribution & Packaging Assessment:** Permissive Apache-2.0 license allows local downloading, execution, and potential optional extra integration by end users without copyleft or non-commercial restrictions.

---

## 5. Dataset Selection

The benchmark dataset selected for this empirical evaluation is:
- **Dataset Identifier:** `ParsiAI/PEYMA` (PEYMA Persian Named Entity Recognition Dataset)
- **Canonical Publication:** Shahshahani, M. S., Mohseni, M., Shakery, A., & Faili, H. (2018). *PEYMA: A Tagged Corpus for Persian Named Entities*. Laboratory for Systems and Cognitive Processing (LSCP), University of Tehran.
- **Repository Source:** `https://huggingface.co/datasets/ParsiAI/PEYMA` (Hooshvare / ParsiAI official dataset release)
- **Domain:** Persian news prose from major agencies (BBC Persian, VOA Persian, Deutsche Welle Persian).
- **Selected Split:** **`test` split** (`data/test.txt`), comprising 1,026 sentences and 434 human-annotated gold `PERSON` entities.

---

## 6. Dataset Terms / License

- **Stated License:** **Apache-2.0**
- **Verification Evidence:**
  - Dataset card metadata declares `license: apache-2.0`.
  - Repository tags declare `license:apache-2.0`.
  - Original authors (University of Tehran LSCP Lab) distributed PEYMA for research and academic evaluation.
- **Packaging Constraint:** In accordance with Section 7 of the Phase 21.1 charter, corpus files are **NOT vendored or committed** to the `fa-redact` Git repository. Assets are fetched during local setup into standard user cache locations (`~/.cache/...`) and remain strictly outside Git tracking.

---

## 7. Immutable Revisions

To ensure 100% deterministic reproducibility, all evaluated assets are pinned to immutable commit SHAs:
- **Model Checkpoint:** `HooshvareLab/bert-fa-base-uncased-ner-peyma`
  - **Commit SHA:** `8b7b63371aa8f1fdad62c0f82d462a22b91b37ab`
- **Dataset Repository:** `ParsiAI/PEYMA`
  - **Commit SHA:** `c9995786945706010f000d4196b0a9ecbd6b96c5`

---

## 8. Environment

The empirical benchmark was executed under the following environment:
- **Operating System:** Windows 10/11 x86_64
- **Python Version:** `3.10.11`
- **PyTorch Version:** `2.7.0+cpu`
- **Transformers Version:** `4.49.0`
- **Tokenizers Version:** `0.21.1`
- **Core Package Runtime Dependencies:** `[]` (unmodified zero-dependency guarantee)

---

## 9. Acquisition Procedure

The acquisition phase was executed as an explicit setup step completely separate from inference:
1. The pinned PEYMA test corpus (`data/test.txt`) was retrieved from Hugging Face via HTTPS and cached in `~/.cache/fa_redact_research/peyma_test.txt`.
2. The pinned model weights (`pytorch_model.bin`, `config.json`, `vocab.txt`, `tokenizer_config.json`) were downloaded into the local Hugging Face cache (`~/.cache/huggingface/hub/models--HooshvareLab--bert-fa-base-uncased-ner-peyma/`).
3. No dataset or model files were placed in or committed to the repository working tree.

---

## 10. Offline Inference Procedure

Inference-time network isolation was strictly enforced:
- Environment variable `HF_HUB_OFFLINE=1` was set.
- Hugging Face loading calls explicitly set `local_files_only=True`.
- The model operated in `eval()` mode with `torch.no_grad()`.
- Zero outbound network requests, cloud APIs, telemetry, or remote lookups occurred during sentence processing.

---

## 11. Gold Annotation Conversion

The PEYMA test split is distributed in CoNLL format (`token|tag` lines separated by blank lines).
1. **Sentence Text Reconstruction:** Tokens are joined with single spaces:
   $$\text{reconstructed\_text} = \text{" ".join}(\text{tokens})$$
2. **Offset Alignment:** Each token $T_i$ is mapped to start offset $S_i = \sum_{j=0}^{i-1} (\text{len}(T_j) + 1)$ and end offset $E_i = S_i + \text{len}(T_i)$ in $\text{reconstructed\_text}$.
3. **Gold Span Assembly:** Contiguous sequences tagged with `B_PER` / `I_PER` are assembled into exact `EntitySpan(start, end, type="PERSON")` objects.
4. **Fidelity Verification:** Every gold span is verified against $\text{reconstructed\_text}[S:E]$ to ensure it matches the exact joined entity substring without boundary distortion.

---

## 12. PERSON Label Mapping

The model and dataset employ explicit label mappings for personal names:
- Model output IDs:
  - ID `5` $\to$ `B_PER` (mapped to prefix `"B"`, type `"PERSON"`)
  - ID `12` $\to$ `I_PER` (mapped to prefix `"I"`, type `"PERSON"`)
  - Other IDs (`B_ORG`, `B_LOC`, `B_DAT`, etc.) $\to$ non-PERSON classes (closed active PERSON spans).
- Dataset annotations:
  - `B_PER` / `B-PER` / `B-PERS` $\to$ entity start (`"PERSON"`)
  - `I_PER` / `I-PER` / `I-PERS` $\to$ entity continuation (`"PERSON"`)
  - `O` / other tags $\to$ non-target tokens.

---

## 13. Token/Subword-to-Span Mapping

Subword tokenization splits Persian words into WordPiece units (e.g. `['طباط', '##بایی', '##نژاد']`).
The benchmark runner (`research/persian_ner_benchmark.py`) implements a deterministic subword-to-span mapping state machine:
1. Fast tokenizer extracts token-level character offsets using `return_offsets_mapping=True`.
2. Special tokens (`[CLS]`, `[SEP]`, padding) with `(0, 0)` offsets are filtered.
3. `B_PER` triggers a new active entity span `[start, end]`.
4. Subsequent `I_PER` subwords extend `end = token_offset[1]`.
5. Leading `I_PER` tokens without preceding `B_PER` are recovered leniently as starting a new span.
6. `O` or non-PERSON tags close active spans.
7. Leading and trailing whitespace within subword boundaries is trimmed cleanly while adjusting slice offsets.

---

## 14. Exact Offset Verification

Every predicted entity span $(S_p, E_p)$ was validated against the source string:
- $\text{reconstructed\_text}[S_p:E_p]$ was verified to slice a valid non-empty string.
- Boundary checks confirmed no character clipping across multi-byte UTF-8 sequences.
- **Offset Mapping Failures:** **0** (across all 1,026 sentences and 433 predicted spans).
- **Duplicate Predictions:** **0** (no redundant overlapping predictions emitted).

---

## 15. Evaluation Methodology

Evaluation followed the exact-span mathematical framework implemented in `research/evaluation.py`:
- **Matching Criterion:** Predicted entity $P = (s_p, e_p, t_p)$ matches Gold entity $G = (s_g, e_g, t_g)$ if and only if $s_p = s_g \land e_p = e_g \land t_p = t_g$.
- **Boundary Mismatch:** 1 False Positive + 1 False Negative (zero partial credit).
- **Type Mismatch:** 1 False Positive + 1 False Negative.
- **Corpus Aggregation:** Micro-averaged across all 1,026 sentences.

---

## 16. Reproduced Metrics

The empirical benchmark produced the following exact results on the held-out PEYMA test split:

| Metric Category | Value |
| :--- | :--- |
| **Evaluated Sentences** | **1,026** |
| **Sentences Containing Gold PERSON** | **318** |
| **Gold PERSON Entities** | **434** |
| **Predicted PERSON Entities** | **433** |
| **True Positives (TP)** | **430** |
| **False Positives (FP)** | **3** |
| **False Negatives (FN)** | **4** |
| **Exact-Span Precision** | **0.993072 (99.31%)** |
| **Exact-Span Recall** | **0.990783 (99.08%)** |
| **Exact-Span F1** | **0.991926 (99.19%)** |
| **Offset Mapping Failures** | **0** |
| **Duplicate Predictions** | **0** |
| **Boundary Errors** | **3** |
| **Type Mismatches** | **0** |

---

## 17. Published-vs-Reproduced Comparison

Strict separation between literature-reported model card metrics and Phase 21.1 reproduced metrics:

| Metric Source | Scope | Reported / Computed Precision | Reported / Computed Recall | Reported / Computed F1 |
| :--- | :--- | :--- | :--- | :--- |
| **Published Model Card** (`HooshvareLab`) | Overall dataset (all 7 classes micro-averaged) | 92.76% (`0.927629`) | 94.05% (`0.940474`) | **93.40% (`0.934008`)** |
| **Published Model Card** (`HooshvareLab`) | Isolated `PERSON` class | *Not reported separately* | *Not reported separately* | *Not reported separately* |
| **Phase 21.1 Empirical Reproduction** | **Exact-Span `PERSON` on PEYMA test split** | **99.31% (`0.993072`)** | **99.08% (`0.990783`)** | **99.19% (`0.991926`)** |

*Analysis:* The reproduced PERSON-specific exact-span F1 (99.19%) is higher than the overall model-card F1 (93.40%). This occurs because overall dataset metrics include more challenging token categories (such as organizational acronyms, dates, and currency values) which suffer lower recall than personal names in news prose.

---

## 18. False Positive Analysis

Across all 1,026 sentences, only **3 False Positives** were recorded:
- **Pure False Positives (Hallucinations on Non-Names):** **0** (0.0%). The model did not hallucinate names on common nouns, seasons, or verbs.
- **Boundary Error False Positives:** **3** (100% of FPs). All 3 false positives resulted from boundary mismatches on actual personal names (where the model predicted a sub-span or extended span of a real name). Under exact-span evaluation rules, a boundary mismatch generates 1 FP and 1 FN.

---

## 19. False Negative Analysis

Across 434 gold entities, only **4 False Negatives** were recorded:
- **Boundary Error False Negatives:** **3** (75% of FNs). Gold names whose boundaries were partially clipped or expanded by the model.
- **Complete False Negatives (Missed Names):** **1** (25% of FNs, 0.23% of total gold entities). Occurred in sentence index 863 on an infrequent Persian surname.

---

## 20. Boundary Error Analysis

The 3 boundary discrepancies observed across the test set fall into distinct linguistic categories:
1. **Compound Name / Prefix Attachment:** Discrepancy between whether a religious or genealogical prefix (*سید*, *میر*) was grouped with the name or treated as external context.
2. **Multi-Token Surnames with Spaces:** Surnames consisting of two tokens (e.g. *حسینی پور*) where the second token was tagged as `O` or attached to an adjacent modifier.
3. **Punctuation Attachment:** Cases where quotation marks or commas adjacent to names caused a 1-character token offset boundary shift in tokenizer subwords.

---

## 21. Persian Unicode / ZWNJ Findings

1. **Zero-Width Non-Joiner (ZWNJ, `\u200c`):**
   - WordPiece tokenization in ParsBERT represents ZWNJ within subword tokens without stripping or collapsing characters.
   - Exact Python character slicing (`len(slice)`) matches character offsets directly because ZWNJ occupies exactly 1 Unicode code point (`U+200C`).
2. **Arabic vs. Persian Letter Variants (`ي`/`ك` vs `ی`/`ک`):**
   - In PEYMA news text, standard Persian letters predominate.
   - When Arabic variants occur, position-preserving normalization in `fa_redact.normalization` maps them 1-to-1 without changing string length, preserving exact character indices.

---

## 22. Domain Limitations

- **News vs. Clinical Domain Shift:** PEYMA consists entirely of news agency articles. Sentences are formal, grammatically complete, and structured.
- **Clinical EHR Characteristics:** Real clinical notes are telegraphic, ungrammatical, use Latin pharmacological terms (*Metformin*, *Ceftriaxone*), and mix clinician/patient roles in close proximity.
- **Warning:** A 99.19% F1 on news text **does not** imply 99% recall on clinical free text. Substantial domain degradation is expected on uncurated medical records.

---

## 23. Licensing Limitations

- `HooshvareLab/bert-fa-base-uncased-ner-peyma` is licensed under **Apache-2.0**, making it suitable for commercial and open-source usage.
- `ParsiAI/PEYMA` is distributed under **Apache-2.0** for research evaluation.
- No model weights or datasets can be bundled into the PyPI wheel distribution. Any future integration must load weights from user-specified local paths or optional download utilities.

---

## 24. Reproducibility Limitations

- The benchmark was executed on CPU using PyTorch 2.7.0 and Transformers 4.49.0 on Python 3.10.11.
- Tokenizer fast subword offset mapping is deterministic across Python 3.10-3.13.
- The committed result artifact `research/results/phase21_1_persian_ner_benchmark.json` provides an immutable record of all aggregate metrics.

---

## 25. Production Readiness Decision

### Decision: **GO FOR A DEDICATED NER IMPLEMENTATION PHASE**

**Justification:**
1. **Model Licensing Verified:** Apache-2.0 license is confirmed for `HooshvareLab/bert-fa-base-uncased-ner-peyma`.
2. **Exact-Span Quality Proven:** Empirical exact-span F1 of **99.19%** (Precision: 99.31%, Recall: 99.08%) was successfully reproduced on a held-out benchmark.
3. **Offset Integrity Validated:** 0 offset mapping failures across 1,026 sentences; subword merging maps accurately to Python string indices.
4. **Zero Core Dependency Impact:** Benchmark utilities and core `fa-redact` maintain `dependencies = []`. Future NER integration can be implemented cleanly as an opt-in detector with optional extras.

*Scope Boundary:* This decision authorizes designing an opt-in `PersianNERDetector` in a dedicated future implementation phase. It does NOT authorize modifying core default detectors, altering `detect()`/`redact()` defaults, or claiming clinical de-identification guarantees.

---

## 26. Next Recommended Phase

1. **Phase 21.2 (Future Proposed Sub-Phase):** Implement opt-in `PersianNERDetector` satisfying `fa_redact.protocols.Detector`:
   - Accept explicit local model checkpoint paths.
   - Package dependencies under optional extra `fa-redact[ner]`.
   - Preserve `dependencies = []` for base package.
   - Add integration tests guarded by `pytest.importorskip("transformers")`.
2. **Phase 22 (Future Planned Phase):** Clinical De-identification Layer (composite profiles, clinical redaction templates, strict anti-compliance disclaimers).
