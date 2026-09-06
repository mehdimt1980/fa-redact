# Phase 21 — Persian Names / NER Research & Evaluation

> **Authoritative Phase Document**
>
> **Project:** `fa-redact`
> **Phase:** 21 — Persian Names / NER Research & Evaluation
> **Date:** September 2026
> **Status:** Research Deliverable (PR #21)

---

## 1. Problem Definition

### 1.1 Deterministic Identifiers vs. Probabilistic Free-Text Entities

In prior development phases (`fa-redact` v0.1.0 and v0.2.0), the library focused on **deterministic, structured identifiers**:
- **Iranian National ID (Code Melli):** 10-digit fixed-length numeric format validated by a strict Modulo-11 checksum algorithm.
- **Iranian Mobile Numbers:** Strict 10-to-13 character prefix format governed by the official 2026 Communications Regulatory Authority (CRA) National Numbering Plan.
- **Iranian IBAN (Sheba):** 26-character alphanumeric sequence validated by MOD-97 checksum arithmetic.
- **Bank Card Numbers (PAN):** 16-digit payment card sequences validated by the Luhn Modulo-10 checksum algorithm.
- **ASCII Email Addresses:** Syntactic dot-atom and RFC 5322 domain structural validation.
- **Pattern Rules:** Explicit, user-configured regular expressions with bounded capture groups.

For each of these direct identifier categories, validity is mathematically or structurally verifiable. The false-positive rate on non-identifier text is near zero when checksums are enforced, and detection logic operates deterministically without machine learning models or statistical ambiguity.

In stark contrast, **Persian Personal Names (`PERSON` / `PER`) in free-text prose represent a probabilistic, contextual, and open-vocabulary problem**:
1. **No Checksum or Mathematical Invariant:** A sequence of Persian words cannot be verified as a personal name by computing a hash, checksum, or fixed mathematical relation.
2. **Infinite and Open Vocabulary:** Iranian personal names encompass traditional Persian names, Arabic-origin Islamic names, Kurdish, Azeri, Gilaki, Mazandarani, Balochi, Lori, and Armenian names, as well as transliterated foreign names and modern compound forms.
3. **Severe Lexical Ambiguity & Common Noun/Adjective Homographs:** A vast number of common Persian personal names are orthographically identical to common nouns, adjectives, seasons, or abstract concepts:
   - *امید* (*Omid* = personal name / "hope")
   - *بهار* (*Bahar* = personal name / "spring")
   - *رضا* (*Reza* = personal name / "satisfaction", "consent")
   - *روشن* (*Roshan* = personal name / "bright", "clear")
   - *شریف* (*Sharif* = personal name / "noble", "honorable")
   - *پیروز* (*Pirooz* = personal name / "victorious")
   - *آزاد* (*Azad* = personal name / "free", "unconstrained")
   - *سلامت* (*Salamat* = personal name / "health", "safety")
   - *توان* (*Tavan* = personal name / "power", "ability")
   - *فرمان* (*Farman* = personal name / "order", "command")
4. **Lack of Orthographic Casing in Persian Script:** Unlike Latin-script languages where capitalized initial letters provide strong syntactic cues for proper nouns (e.g., *John Smith* vs. *smith*), Persian script uses an unicameral alphabet (no uppercase/lowercase distinction). Entity boundaries must be inferred purely from lexical semantics, syntax, and surrounding context.
5. **Morphological Complexity & Compound Surnames:** Persian names frequently span multiple tokens with prefixes (*سید*, *سیده*, *میر*, *حاج*, *شیخ*), multi-token surnames (*طباطبایی نژاد*, *حسینی پور*, *میر محمدی*), and Zero-Width Non-Joiner (ZWNJ, `U+200C`) variations (*علیرضا* vs. *علی‌رضا*, *میرزایی‌فر*).
6. **Contextual Role Mixing in Healthcare:** In clinical notes, patient names, physician names, nurse names, family members, and institutional names named after persons (e.g., *بیمارستان شهید بهشتی*) appear in close proximity without uniform structural delimiters.

### 1.2 Engineering Consequences of Probabilistic Detection

Because personal name detection is inherently statistical:
- **False Positives (Over-redaction):** Incorrectly predicting a common word as a name damages document readability, destroys clinical semantics (e.g., redacting "فصل بهار" to "فصل `[PERSON_1]`" or redacting "وضعیت سلامت بیمار" to "وضعیت `[PERSON_1]` بیمار"), and degrades downstream utility.
- **False Negatives (Under-redaction / Leakage):** Failing to detect a patient or clinician name leaves sensitive PII directly exposed in redacted logs, research corpora, or external LLM prompts, violating privacy invariants.

Consequently, **false positives and false negatives must be treated as first-class engineering concerns** rather than minor edge cases.

---

## 2. Requirements for `fa-redact`

Any named entity recognition capability considered for `fa-redact` must satisfy strict architectural, privacy, and performance requirements:

1. **Zero-Dependency Core Invariant:**
   The base package `fa-redact` must maintain `dependencies = []`. Core rule-based detectors, validators, pipeline orchestration, conflict resolution, structured data helpers, and CLI must remain functional with the Python standard library alone. Any machine learning or NLP framework must be packaged strictly as an **optional extra** (e.g. `fa-redact[ner]`).
2. **Exact-Span Offset Invariant:**
   Every detection must emit `(start, end)` character offsets such that `original_text[start:end]` accurately slices the exact detected entity substring in the user's input string. Subword tokenizers (WordPiece, BPE) and any internal text normalizers must preserve or reconstruct exact character-level offsets pointing to the unmodified original Python string.
3. **Deterministic, 100% Offline Inference:**
   Once model assets are installed or cached locally, inference must execute entirely offline without making outbound network requests, contacting external APIs (Hugging Face Hub, cloud inference endpoints), or emitting telemetry. Automatic hidden background downloads during runtime `detect()` or `redact()` calls are prohibited.
4. **Supported Python Versions:**
   Optional NER extensions must maintain compatibility across supported Python versions (`>=3.10`, including 3.10, 3.11, 3.12, and 3.13). Any optional dependency whose current releases drop Python 3.10 support (e.g. recent ONNX Runtime versions) must be bounded or guarded by environment markers.
5. **Standard `Detector` Protocol Compliance:**
   Probabilistic detectors must satisfy `fa_redact.protocols.Detector`:
   ```python
   def detect(
       self,
       original_text: str,
       normalized_text: str,
   ) -> Sequence[Detection]: ...
   ```
6. **Transparent Licensing:**
   All datasets and models evaluated or integrated must possess unambiguous, permissive, or well-defined licenses compatible with the project's open-source architecture.
7. **Narrow Entity Scope:**
   The primary deliverable entity type is `PERSON` (or `PERSON_NAME`). Broad multi-class extraction (e.g. extracting all diseases, facilities, drugs, percentages) is out of scope for Phase 21.

---

## 3. Candidate Datasets Comparison

We conducted a review of publicly available Persian Named Entity Recognition corpora:

| Dataset Name | Canonical Source / URL | Primary Publication / Authors | Domain & Text Source | Entity Labels | Size (Tokens / Sentences) | Splits Available | Stated License / Terms | Redistribution & Packaging Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PEYMA** | [LSCP-Lab/PEYMA](https://github.com/LSCP-Lab/PEYMA) | Shahshahani et al. (2018), University of Tehran | Persian News (BBC Persian, VOA, Deutsche Welle) | 7 types: `Person`, `Organization`, `Location`, `Date`, `Time`, `Money`, `Percent` | 302,530 tokens / 7,145 sentences / 41,148 entity tokens | Train (~5,716 sent) / Test (~1,429 sent) | Research / Academic use stated by authors | **Safe for external academic citation & research reference.** *Redistribution / commercial / package vendoring requires separate verification.* |
| **ArmanPersoNERCorpus (ARMAN)** | [HaniehP/PersianNER](https://github.com/HaniehP/PersianNER) / [ACL Anthology L18-1701](https://aclanthology.org/L18-1701/) | Poostchi et al. (LREC 2018) | Contemporary Persian text & news (BijanKhan subset) | 6 types: `pers` (Person), `org`, `loc`, `fac`, `event`, `pro`, `other` | 250,015 tokens / 7,682 sentences | 3-fold cross-validation / Standard splits | Academic Research Use Only (corpus terms) | **Safe for external academic reference & research benchmarking.** *Unsafe to vendor in MIT package.* |
| **MultiNERD (Persian subset)** | [Babelscape/multinerd](https://huggingface.co/datasets/Babelscape/multinerd) | Tedeschi & Navigli (NAACL 2022) | Multilingual Wikipedia / Wikinews | 15 types: `PER`, `ORG`, `LOC`, `DIS`, `ANIM`, etc. | ~30,000 sentences (fa) | Standard train/dev/test | CC BY-NC-SA 4.0 | **Safe for research reference.** *Wikipedia domain; non-commercial / ShareAlike restrictions.* |
| **WikiANN (Persian subset)** | [unimelb-nlp/wikiann](https://huggingface.co/datasets/unimelb-nlp/wikiann) | Pan et al. (ACL 2017) / Rahimi et al. (ACL 2019) | Persian Wikipedia articles with cross-lingual entity links | 3 types: `PER`, `ORG`, `LOC` | ~20,000 sentences (train) / ~10,000 (test) | Standard train/dev/test | UNKNOWN / REQUIRES VERIFICATION (Hugging Face `unimelb-nlp/wikiann` shows license: unknown; Apache-2.0 in loader script applies to script code only) | **License unverified.** *Silver standard with high label noise and partial spans; do not redistribute, vendor, or assume permissive reuse.* |
| **Persian Clinical Corpora** | Academic literature (Tehran Univ. of Med. Sci., Shahid Beheshti Univ.) | Various medical informatics papers (2020–2024) | Medical Q&A, clinical health articles | Disease, Drug, Symptom (rarely gold `PERSON`) | Variable / Small | Non-standard | Restricted access / Confidential | **Restricted / Internal.** No public, open, gold-standard clinical discharge summary dataset with personal names exists in Persian. |

### Key Dataset Findings:
- **PEYMA and ARMAN** are the primary established research benchmarks for Persian NER, containing human-annotated `PERSON` / `pers` entities in news and formal text.
- **No public, redistributable clinical EHR corpus with gold personal names exists in Persian.** Medical datasets in the literature focus on clinical terminology (diseases, pharmacology), not de-identification of real patient records.
- All primary general corpora carry **academic research restrictions, non-commercial (NC), ShareAlike (SA), or unverified license terms (WikiANN)**, making vendoring corpus files into the `fa-redact` repository unacceptable. WikiANN dataset content licensing is unknown and requires verification; the Apache-2.0 header on dataset scripts covers loader code only, not the underlying Wikipedia-derived corpus.

---

## 4. Candidate Models & Approaches Comparison

We investigated candidate approaches for Persian `PERSON` NER:

| Approach / Model | Architecture | Framework & Dependencies | Stated Model License | Offline Feasibility | Literature Reported Metrics | Computational Characteristics | Feasibility for `fa-redact` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Heuristic / Dictionary / Regex** | Static name lists + Honorific prefixes + Suffix rules | Standard Library (`re`, `set`) — **0 dependencies** | MIT | 100% Offline | Poor (severe false positives on common words; misses out-of-vocabulary names) | Minimal CPU overhead | **REJECTED.** Unacceptable false positive / false negative rates. |
| **2. Stanza Persian ARMAN NER** | BiLSTM-CRF (`stanza.Pipeline(lang='fa', processors='tokenize,ner')`) | `stanza`, `torch` | Apache-2.0 | Offline after explicit local model installation/download | **80.07% F1** on ARMAN (Stanza documentation) | Moderate CPU overhead; requires Stanza/PyTorch ecosystem | **CONDITIONAL.** Moderate accuracy on ARMAN; requires Stanza/PyTorch runtime dependencies. |
| **3. ParsBERT PEYMA NER** (`HooshvareLab/bert-fa-base-uncased-ner-peyma`) | 12-layer Transformer (BERT-base, 110M params) | `transformers`, `torch`, `tokenizers` | Apache-2.0 (Model Card) | 100% Offline with local weights | **93.40% Overall F1** on PEYMA (Model Card) | Requires PyTorch runtime; CPU latency requires benchmarking | **CANDIDATE FOUNDATION.** Strong Persian linguistic modeling; Apache-2.0 license. |
| **4. ParsBERT ARMAN NER** (`HooshvareLab/bert-fa-base-uncased-ner-arman`) | 12-layer Transformer (BERT-base, 110M params) | `transformers`, `torch`, `tokenizers` | Apache-2.0 (Model Card) | 100% Offline with local weights | **99.84% Overall F1** on ARMAN (Model Card) | Requires PyTorch runtime; benchmark setup is dataset-specific | **CANDIDATE FOUNDATION.** Strong linguistic representation on ARMAN fold. |
| **5. DistilBERT-fa NER** (`HooshvareLab/distilbert-fa-zwnj-base-ner`) | 6-layer Transformer (66M params, distilled) | `transformers`, `torch`, `tokenizers` | UNCLEAR / REQUIRES VERIFICATION (Base model is Apache-2.0, but fine-tuned NER checkpoint lacks explicit license declaration on its repository) | 100% Offline with local weights | **95.07% Overall F1**, **95.85% PER F1** on combined Persian NER dataset | Reduced parameter count; faster CPU inference than BERT-base | **CANDIDATE LIGHTWEIGHT.** Compact architecture with PER-specific reporting. |
| **6. ONNX Runtime Exported ParsBERT / DistilBERT** | Pre-quantized INT8 / FP32 ONNX graph + Fast Subword Tokenizer | `onnxruntime` + Python standard library | Apache-2.0 (Model permitting) / MIT (ONNX Runtime) | 100% Offline | Expected close to PyTorch baseline; requires empirical benchmarking | Reduced dependency footprint compared to full PyTorch | **CANDIDATE ARCHITECTURE.** Requires prototype validation for Python matrix compatibility. |

---

## 5. Licensing Assessment

Licensing is a **hard gate** for any software component or data asset considered for integration:

| Candidate Asset | Asset Type | Stated License / Terms | Safe to Reference Externally? | Safe to Download for Local Research? | Safe to Vendor in Repository? | Safe for Package Integration? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PEYMA Corpus** | Dataset | Research / Academic use stated by authors | **YES** | **YES** | **NO** (Terms do not permit unconditional PyPI package bundling) | **NO** (Cannot bundle data files in PyPI wheel) |
| **ARMAN Corpus** | Dataset | Academic Research Use Only (corpus terms) | **YES** | **YES** | **NO** (Academic-only terms incompatible with MIT package) | **NO** (Cannot bundle data files) |
| **MultiNERD (fa)** | Dataset | CC BY-NC-SA 4.0 | **YES** | **YES** | **NO** (Non-commercial restriction) | **NO** |
| **WikiANN (fa)** | Dataset | UNKNOWN / REQUIRES VERIFICATION (Canonical `unimelb-nlp/wikiann` metadata declares unknown; script Apache-2.0 covers loader code only) | **YES** (Academic reference) | **YES** (Academic research download) | **NO** (Unverified license / silver data) | **NO** (Cannot bundle or redistribute unverified corpus) |
| **ParsBERT PEYMA Weights** (`HooshvareLab`) | Model Weights | Apache-2.0 (Model Card) | **YES** | **YES** | **NO** (Large binary files do not belong in git) | **YES** (Permissive Apache-2.0; user-downloaded / local path) |
| **ParsBERT ARMAN Weights** (`HooshvareLab`) | Model Weights | Apache-2.0 (Model Card) | **YES** | **YES** | **NO** (Large binary files do not belong in git) | **YES** (Permissive Apache-2.0) |
| **DistilBERT-fa Weights** (`HooshvareLab`) | Model Weights | UNCLEAR / REQUIRES VERIFICATION (Fine-tuned NER checkpoint lacks explicit license tag; base model is Apache-2.0) | **YES** | **YES** | **NO** (Large binary files do not belong in git) | **NO / REQUIRES VERIFICATION** (Unclear license prevents unverified redistribution/integration) |
| **ONNX Runtime** | Runtime Engine | MIT | **YES** | **YES** | N/A (Standard pip dependency) | **YES** (Compatible with `fa-redact` MIT license) |

### Hard Gate Summary:
- **No training datasets or corpus files are committed to this repository.**
- **No binary model weights or tokenizer blobs are committed to this repository.**
- Model weights released under **Apache-2.0** can be loaded by end users via optional extras from local storage.

---

## 6. Dependency & Packaging Assessment

### 6.1 Preservation of Zero-Dependency Core
The core `fa-redact` package must remain completely free of mandatory runtime dependencies:
```toml
# pyproject.toml
[project]
dependencies = []
```

### 6.2 Optional Extra Principles (Future Sub-Phase)
No optional dependencies are added in Phase 21. For any future prototype sub-phase, an optional extra (e.g. `fa-redact[ner]`) must be strictly decoupled from the core package so that `dependencies = []` is preserved.

### 6.3 ONNX Runtime Python Version Compatibility
- `onnxruntime` 1.29.0 requires `python >= 3.11` on certain platforms.
- `onnxruntime` 1.24.2 requires `python >= 3.10`.
- An open-ended future requirement such as `onnxruntime>=1.16.0; python_version < '3.14'` must not be proposed as though that guarantees Python 3.10 resolution forever; while a resolver on Python 3.10 may choose the newest compatible version today, future release behavior must be tested.
- **Requirement:** The prototype phase must establish tested dependency bounds/environment markers for each supported Python version before defining `fa-redact[ner]`.
- **Phase 21 Status:** Do NOT add an optional dependency in Phase 21.

### 6.4 Offline Model Loading & Asset Management
- In accordance with Privacy Invariant 19, `fa-redact` **must never initiate automatic runtime network requests** to Hugging Face or remote CDNs during `detect()` or `redact()`.
- Future NER detectors must require an **explicit local model file path** or read a configured environment variable (e.g. `FA_REDACT_NER_MODEL_PATH`), ensuring the developer maintains complete control over local model assets and air-gapped deployments.

---

## 7. Offset & Span Mapping Invariants

A critical invariant of `fa-redact` is:
$$\text{original\_text}[\text{start}:\text{end}] \equiv \text{detected\_entity\_value}$$

### Subword Tokenization Offset Challenges
Transformer-based models (such as ParsBERT) split Persian words into subword tokens using WordPiece or Byte-Pair Encoding (BPE):
- Example: The name "طباطبایی‌نژاد" may be tokenized into `['طباط', '##بایی', '##‌نژاد']`.
- If a tokenizer applies destructive pre-tokenization (e.g., stripping ZWNJ `\u200c`, removing diacritics, decomposing Unicode characters, or stripping whitespace), the token-level character offsets returned by Hugging Face's `return_offsets_mapping=True` will point to the *normalized* or *modified* string rather than the original input string.

### Strict Offset Mapping Rules for Future Implementation:
1. The NER detector must use the original source string for token offset alignment.
2. Contiguous subword tokens tagged with `B-PERS` and `I-PERS` must be merged into a single `[start:end]` entity span.
3. The slice `original_text[start:end]` must be verified to ensure that:
   - It does not cut across Unicode multi-byte characters or combine with adjacent whitespace.
   - Leading and trailing whitespace or punctuation attached by tokenizer boundaries are stripped cleanly with corresponding offset adjustments.
4. Position-preserving normalization guarantees (`len(normalized_text) == len(original_text)`) must remain active.

---

## 8. Evaluation Methodology

### 8.1 Exact-Span Entity-Level Metrics

Token-level accuracy (e.g., scoring individual subword tokens as $O$ or $B\text{-}PERS$) is **strictly inadequate and misleading** for redaction:
- In a document of 1,000 tokens with 10 entity tokens, predicting all tokens as $O$ yields 99% token accuracy, but **0% entity recall** (complete privacy failure).
- Token accuracy masks entity boundary errors (e.g., redacting "محمد رضایی" as only "محمد" leaves the surname exposed).

Therefore, `fa-redact` adopts **Entity-Level Exact-Span Evaluation**:
A predicted entity $P = (s_p, e_p, t_p)$ matches a gold entity $G = (s_g, e_g, t_g)$ if and only if:
$$s_p = s_g \quad \land \quad e_p = e_g \quad \land \quad t_p = t_g$$

### 8.2 Mathematical Metric Formulations
- **True Positives ($TP$):** $\left| \{ G \in \text{Gold} \mid \exists P \in \text{Pred}: s_p = s_g \land e_p = e_g \land t_p = t_g \} \right|$
- **False Positives ($FP$):** $\left| \{ P \in \text{Pred} \mid \neg \exists G \in \text{Gold}: s_p = s_g \land e_p = e_g \land t_p = t_g \} \right|$
- **False Negatives ($FN$):** $\left| \{ G \in \text{Gold} \mid \neg \exists P \in \text{Pred}: s_p = s_g \land e_p = e_g \land t_p = t_g \} \right|$
- **Precision ($P$):**
  $$P = \frac{TP}{TP + FP} \quad (\text{if } TP+FP=0, P=1.0 \text{ if } FN=0 \text{ else } 0.0)$$
- **Recall ($R$):**
  $$R = \frac{TP}{TP + FN} \quad (\text{if } TP+FN=0, R=1.0 \text{ if } FP=0 \text{ else } 0.0)$$
- **$F_1$ Score:**
  $$F_1 = \frac{2 \cdot P \cdot R}{P + R} \quad (\text{if } P+R=0, F_1=0.0)$$

### 8.3 Error Penalties:
- **Boundary Mismatch (Partial Overlap):** If gold is `(0, 10, "PERSON")` and prediction is `(0, 8, "PERSON")`, exact-span scoring awards **0 partial credit**, registering **1 False Positive** and **1 False Negative**.
- **Type Mismatch:** If gold is `(0, 10, "PERSON")` and prediction is `(0, 10, "ORG")`, it registers **1 False Positive** and **1 False Negative**.
- **Duplicate Predictions:** Under the default `count_as_fp` policy, duplicate predicted spans matching a gold entity are awarded 1 TP for the first occurrence, while subsequent identical emissions count as FPs, penalizing precision. Under `reject` policy, duplicate predictions raise `ValueError`.

---

## 9. Error Analysis Framework & Failure Modes

An extensive taxonomy of Persian named entity failure modes must be accounted for:

```
                               PERSIAN NER FAILURE MODES
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         │                                 │                                 │
  Lexical Ambiguity               Morphological & Orthographic        Contextual & Domain
  ├── Common Noun Homographs      ├── ZWNJ (U+200C) Variations        ├── News-to-Clinical Domain Shift
  │   (امید, بهار, رضا, روشن)     │   (علی‌رضا vs علیرضا)             │   (telegraphic clinical notes)
  ├── Titles Without Names        ├── Arabic Character Variants       ├── Institution vs Person
  │   (دکتر, مهندس, بیمار)        │   (ي / ك vs ی / ک)                │   (بیمارستان شهید بهشتی)
  └── Out-of-Vocabulary Names     ├── Compound Multi-Token Surnames   └── Role Ambiguity
      (rare regional/foreign)     │   (سید علی طباطبایی نژاد)             (physician vs patient vs relative)
                                  └── Ezafe Constructions
                                      (پرونده آقای رضایی)
```

### 1. Common Noun / Adjective Homographs
- Example: "بهار فصل زیبایی است" (*Bahar* is spring) vs. "بهار احمدی مدارک را تحویل داد" (*Bahar* is a person).
- Risk: Context-unaware models or naive dictionaries tag seasons or adjectives as people, causing massive over-redaction.

### 2. Title / Honorific Preceding Names
- Persian formal titles (*دکتر*, *آقای*, *خانم*, *مهندس*, *استاد*, *سید*, *سیده*, *حاج آقا*) may or may not be annotated as part of the entity span depending on the dataset.
- In PEYMA, titles are generally excluded from the `Person` span (e.g. `[دکتر] [مریم کاظمی](PER)`), whereas in some clinical guidelines, honorifics are grouped with the name. A consistent boundary policy must be enforced.

### 3. Compound Surnames and Prefixes
- Surnames containing prefixes (*میر*, *سید*) or compound tokens (*طباطبایی نژاد*, *حسینی پور*, *شمس آبادی*) frequently suffer from partial boundary truncation (e.g. model redacts *سید علی* but leaves *طباطبایی نژاد* exposed).

### 4. Zero-Width Non-Joiner (ZWNJ, `\u200c`)
- Surnames and first names containing ZWNJs (*میرزایی‌فر*, *خانم‌زاده*, *علی‌رضا*) must not be broken into disconnected tokens or stripped during normalization.

### 5. Arabic vs. Persian Unicode Variants
- In Persian medical records, names are frequently keyed with Arabic letter variants: *على* (`U+064A`), *كريمى* (`U+0643`). Position-preserving normalization in `fa_redact.normalization` maps these 1-to-1 to Persian canonical code points (`ی`, `ک`), ensuring reliable detection while preserving exact string offsets.

### 6. Institution vs. Person Confusion
- Iranian hospitals, universities, highways, and foundations are universally named after historical or religious figures (e.g., *بیمارستان شهید بهشتی*, *دانشگاه امام صادق*, *بزرگراه حکیم*, *درمانگاه خاتم الانبیاء*).
- A naive entity detector frequently extracts the personal name from the facility name, improperly redacting "بیمارستان `[PERSON_1]`" instead of recognizing the facility as an institutional entity or leaving the public facility name intact.

---

## 10. Healthcare Domain Shift Analysis

All major publicly available Persian NER datasets (PEYMA, ARMAN, MultiNERD) are sourced from **news agencies and encyclopedic text**:

### The Domain Gap:
1. **Syntactic Differences:**
   - *News Domain:* Complete, grammatically structured sentences with formal syntax (*"وزیر بهداشت در مصاحبه مطبوعاتی روز گذشته در تهران اعلام کرد..."*).
   - *Clinical Domain:* Fragmented, telegraphic, non-standard clinical notes, bullet points, shorthand (*"بیمار خانم ۴۵ ساله با c/o درد قفسه سینه. شرح حال: فاطمه رضایی. ویزیت توسط دکتر کاظمی. تجویز: ASA 80mg روزانه."*).
2. **Mixed Language & Pharmacological Jargon:**
   - Clinical notes mix Latin-script medical terms, brand-name medications (*Atorvastatin*, *Metformin*), and transliterated Persian phonetics.
3. **Multi-Role Proximity:**
   - In a single outpatient note, multiple people may be referenced:
     - The Patient (*فاطمه حسینی*)
     - The Attending Physician (*دکتر بهرامی*)
     - The Referring Clinician (*دکتر سلیمانی*)
     - The Accompanying Family Member (*آقای حسینی، همسر بیمار*)

### Engineering Finding:
- **Substantial domain shift is plausible and expected** when transferring news-trained Persian NER models to clinical prose.
- **The exact numerical magnitude of this domain shift is UNKNOWN** from current evaluation, as no publicly available, gold-standard Persian clinical de-identification benchmark was executed in this phase.
- **Production clinical recall and precision cannot be inferred from news-domain benchmark scores.**

---

## 11. Privacy & Clinical Boundaries

In alignment with `fa-redact`'s core privacy policy:

1. **No Complete De-Identification Claim:**
   Detection of Persian personal names is an essential building block, but `fa-redact` does **not** claim complete clinical de-identification. Free-text clinical records may contain indirect identifiers (geographical locations, occupational descriptions, rare diseases, narrative life details) that are not captured by personal name detectors.
2. **No Regulatory Compliance Guarantees:**
   Use of `fa-redact` does not automatically confer compliance with HIPAA Safe Harbor, GDPR, or Iranian health data protection regulations. Organizations must independently audit and validate their end-to-end data processing pipelines.
3. **Role-Agnostic Detection:**
   A `PERSON` detector identifies personal names; it does **not** distinguish whether a detected name represents a patient, physician, nurse, family member, or historical figure. All detected person names are treated uniformly under the configured redaction or pseudonymization policy.

---

## 12. Architecture Options Comparison

| Architecture Option | Description | Core Dependency Impact | CPU & Memory Characteristics | Offset Integrity | Recommendation Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Option A: Heavy PyTorch in Core** | Bundle PyTorch + Hugging Face Transformers in `fa-redact` main dependencies | **FATAL** (`dependencies = ["torch", "transformers"]`) | Heavy disk and RAM footprint (>1.5 GB) | High | **REJECTED.** Violates zero-dependency core invariant. |
| **Option B: Rule-Based Heuristics in Core** | Static name dictionary + honorific regex in standard library | None (`dependencies = []`) | Minimal overhead | High | **REJECTED.** Unacceptable precision/recall on ambiguous/unseen names. |
| **Option C: Optional ONNX Runtime Adapter (`fa-redact[ner]`)** | Pre-quantized ParsBERT/DistilBERT ONNX model loaded via `onnxruntime` optional extra | None in core; optional extra | Expected to reduce memory and CPU footprint; requires prototype benchmarking | Exact | **CANDIDATE ARCHITECTURE.** Requires prototype validation for Python matrix compatibility. |
| **Option D: Optional Transformers Adapter (`fa-redact[ner-transformers]`)** | Hugging Face Transformers adapter for users already running PyTorch | None in core; optional extra | Standard PyTorch overhead | Exact | **CANDIDATE SECONDARY.** Flexible for existing PyTorch environments. |
| **Option E: Sidecar Service / Remote API** | External HTTP/gRPC server performing NER inference | None | Network overhead | Variable | **REJECTED for Core.** Violates offline, deterministic local execution principles. |

---

## 13. Three-Tier Metric Separation

To maintain rigorous transparency, metrics are strictly separated into three distinct categories:

### Tier A: Published / Literature-Reported Metrics (Primary Sources)

| Model Name / Checkpoint | Primary Source / Model Card | Evaluation Dataset | Overall Precision | Overall Recall | Overall F1 | PER / Person Specific Metrics |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `HooshvareLab/bert-fa-base-uncased-ner-peyma` | Hugging Face Model Card | PEYMA test set | Not reported separately | Not reported separately | **93.40%** (Dataset-wide) | Not reported separately on model card |
| `HooshvareLab/bert-fa-base-uncased-ner-arman` | Hugging Face Model Card | ARMAN test fold | Not reported separately | Not reported separately | **99.84%** (Dataset-wide) | Not reported separately on model card |
| `HooshvareLab/distilbert-fa-zwnj-base-ner` | Hugging Face Model Card | Combined Persian NER dataset | **94.63%** (`0.946326`) | **95.50%** (`0.955040`) | **95.07%** (`0.950663`) | **PER Precision: 95.98%** (`0.959818`), **PER Recall: 95.73%** (`0.957278`), **PER F1: 95.85%** (`0.958546`) |

### Tier B: Metrics Reproduced by this Phase 21 Research
- **Empirical Model Execution on Raw Corpus:** Real empirical model evaluation performed in Phase 21: **NO**.
- Phase 21 delivered the exact-span mathematical evaluation harness, synthetic challenge fixtures, and architectural/licensing research. It did **NOT** perform real empirical evaluation of model checkpoints on raw Persian corpora.
- Model suitability has **not** been empirically validated by this repository in this phase.

### Tier C: Synthetic Evaluator Sanity Checks (Harness Self-Test)
- **Evaluator Self-Test / Perfect-Prediction Sanity Check:**
  - Precision: **1.0 (100.0%)**
  - Recall: **1.0 (100.0%)**
  - F1: **1.0 (100.0%)**
  - False Positives: **0**
  - False Negatives: **0**
  - Evaluated on: 14 synthetic challenge fixtures ([`research/synthetic_fixtures.py`](file:///d:/fa-redact/research/synthetic_fixtures.py)).
  - **Explicit Note:** This score verifies that the evaluation harness computes exact-span metrics without mathematical defects when fed identical gold spans. **NO model accuracy or real-world performance is implied.**

---

## 14. Tooling & Challenge Fixtures

Phase 21 delivered standard-library-only evaluation tooling:

1. **Evaluation Module (`research/evaluation.py`):**
   - Entity-level exact-span precision, recall, and $F_1$ scoring.
   - Multi-document corpus aggregation with micro-averaging and per-entity-type breakdown.
   - Detailed error analysis categorizer (isolating boundary errors, type mismatches, false positives, and false negatives).
   - Strict duplicate gold rejection (`ValueError`) and configurable duplicate prediction penalization (`count_as_fp` or `reject`).
   - Zero external runtime dependencies (Python standard library only).
2. **Synthetic Challenge Fixtures (`research/synthetic_fixtures.py`):**
   - 14 distinct synthetic challenge test cases covering:
     - Standard single and full personal names
     - Compound surnames with prefixes and suffixes
     - Honorific and title prefixes (*دکتر*, *خانم مهندس*) — *note: title inclusion is an intentional challenge fixture boundary choice, contrasting with PEYMA's title exclusion policy*
     - Common-word / name homographs (*امید*, *بهار*, *پیروز*, *روشن*, *شریف*)
     - Zero-Width Non-Joiners (ZWNJ, `\u200c`)
     - Arabic character variants (*ي* / *ك*)
     - Punctuation and quotation boundaries
     - Names adjacent to National IDs and mobile numbers
     - Repeated names across a document
     - Synthetic clinical consultation notes
     - Negative controls (institutions named after people, clinical/pharmacological terms)
   - 100% synthetic, non-personal test data.
3. **Automated Unit Tests (`tests/test_ner_evaluation.py`):**
   - 30 unit tests verifying evaluation harness mathematical correctness, duplicate prediction policies, exact-span edge cases, deduplication, and synthetic fixture offset integrity.

---

## 15. Recommendation & Decision

### 15.1 Decision: CONDITIONAL GO ONLY FOR A DEDICATED EMPIRICAL BENCHMARK / PROTOTYPE SUB-PHASE

- **Research Foundation Status:** RESEARCH FOUNDATION COMPLETE, BUT NO-GO FOR PRODUCTION NER IMPLEMENTATION UNTIL A REAL REPRODUCIBLE MODEL BENCHMARK IS COMPLETED.
- **Phase 21 Empirical Scope:** Real empirical model evaluation performed in Phase 21: **NO**. Phase 21 delivered the exact-span mathematical evaluation harness, synthetic challenge fixtures, and architectural research. Phase 21 itself did **NOT** empirically establish real-world model quality.
- **Decision:** CONDITIONAL GO ONLY FOR A DEDICATED EMPIRICAL BENCHMARK / PROTOTYPE SUB-PHASE.
- **Production Decision:** NO-GO pending reproduced PERSON exact-span evaluation, offset validation, dependency compatibility, and clinical-domain evidence.
- **No Production Detector in Phase 21:** In strict compliance with Phase 21 gate criteria, no production `PersianNameDetector` is added to `src/fa_redact/detectors/` in this phase.

### 15.2 Next Sub-Phase Roadmap (Dedicated Benchmark / Prototype Sub-Phase)

The next sub-phase must begin with real model benchmarking before ONNX export or production detector implementation. The prescribed sequence is:

1. **Select Candidate Models:** Select one or two legally usable model candidates.
2. **Pin Revisions:** Pin exact model revisions.
3. **Obtain Local Held-Out Corpus:** Obtain legally usable held-out evaluation corpus locally.
4. **Run Actual Inference:** Run actual inference.
5. **Convert Predictions:** Convert BIO/BIOES predictions to entities.
6. **Reconstruct Character Offsets:** Reconstruct/verify exact original-text character offsets.
7. **Report PERSON Metrics:** Report PERSON:
   - True Positives (TP)
   - False Positives (FP)
   - False Negatives (FN)
   - Exact-span precision
   - Exact-span recall
   - Exact-span F1
8. **Perform Error Analysis:** Perform error analysis.
9. **Benchmark ONNX Export:** Only then benchmark/compare ONNX export if justified.
10. **Production Decision:** Only after that decide whether `PersianNERDetector` implementation is warranted.

---

## 16. References & Canonical Citations

1. **Poostchi, H., Zare Borzeshi, E., & Piccardi, M.** (2018). *BiLSTM-CRF for Persian Named Entity Recognition; ArmanPersoNERCorpus: The First Entity-Annotated Persian Dataset*. In Proceedings of the 11th Language Resources and Evaluation Conference (LREC 2018), ACL Anthology [L18-1701](https://aclanthology.org/L18-1701/).
2. **Shahshahani, M. S., Mohseni, M., Shakery, A., & Faili, H.** (2018). *PEYMA: A Tagged Persian Named Entity Recognition Corpus*. Laboratory for Systems and Cognitive Processing (LSCP), University of Tehran. [GitHub: LSCP-Lab/PEYMA](https://github.com/LSCP-Lab/PEYMA).
3. **Farahani, M., Gharachorloo, M., Farahani, M., & Manthouri, M.** (2021). *ParsBERT: Transformer-based Model for Persian Language Understanding*. Neural Computing and Applications, 33(21), 14213-14223. [Hugging Face: HooshvareLab/bert-fa-base-uncased-ner-peyma](https://huggingface.co/HooshvareLab/bert-fa-base-uncased-ner-peyma).
4. **HooshvareLab** (2021). *DistilBERT Persian ZWNJ NER*. [Hugging Face: HooshvareLab/distilbert-fa-zwnj-base-ner](https://huggingface.co/HooshvareLab/distilbert-fa-zwnj-base-ner).
5. **Qi, P., Zhang, Y., Zhang, Y., Bolton, J., & Manning, C. D.** (2020). *Stanza: A Python Natural Language Processing Toolkit for Many Human Languages*. In Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics: System Demonstrations. [Stanza Persian NER Documentation](https://stanfordnlp.github.io/stanza/ner_models.html).
6. **Tedeschi, S., & Navigli, R.** (2022). *MultiNERD: A Multilingual, Multi-Genre and Fine-Grained Dataset for Named Entity Recognition*. In Findings of NAACL 2022. [Hugging Face: Babelscape/multinerd](https://huggingface.co/datasets/Babelscape/multinerd).
7. **Pan, X., Zhang, B., May, J., Nothman, J., Knight, K., & Ji, H.** (2017). *Cross-lingual Name Tagging and Linking for 282 Languages*. In Proceedings of ACL 2017. [Hugging Face: unimelb-nlp/wikiann](https://huggingface.co/datasets/unimelb-nlp/wikiann).
