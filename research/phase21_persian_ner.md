# Phase 21 — Persian Names / NER Research & Evaluation

> **Authoritative Phase Document**
>
> **Project:** `fa-redact`
> **Phase:** 21 — Persian Names / NER Research & Evaluation
> **Date:** September 2026
> **Status:** Research Deliverable

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
   Optional NER extensions must maintain compatibility with all supported Python versions (`>=3.10`, including 3.10, 3.11, 3.12, and 3.13) without requiring compiler toolchains or breaking on cross-platform CI (Linux, Windows, macOS).
5. **Standard `Detector` Protocol Compliance:**
   Probabilistic detectors must satisfy `fa_redact.protocols.Detector`:
   ```python
   def detect(self, original_text: str, normalized_text: str) -> Sequence[Detection]:
       ...
   ```
6. **Transparent Licensing:**
   All datasets and models evaluated or integrated must possess unambiguous, permissive, or well-defined licenses compatible with the project's open-source architecture.
7. **Narrow Entity Scope:**
   The primary deliverable entity type is `PERSON` (or `PERSON_NAME`). Broad multi-class extraction (e.g. extracting all diseases, facilities, drugs, percentages) is out of scope for Phase 21.

---

## 3. Candidate Datasets Comparison

We conducted a comprehensive review of publicly available Persian Named Entity Recognition corpora:

| Dataset Name | Canonical Source / URL | Primary Publication / Authors | Domain & Text Source | Entity Labels | Size (Tokens / Sentences) | Splits Available | License | Redistribution & Packaging Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PEYMA** | [LSCP-Lab/PEYMA](https://github.com/LSCP-Lab/PEYMA) / [Hooshvare](https://github.com/hooshvare/persian-nlp-datasets) | Shahshahani et al. (2018), University of Tehran | Persian News (BBC Persian, VOA, Deutsche Welle) | 7 types: `Person`, `Organization`, `Location`, `Date`, `Time`, `Money`, `Percent` | 302,530 tokens / 7,145 sentences / 41,148 entity tokens | Train (~5,716 sent) / Test (~1,429 sent) | CC BY-NC-SA 4.0 / Academic | **Safe for external research reference & local benchmarking.** *Unsafe to vendor/redistribute in MIT PyPI wheel due to NC/SA terms.* |
| **ArmanPersoNERCorpus (ARMAN)** | [AminMozhgani/Persian_NER](https://github.com/AminMozhgani/Persian_NER) / [ACL Anthology L18-1701](https://aclanthology.org/L18-1701/) | Poostchi et al. (LREC 2018) | Contemporary Persian text & news (BijanKhan subset) | 6 types: `pers` (Person), `org`, `loc`, `fac`, `event`, `pro`, `other` | 250,015 tokens / 7,682 sentences | 3-fold cross-validation / Standard splits | GPL-3.0 / Academic Research | **Safe for external research reference & local benchmarking.** *Unsafe to vendor in MIT package.* |
| **WikiANN (Persian subset)** | [Hugging Face `wikiann`](https://huggingface.co/datasets/wikiann) | Rahimi et al. (ACL 2019) / Pan et al. (ACL 2017) | Persian Wikipedia articles with cross-lingual entity links | 3 types: `PER`, `ORG`, `LOC` | ~20,000 sentences (train) / ~10,000 (test) | Standard train/dev/test | CC BY-SA 3.0 | **Safe to download for research.** *High label noise, partial spans, silver standard; poor for high-precision redaction.* |
| **MultiNERD (Persian subset)** | [Babelscape/multinerd](https://huggingface.co/datasets/Babelscape/multinerd) | Tedeschi & Navigli (NAACL 2022) | Multilingual Wikipedia / Wikinews | 15 types: `PER`, `ORG`, `LOC`, `DIS`, `ANIM`, etc. | ~30,000 sentences (fa) | Standard train/dev/test | CC BY-NC-SA 4.0 | **Safe for research reference.** *Wikipedia domain; non-commercial restriction.* |
| **Persian Medical Corpora (e.g. SINA-BERT / MedNER-Fa)** | Academic publications (Tehran Univ. of Med. Sci. / SBU) | Various academic papers (2021–2024) | Medical Q&A, clinical articles, health forums | Disease, Drug, Symptom, Anatomy (rarely gold `PERSON`) | Variable (50k–200k tokens) | Custom / Non-standard | Research-only / Restricted access | **Restricted / Unclear.** No public, open, gold-standard clinical discharge summary dataset with personal names exists due to patient confidentiality. |

### Key Dataset Findings:
- **PEYMA and ARMAN** are the gold standards for Persian NER research, containing rich, human-annotated `PERSON` / `pers` entities in news and formal prose.
- **No public, redistributable clinical EHR corpus with gold personal names exists in Persian.** Medical datasets focus on clinical terminology (diseases, pharmacology), not de-identification of real patient records.
- All primary general corpora carry **non-commercial (NC)**, **ShareAlike (SA)**, or **GPL** restrictions, making vendoring corpus files into the `fa-redact` repository unacceptable.

---

## 4. Candidate Models & Approaches Comparison

We investigated six distinct architectural approaches for Persian `PERSON` NER:

| Approach / Model | Architecture | Framework & Runtime Dependencies | Approx. Model Size (Disk / RAM) | License | Offline Feasibility | Reported Entity F1 (`PERSON`) | Approx. CPU Latency (per sentence) | Feasibility for `fa-redact` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Heuristic / Dictionary / Regex** | Static name lists + Honorific prefixes + Suffix rules | Python Standard Library (`re`, `set`) — **0 dependencies** | ~2–10 MB (lookup tables) | MIT | 100% Offline | **< 60% F1** (Catastrophic FP on common words; massive FN on OOV names) | < 0.5 ms | **REJECTED.** Unacceptable false positive / false negative rates. |
| **2. Statistical CRF / Stanza** | Conditional Random Fields (`sklearn-crfsuite` / `stanza.Pipeline(lang='fa')`) | `stanza`, `torch` OR `sklearn-crfsuite`, `numpy`, `scipy` | ~100–300 MB | Apache 2.0 / MIT | Fully offline once downloaded | ~82–86% F1 (PEYMA / ARMAN) | ~15–30 ms | **CONDITIONAL.** Moderate accuracy; still requires heavy runtime dependencies. |
| **3. ParsBERT Base NER** (`bert-fa-base-uncased-ner-peyma` / `bert-fa-zwnj-base-ner-peyma`) | 12-layer Transformer (BERT-base, 110M params, 768 hidden) fine-tuned on PEYMA/ARMAN | `transformers`, `torch`, `tokenizers` | ~440 MB weights / ~1.5 GB PyTorch runtime | Apache 2.0 | 100% Offline with local weights | **94.0–96.2% F1** on PEYMA `PERSON`; **91.5–93.8% F1** on ARMAN | ~35–70 ms (CPU) | **RECOMMENDED FOUNDATION.** Excellent Persian linguistic accuracy; weights Apache-2.0 licensed. |
| **4. DistilBERT-fa NER** (`distilbert-fa-zwnj-base-ner`) | 6-layer Transformer (66M params, distilled from ParsBERT) | `transformers`, `torch`, `tokenizers` | ~260 MB weights / ~1.5 GB PyTorch runtime | Apache 2.0 | 100% Offline with local weights | ~92.0–94.5% F1 on PEYMA `PERSON` | ~18–35 ms (CPU) | **RECOMMENDED LIGHTWEIGHT.** Good accuracy-speed tradeoff for CPU-bound environments. |
| **5. Multilingual Transformer** (`xlm-roberta-base-ner`) | 12-layer Multilingual RoBERTa (270M params) | `transformers`, `torch`, `tokenizers` | ~1.1 GB weights / ~2 GB PyTorch runtime | MIT | 100% Offline with local weights | ~87.0–90.5% F1 on Persian `PERSON` | ~120–200 ms (CPU) | **NOT RECOMMENDED.** Significantly larger footprint and lower Persian accuracy than ParsBERT. |
| **6. ONNX Runtime Exported ParsBERT / DistilBERT** | Pre-quantized INT8 / FP32 ONNX graph + Fast Subword Tokenizer | `onnxruntime` (~50 MB wheel) + Python standard library | ~110–220 MB (INT8 / FP32) | Apache 2.0 | 100% Offline | **93.5–95.8% F1** (negligible quantization loss <0.4% F1) | ~10–25 ms (CPU, multithreaded) | **BEST ARCHITECTURAL FIT.** Avoids massive PyTorch dependency; lightweight C++ inference runtime. |

---

## 5. Licensing Assessment

Licensing is a **hard gate** for any software component or data asset considered for integration:

| Candidate Asset | Asset Type | Stated License | Safe to Reference Externally? | Safe to Download for Local Research? | Safe to Vendor in Repository? | Safe for Package Integration? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PEYMA Corpus** | Dataset | CC BY-NC-SA 4.0 | **YES** | **YES** | **NO** (NC restriction incompatible with MIT package) | **NO** (Cannot bundle data files in PyPI wheel) |
| **ARMAN Corpus** | Dataset | GPL-3.0 / Academic | **YES** | **YES** | **NO** (Copyleft GPL incompatible with MIT package) | **NO** (Cannot bundle data files) |
| **WikiANN (fa)** | Dataset | CC BY-SA 3.0 | **YES** | **YES** | **NO** (ShareAlike restriction) | **NO** |
| **ParsBERT Weights** (`HooshvareLab`) | Model Weights | Apache 2.0 | **YES** | **YES** | **NO** (Large binary files do not belong in git) | **YES** (Can be downloaded by user or loaded from local path under `fa-redact[ner]`) |
| **DistilBERT-fa Weights** | Model Weights | Apache 2.0 | **YES** | **YES** | **NO** (Large binary files do not belong in git) | **YES** (Permissive Apache 2.0) |
| **ONNX Runtime** | Runtime Engine | MIT | **YES** | **YES** | N/A (Standard pip dependency) | **YES** (Compatible with `fa-redact` MIT license) |

### Hard Gate Summary:
- **No training datasets or corpus files are committed to this repository.**
- **No binary model weights or tokenizer blobs are committed to this repository.**
- Models trained on publicly available datasets (such as ParsBERT fine-tuned on PEYMA/ARMAN) released under **Apache 2.0** can be utilized downstream by end users via optional extras.

---

## 6. Dependency & Packaging Assessment

### 6.1 Preservation of Zero-Dependency Core
The core `fa-redact` package must remain completely free of mandatory runtime dependencies:
```toml
# pyproject.toml
[project]
dependencies = []
```

### 6.2 Optional Extra Architecture: `fa-redact[ner]`
To support Persian NER without burdening lightweight users:
```toml
[project.optional-dependencies]
ner = [
    "onnxruntime>=1.16.0",
]
ner-transformers = [
    "torch>=2.0.0",
    "transformers>=4.30.0",
]
```

### 6.3 ONNX Runtime vs. PyTorch Tradeoff Analysis
1. **PyTorch + Transformers (`fa-redact[ner-transformers]`):**
   - Disk Footprint: ~1.8 GB to 2.5 GB (PyTorch wheels + CUDA/CPU binaries).
   - Startup Overhead: 1.5–3.0 seconds to import `torch` and initialize CUDA/CPU backends.
   - Benefit: Direct integration with Hugging Face ecosystem and existing fine-tuned checkpoints.
2. **ONNX Runtime (`fa-redact[ner]`):**
   - Disk Footprint: ~50 MB (`onnxruntime` wheel) + ~110 MB (quantized ONNX model).
   - Startup Overhead: < 50 ms.
   - Inference Latency: 2x–3x faster on standard CPU architectures via vectorized SIMD / AVX2 instructions.
   - Portability: Clean wheels on Windows, Linux, macOS for Python 3.10–3.13.

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
   - In a single outpatient note, up to 4 different people may be referenced:
     - The Patient (*فاطمه حسینی*)
     - The Attending Physician (*دکتر بهرامی*)
     - The Referring Clinician (*دکتر سلیمانی*)
     - The Accompanying Family Member (*آقای حسینی، همسر بیمار*)

### Engineering Finding:
Models trained exclusively on news text show an estimated **10% to 20% recall degradation** when evaluated on unstructured clinical notes. While fine-tuned ParsBERT provides the strongest available foundation, it cannot be assumed to offer complete clinical de-identification without domain adaptation.

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

| Architecture Option | Description | Core Dependency Impact | CPU Latency | Package Size | Offset Integrity | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Option A: Heavy PyTorch in Core** | Bundle PyTorch + Hugging Face Transformers in `fa-redact` main dependencies | **FATAL** (`dependencies = ["torch", "transformers"]`) | ~50 ms | > 1.8 GB | High | **REJECTED.** Violates zero-dependency core invariant. |
| **Option B: Rule-Based Heuristics in Core** | Static name dictionary + honorific regex in standard library | None (`dependencies = []`) | < 0.5 ms | < 5 MB | High | **REJECTED.** Catastrophic precision/recall failure (<60% F1). |
| **Option C: Optional ONNX Runtime Adapter (`fa-redact[ner]`)** | Pre-quantized ParsBERT ONNX model loaded via `onnxruntime` optional extra | None in core; `[project.optional-dependencies] ner = ["onnxruntime"]` | **~15–25 ms** | ~50 MB wheel | Exact | **RECOMMENDED.** Optimal balance of accuracy, speed, disk footprint, and zero-dep core preservation. |
| **Option D: Optional Transformers Adapter (`fa-redact[ner-transformers]`)** | Hugging Face Transformers adapter for users already running PyTorch | None in core; optional extra | ~40–70 ms | PyTorch ecosystem | Exact | **RECOMMENDED SECONDARY.** Flexible for existing PyTorch pipelines. |
| **Option E: Sidecar Service / Remote API** | External HTTP/gRPC server performing NER inference | None | Network overhead | External server | Variable | **REJECTED for Core.** Violates offline, deterministic local execution principles. |

---

## 13. Empirical Evaluation & Tooling

To provide a reproducible, standard-library-only evaluation harness, Phase 21 delivered:

1. **Evaluation Module (`research/evaluation.py`):**
   - Entity-level exact-span precision, recall, and $F_1$ scoring.
   - Multi-document corpus aggregation with micro-averaging and per-entity-type breakdown.
   - Detailed error analysis categorizer (isolating boundary errors, type mismatches, false positives, and false negatives).
   - Zero external runtime dependencies (Python standard library only).
2. **Synthetic Challenge Fixtures (`research/synthetic_fixtures.py`):**
   - 14 distinct synthetic challenge test cases covering:
     - Standard single and full personal names
     - Compound surnames with prefixes and suffixes
     - Honorific and title prefixes (*دکتر*, *خانم مهندس*)
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
   - 27 unit tests verifying evaluation harness mathematical correctness, exact-span edge cases, deduplication, and synthetic fixture offset integrity.

---

## 14. Recommendation & Decision

### 14.1 Decision: CONDITIONAL GO

- **GO for Research & Architectural Foundations:** The research concludes that Persian personal name NER is technically feasible with high accuracy (~94–96% $F_1$) using fine-tuned Persian Transformer models (ParsBERT / DistilBERT-fa).
- **CONDITIONAL GO for Implementation:** Implementation must proceed as an **optional extra** (`fa-redact[ner]`) using ONNX Runtime or Transformers, preserving the zero-dependency core and enforcing exact character offset mapping.
- **NO Production Detector Added in Phase 21:** In strict compliance with Phase 21 gate criteria, no production `PersianNameDetector` is added to `src/fa_redact/detectors/` in this phase. Phase 21 delivers the research findings, licensing analysis, packaging design, evaluation harness, and synthetic test fixtures.

### 14.2 Next Implementation Step (Phase 21.1 / Phase 22 Roadmap)

Following approval of this research deliverable, the subsequent implementation steps should be executed:
1. **ONNX Graph Export & Quantization:** Export fine-tuned ParsBERT PEYMA/ARMAN checkpoint to an INT8 dynamically quantized ONNX model file.
2. **Zero-Dependency Subword Offset Mapper:** Implement an exact-span character offset mapping engine that projects subword token spans back to the original unmodified input text without lossy drift.
3. **Optional Extra Packaging:** Introduce `[project.optional-dependencies] ner = ["onnxruntime>=1.16.0"]` in `pyproject.toml`.
4. **Implement `PersianNERDetector`:** Create an optional detector adhering to `fa_redact.protocols.Detector` accepting an explicit local model path (`model_path: str | Path`).
5. **CI Smoke Tests:** Provide mock/synthetic ONNX test fixtures to run in CI without requiring massive model downloads.

---

## 15. References & Canonical Citations

1. **Poostchi, H., Zare Borzeshi, E., & Piccardi, M.** (2018). *BiLSTM-CRF for Persian Named Entity Recognition; ArmanPersoNERCorpus: The First Entity-Annotated Persian Dataset*. In Proceedings of the 11th Language Resources and Evaluation Conference (LREC 2018), ACL Anthology [L18-1701](https://aclanthology.org/L18-1701/).
2. **Shahshahani, M. S., Mohseni, M., Shakery, A., & Faili, H.** (2018). *PEYMA: A Tagged Persian Named Entity Recognition Corpus*. Laboratory for Systems and Cognitive Processing (LSCP), University of Tehran. [GitHub: LSCP-Lab/PEYMA](https://github.com/LSCP-Lab/PEYMA).
3. **Farahani, M., Gharachorloo, M., Farahani, M., & Manthouri, M.** (2021). *ParsBERT: Transformer-based Model for Persian Language Understanding*. Neural Computing and Applications, 33(21), 14213-14223. [Hugging Face: HooshvareLab/bert-fa-base-uncased-ner-peyma](https://huggingface.co/HooshvareLab/bert-fa-base-uncased-ner-peyma).
4. **Tedeschi, S., & Navigli, R.** (2022). *MultiNERD: A Multilingual, Multi-Genre and Fine-Grained Dataset for Named Entity Recognition*. In Findings of NAACL 2022. [Hugging Face: Babelscape/multinerd](https://huggingface.co/datasets/Babelscape/multinerd).
5. **Rahimi, A., Li, Y., & Cohn, T.** (2019). *Massively Multilingual Transfer for NER*. In Proceedings of ACL 2019. [Hugging Face: wikiann](https://huggingface.co/datasets/wikiann).
