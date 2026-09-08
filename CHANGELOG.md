# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-09-08

### Added
- **Performance Profiling & Evidence-Based Optimization (Phase 33):**
  - Comprehensive empirical profiling deliverable (`research/phase33_performance.md`) and aggregate benchmark artifact (`research/results/phase33_performance.json`) measuring CPU latency, throughput, long-document sliding-window scaling, model initialization, and process resident memory (RSS) across lifecycle.
  - Evaluated zero-dependency deterministic core (`fa_redact.detect` with default detectors `IR_NATIONAL_ID`, `IR_MOBILE`, `IR_IBAN`): achieves 0.0321 ms median latency (26,171 docs/sec) on ~100-char documents, 0.1830 ms (5,291 docs/sec) on ~1,000-char documents, and 1.6441 ms (534 docs/sec) on ~10,000-char documents with 0 runtime dependencies, achieving approximately 2.8 million characters/sec on the measured synthetic workload.
  - Steady-state NER inference on Dataset B (150 documents): PEYMA PyTorch backend achieved 69.56 ms median latency (12.50 docs/sec, 215.88 tokens/sec); TookaBERT ONNX backend achieved 91.22 ms median latency (9.61 docs/sec, 222.82 tokens/sec; ~31.1% higher median latency / ~1.31x PEYMA latency).
  - Steady-state NER inference on Dataset C (120 clinical documents): PEYMA PyTorch backend achieved 124.08 ms median latency (7.43 docs/sec, 497.03 tokens/sec); TookaBERT ONNX backend achieved 370.60 ms median latency (2.64 docs/sec, 247.56 tokens/sec; ~198.7% higher median latency / ~2.99x PEYMA latency).
  - Documented tokenizer token-throughput limitation: PEYMA and TookaBERT use different tokenizers and produce different token counts for the same documents, so cross-backend `tokens/sec` is not a direct apples-to-apples speed comparison.
  - Long-document sliding-window scaling: verified linear scaling with sequence length across ~250, ~550, and ~1000 token documents (~2,125 ms for ~1000 tokens in PEYMA vs ~7,592 ms in TookaBERT ONNX).
  - Model initialization and memory footprints across lifecycle: PEYMA constructor requires ~6.4s cold start, 348.0 MiB post-load RSS, 714.8 MiB post-inference RSS, and 714.8 MiB peak RSS; TookaBERT ONNX constructor requires ~7.8s cold start, 728.9 MiB post-load RSS, 885.0 MiB post-inference RSS, and 887.9 MiB peak RSS.
  - Streaming batch processing helper: confirmed `fa_redact.detect_many()` demonstrates no material orchestration penalty on synthetic benchmarks across 6 counterbalanced repetitions (-8.59% observed difference vs explicit loop).
  - Recommendation rubric decision: `NO UNIVERSAL CPU PERFORMANCE WINNER` (on the measured Windows CPU environment and synthetic workloads, PEYMA had lower document latency and lower measured process memory than TookaBERT ONNX; ONNX retained as optional alternative for non-PyTorch environments; PEYMA recommended for reference PERSON quality and CPU speed).
  - Optimization gate decision: `NO PRODUCTION OPTIMIZATION JUSTIFIED` (no fa-redact-owned bottleneck was independently demonstrated, so the Phase 33 optimization eligibility gate was not satisfied).
  - Preserved all core invariants: zero modifications to `src/fa_redact/**`, zero new base runtime dependencies (`dependencies = []`), and package version remaining `0.3.0`.
  - Independent validation gate deliverable (`research/phase32_ner_validation.md`) evaluating both production `PERSON` backends: `PersianNERDetector` (PEYMA reference) and `ONNXPersianNERDetector` (TookaBERT ONNX candidate).
  - Executed reproducible benchmarks against synthetic Challenge Sets B (150 documents, 30 gold PERSON) and C (120 documents, 255 gold PERSON) using exact character-span matching.
  - PEYMA backend validated at 1.0000 Precision, 1.0000 Recall, and 1.0000 F1 on both Dataset B and Dataset C with zero false positives.
  - ONNX backend validated at 0.8485 Precision, 0.9333 Recall, 0.8889 F1 on Dataset B (exceeding Phase 29 wrapper baseline of 0.8710) and 1.0000 Precision, 1.0000 Recall, 1.0000 F1 on Dataset C.
  - Zero offset failures across all predictions and chunk boundaries; 100% adherence to `0 <= start < end <= len(text)` and `text[start:end] == d.value`.
  - Zero adapter/runtime errors across all evaluations.
  - Determinism verified: 100% identical predictions across 3 independent runs on sample documents.
  - Sliding-window long-document validation passed on ~256, ~512, and ~1000 token documents with 100% planted entity recall.
  - Negative-document false-positive rate: 0.0% for PEYMA and 1.67% for ONNX on Dataset B (2/120 documents); N/A on Dataset C (no PERSON-negative documents in Dataset C; 0 total PERSON false positives across Dataset C).
  - Overall gate decision: **PASS** (all 8 mandatory quality and integrity gates passed).
  - Production recommendation: PEYMA remains the validated reference PERSON backend; ONNX is a validated optional alternative; runtime/performance recommendations deferred to Phase 33.
  - Aggregate metadata-only results artifact saved at `research/results/phase32_ner_validation.json` with zero PII, snippets, or local workstation paths.
  - Strict research boundary maintained: zero modifications to `src/fa_redact/**`, zero new base dependencies (`dependencies = []`), and package version remaining `0.3.0`.
  - Added public detector `ONNXPersianNERDetector(model_path, *, max_length=512)` under `fa_redact.detectors` (and exported from top-level `fa_redact`) for local-only Persian `PERSON` named-entity recognition using ONNX Runtime.
  - Added strictly optional dependency extra `fa-redact[onnx]` (`onnxruntime>=1.16.0`, `transformers>=4.49.0,<5`) while keeping core package base dependencies empty (`dependencies = []`).
  - Strict local-only artifact resolution (`local_files_only=True`, `trust_remote_code=False`), rejecting network downloads or automatic Hugging Face Hub resolution.
  - Supported standard `PERSON`/`PER` BIO labels and fine-grained name components (`B-GIVENNAME`, `I-GIVENNAME`, `B-SURNAME`, `I-SURNAME`, `B-FIRSTNAME`, `B-LASTNAME`).
  - Conservative name reconstruction: merges adjacent compatible name components (`GIVENNAME` + `SURNAME`) separated only by whitespace/ZWNJ into single `PERSON` spans.
  - Excluded `TITLE` (e.g. `دکتر`, `مهندس`) strictly from `PERSON` detections.
  - Preserved separate evidence for distinct `B-PER` entities or names separated by punctuation, conjunctions, or context words.
  - Derived exact source character offsets directly from fast tokenizer offset mappings without document re-scanning.
  - Reused sliding-window principles for long documents exceeding `max_length` via internal shared helper `_ner_utils.py`, with bounded overlapping windows and deterministic candidate deduplication.
  - Maintained all core invariants: zero new base runtime dependencies (`dependencies = []`), default detectors unchanged (`_DEFAULT_DETECTORS` unchanged), clinical defaults unchanged, and package version remaining `0.3.0`.

- **Robust Long-Document Persian NER (Phase 30):**
  - Upgraded strictly opt-in `PersianNERDetector` to safely and deterministically process long Persian documents exceeding the configured sequence length (`max_length`).
  - Deterministic overlapping sliding-window inference with stride `max(1, (max_length - 2) // 2)` for inputs exceeding `max_length`.
  - Preserved single-pass fast path for sequences within `max_length` (100% backward compatible, zero overhead).
  - Exact source character offset reconstruction derived directly from fast tokenizer character offset mappings without document re-scanning or heuristic string searching.
  - Deterministic deduplication of identical and subsumed PERSON detections across overlapping windows.
  - Conservative boundary-split entity merging when fragments across window boundaries are separated by whitespace/ZWNJ and carry `I-PER` continuation labels or contiguous subwords.
  - Preserved distinct adjacent `B-PER` detections without incorrect boundary merging.
  - Zero mandatory runtime dependencies (`dependencies = []`), Python >=3.10 support, and package version remaining `0.3.0`.

- **Persian PII Ecosystem Audit & Independent Benchmark (Phase 29):**
  - Comprehensive empirical research audit (`research/phase29_persian_pii_ecosystem.md`) evaluating the Persian PII de-identification and NLP landscape across the OpenMed Persian / Reza2kn ecosystem (TookaBERT-Large ONNX INT4, Google mBERT ONNX INT4, 848k OpenPII dataset), ParsiKit 3.3.0 (MIT), py-persian-tools 0.0.11 (MIT), and `fa-redact` internal baselines.
  - Recorded supply-chain / maintenance risk observation regarding suspicious credential-collecting workflow on current GitHub master of `persian-tools/py-persian-tools` (commit `18aa49e`), distinct from audited PyPI 0.0.11 package.
  - Reproducible multi-dataset benchmark evaluating publisher-compatible reproduction vs. canonical exact-span metrics on OpenMed test split (Dataset A, 100 rows), an independent out-of-distribution challenge set (Dataset B, 150 documents), an Iranian clinical-style challenge set (Dataset C, 120 documents), long-document scaling (3 documents), and reproducibility.
  - Symmetrically mapped gold and prediction taxonomies with canonical TITLE/PERSON separation and deterministic address component policies.
  - Dedicated PERSON-only comparison showing current opt-in `PersianNERDetector` (PEYMA model) achieves 1.0000 Precision, 1.0000 Recall, and 1.0000 F1 on both Dataset B (30 entities) and Dataset C (255 entities) with zero false positives.
  - Empirical verification that `fa-redact` uniquely provides guaranteed 0 offset failures, pure Python zero-dependency execution, stateful reversible pseudonymization sessions, deterministic typed placeholders with cross-turn stable mappings, and clinical de-identification profiles.
  - Hard research boundary strictly maintained: 100% research-only deliverables, zero changes to production `src/fa_redact/`, zero new runtime dependencies (`dependencies = []`), no model bundled, no new detector enabled, and package version remaining `0.3.0`.

- **Opt-in Iranian Legal Entity National ID Implementation (Phase 28):**
  - Public validator `is_valid_iranian_legal_entity_id(value: str) -> bool` in `fa_redact.validators` and exported from top-level `fa_redact`.
  - Public detector `IranianLegalEntityIDDetector` with canonical entity type `IR_LEGAL_ENTITY_ID` in `fa_redact.detectors` and exported from top-level `fa_redact`.
  - Offline mathematical checksum implementation following the Phase 27 Variant A consensus formula (`[29, 27, 23, 19, 17, 29, 27, 23, 19, 17]`, `d[9] + 2`, modulo 11, remainder 10 $\to$ 0) with defensive rejection of all-identical 11-digit pseudo-values.
  - Position-preserving digit normalization supporting ASCII (`0-9`), Persian (`۰-۹`), Arabic-Indic (`٠-٩`), and mixed-script representations while preserving exact original source offsets and raw surface strings in `Detection.value`.
  - Strictly opt-in integration: `_DEFAULT_DETECTORS` remains strictly `(IranianNationalIDDetector, IranianMobileNumberDetector, IranianIBANDetector)` (3 default detectors).
  - Explicit detector composition: explicit `detectors=[IranianLegalEntityIDDetector()]` replaces defaults; composition with defaults requires explicit detector list.
  - Full pipeline, redaction, pseudonymization, reporting, serialization, batch, and structured helper compatibility.
  - Extended synthetic regression corpus in `research.detection_corpus` with dedicated `legal_entity_id` suite.
  - Zero network or registry lookups: purely offline structural and mathematical validation without SSAA/ILENC queries, active status verification, or network dependencies.
  - No official statutory checksum claim: documented as Variant A technical consensus from Phase 27 research.
  - Zero mandatory runtime dependencies (`dependencies = []`), Python >=3.10 support, and package version `0.3.0`.
- **Additional Iranian Identifier Research & Decision Gate (Phase 27):**
  - Comprehensive evidence review deliverable (`research/phase27_additional_iranian_identifiers.md`) evaluating four candidate Iranian identifier types: Legal Entity National ID (*شناسه ملی اشخاص حقوقی*), Iranian Postal Code (*کد پستی ده رقمی*), Company Registration Number (*شماره ثبت شرکت‌ها*), and Economic/Tax Identifier (*کد اقتصادی*).
  - Deterministic 8-dimension suitability scoring rubric and metadata-only decision artifact (`research/results/phase27_identifier_decision.json`) recording scores, blocker lists, and evidence counts without real identifiers or text dumps.
  - Standard-library-only research reference implementations (`research/legal_entity_id_reference.py`) resolving checksum algorithm disagreements across community implementations and confirming consensus prime-weight formula with 10th-digit offset against a manually checked public sample.
  - Hard constraint maintained: zero production source modifications (`src/fa_redact/`), no new detectors or validators added, no default detector changes, and zero new runtime dependencies (`dependencies = []`).
- **Privacy-Safe Structured Serialization (Phase 26):**
  - Standard-library-only serialization helpers `detection_to_dict()`, `detections_to_list()`, `report_to_dict()`, `reports_to_dict()`, `dumps_detections()`, `dumps_report()`, and `dumps_reports()` in `fa_redact.serialization` and exported from top-level `fa_redact`.
  - Explicit Detection structural metadata serialization (`type`, `start`, `end`) that is strictly value-free (never serializes raw `value` or `normalized_value`).
  - Explicit DetectionReport aggregate metadata serialization (`total_detections`, `counts`, `distinct_types`, `has_conflicts`, `conflict_pairs`, `conflicting_detections`, `duplicate_groups`) with value-free and span-free privacy guarantees.
  - Mapping serializer `reports_to_dict()` / `dumps_reports()` supporting field-level report mappings (such as outputs from `report_fields()`).
  - Deterministic JSON formatting with `ensure_ascii=False`, configurable indentation (default `2`), and exactly one trailing newline.
  - CLI `detect` and `report` subcommands refactored to reuse shared serialization helpers with byte-for-byte backward compatibility.
  - Zero mandatory runtime dependencies preserved in the base package (`dependencies = []`).
- **Synthetic Detector Evaluation Corpus & Benchmark Tooling (Phase 25):**
  - Standard-library-only, offline synthetic regression corpus (`SYNTHETIC_DETECTION_CORPUS`) and validation harness (`validate_detection_corpus`) in `research.detection_corpus`.
  - Immutable `SyntheticDetectionCase` research data model with exact character offsets, strict bounds checking, and duplicate span validation.
  - Safe substring span-builder helper `_span_for` for deterministic index resolution without source text rewriting.
  - Curated 100% synthetic test suites covering:
    - Default direct identifiers (`IR_NATIONAL_ID`, `IR_MOBILE`, `IR_IBAN`) with ASCII, Persian, and Arabic-Indic script variants, surrounding Persian prose, punctuation boundaries, and negative controls.
    - Opt-in `EMAIL` detection covering ASCII syntax, subdomains, and punctuation boundary variants.
    - Opt-in `BANK_CARD` detection covering 16-digit Luhn numbers across script variants and negative controls.
    - Configurable institutional `PatternRule` / `PatternDetector` fixtures (`MRN`, `PATIENT_ID`, contextual capture groups, and normalized digit matching).
    - Multi-identifier mixed documents with repeated and adjacent identifiers.
  - Offline benchmark runner (`research.detection_corpus_benchmark`) computing micro-averaged overall, per-type, and per-category exact-span metrics using existing `research.evaluation` functions.
  - Value-free, privacy-safe benchmark result serializer producing deterministic JSON metadata (`research/results/phase25_detection_corpus.json`) with zero text, raw value, timestamp, or system path leakage.
  - Zero runtime API modifications; top-level `fa_redact` exports and `src/fa_redact/` remain completely untouched.
- **Batch Processing Helpers (Phase 24):**
  - Lazy, streaming batch-processing helpers `detect_many()`, `redact_many()`, and `report_many()` in `fa_redact.batch` and exported from top-level `fa_redact`.
  - Sequential, one-document-at-a-time processing preserving exact input order without materializing the document collection in memory (`len()`, `list()`, or `tuple()` conversions are avoided).
  - Support for any Python `Iterable[str]` including generators, iterators, lists, tuples, and one-shot streams.
  - Immutable configuration snapshotting: caller-supplied mutable sequences (`detectors`, `type_priority`) are snapshotted to immutable tuples at helper invocation time, preventing caller mutations from affecting in-flight iteration.
  - Independent per-document redaction semantics: `redact_many()` treats each document as an independent call, restarting placeholder numbering from `1` per document without maintaining cross-document pseudonymization state.
  - Privacy-safe aggregate reporting: `report_many()` yields one value-free `DetectionReport` per document.
  - Zero mandatory runtime dependencies preserved in the base package (`dependencies = []`).

### Limitations
- **Detection Metadata Contains Offsets:** Detection structural serialization is value-free (never serializes `value` or `normalized_value`), but deliberately contains character offsets (`start`, `end`).
- **No Raw Value Export:** No opt-in parameters or flags exist to export raw or normalized detected identifier values.
- **No Deserialization:** Serialized detection metadata intentionally omits raw values and cannot reconstruct `Detection` objects; one-way serialization is enforced.
- **No Arbitrary Record Serializer:** The library does not serialize arbitrary or partially-redacted record mappings to prevent implying that unselected fields are privacy-safe.
- **No Pseudonymization Session Serialization:** `PseudonymizationSession.mapping` contains raw identifier associations and is not serializable.
- **No FHIR / HL7 Adapters:** Healthcare-specific interchange formats (FHIR, HL7, CDA) are excluded from this phase.
- **Synthetic Regression Boundary Only:** Phase 25 evaluation measures correctness against curated synthetic regression fixtures only; it makes no claims regarding real-world clinical recall, population-level precision, prevalence-adjusted accuracy, or regulatory compliance.
- **No Automatic Cross-Document Consistency:** `redact_many()` does not maintain or share a `PseudonymizationSession` across documents; use `PseudonymizationSession` explicitly if stable cross-document aliases are required.
- **No Whole-Batch Rollback:** Iterators stream results lazily; if an error occurs on document $N$, earlier yielded results remain valid and no batch-wide rollback is performed.
- **No NER Chunking:** Batch helpers process distinct documents; they do not partition single long documents into token windows or stitch overlapping NER inference chunks.
- **No Concurrency or Asynchronous Execution:** Processing is strictly sequential, synchronous, and deterministic.
- **No Filesystem / JSONL Batch Interfaces:** Batch helpers operate on in-memory/in-process Python iterables of strings only; directory traversal, globbing, and JSONL/CSV parsing are not included.
- **No Batch Aggregate Report:** `report_many()` yields one `DetectionReport` per input document; cross-document aggregate metrics are not computed in this phase.

## [0.3.0] - 2026-09-07

### Added
- **Clinical Redaction Profiles & Templates (Phase 22):**
  - High-level composition layer (`ClinicalRedactionProfile` and builder `clinical_profile`) composing built-in direct identifier detectors (`IranianNationalIDDetector`, `IranianMobileNumberDetector`, `IranianIBANDetector`), optional email (`EmailDetector`, default `True`), bank card (`BankCardDetector`, default `False`), institutional regex patterns (`PatternRule`), and optional person detectors (`person_detector`) into deterministic profiles.
  - Standardized clinical text template workflow presets: `outpatient_note`, `discharge_summary`, and `referral_letter` via `ClinicalTextTemplate` literal type.
  - Profile convenience methods delegating to core pipeline, transformation, and structured helpers (`detect`, `redact`, `report`, `detect_fields`, `redact_fields`, `report_fields`) with record-wide referential consistency and value-free reporting guarantees.
  - Public export of `ClinicalRedactionProfile`, `ClinicalTextTemplate`, and `clinical_profile` from `fa_redact` and `fa_redact.clinical`.
- **Experimental Opt-In Persian NER Detector (Phase 21.2):**
  - Opt-in `PersianNERDetector` performing local Persian personal name (`PERSON`) named entity recognition using explicitly supplied local Hugging Face-compatible token-classification model directories (`local_files_only=True`, `trust_remote_code=False`).
  - Optional `ner` dependency extra (`torch>=2.7.0,<3`, `transformers>=4.49.0,<5`) preserving zero mandatory runtime dependencies in the base package.
  - Exact source character offset extraction from position-preserving normalized text, slicing exact raw strings for `Detection.value` and aligned normalized strings for `Detection.normalized_value` without text distortion.
  - Structural tokenizer offset safety check verifying non-special token offsets are non-negative, bounded within text length, and monotonic.
  - Deterministic BIO to `PERSON` span reconstruction supporting subword merging, consecutive distinct `B-PER` entities, and leading `I-PER` recovery.
  - Privacy-safe fail-loud long-text policy raising `ValueError` on inputs exceeding configured/model max length without silent truncation.
  - Public export of `PersianNERDetector` from `fa_redact` and `fa_redact.detectors`.
- **Persian NER Research, Evaluation & Benchmark Infrastructure (Phases 21 & 21.1):**
  - Standard-library-only research evaluation harness (`research/evaluation.py`) computing exact-span entity-level precision, recall, and F1 with corpus micro-averaging and detailed error classification.
  - Synthetic Persian NER challenge set (`research/synthetic_fixtures.py`) containing 14 challenge fixtures covering multi-token compound surnames, honorifics, common-word/name homographs, ZWNJ variations, Arabic character variants, and clinical contexts.
  - Reproducible empirical benchmark runner (`research/persian_ner_benchmark.py`) reproducing exact-span `PERSON` metrics on the held-out PEYMA test split (1,026 sentences, 434 gold entities: TP=430, FP=3, FN=4, Precision=99.31%, Recall=99.08%, F1=99.19%, 0 offset mapping failures) with Apache-2.0 model checkpoint `HooshvareLab/bert-fa-base-uncased-ner-peyma`.
  - Comprehensive research deliverable (`research/phase21_persian_ner.md`) evaluating candidate models, corpora, licensing, optional packaging design (`fa-redact[ner]`), and healthcare domain shift.
- **Structured Data Helpers (Phase 20):**
  - Non-destructive processing of explicitly selected string paths within Python mappings/records: `detect_fields()`, `redact_fields()`, and `report_fields()`.
  - Dot-separated path navigation (e.g., `"note"`, `"meta.contact"`, `"patient.info.note"`) with strict path syntax validation and duplicate path rejection.
  - Record-wide referential consistency in `redact_fields()` across multiple targeted fields within a single record.
  - Non-destructive copying returning clean `dict[str, Any]` transformed records while preserving all non-target keys, numbers, booleans, None, lists, and unselected strings unchanged.
  - Public exports `detect_fields`, `redact_fields`, and `report_fields` from `fa_redact` and `fa_redact.structured`.
- **Command-Line Interface (Phase 19):**
  - Conservative, privacy-conscious command-line interface `fa-redact` via console script entry point and `python -m fa_redact` module entry point.
  - Subcommands `detect`, `report`, and `redact` across `stdin`/`stdout` streams and file paths.
  - Explicit `--detectors` selection across CLI subcommands, strictly replacing the default detector set with built-in (`national_id`, `mobile`, `iban`) or opt-in (`email`, `bank_card`) detectors.
  - Privacy-safe CLI error handling directing sanitized diagnostics to `stderr` without exposing input text, detected PII, or internal state.
  - In-place overwrite protection rejecting execution cleanly when input and output refer to the same file path.
- **Privacy-Safe Aggregate Detection Reports (Phase 18):**
  - Privacy-safe aggregate reporting model `DetectionReport` (frozen dataclass with slots) summarizing raw detection evidence without storing, returning, or persisting detected PII values, normalized values, text, spans, snippets, or PII hashes.
  - Pure aggregation function `report_detections(detections)` computing total detections, deterministic lexicographical type counts (`counts: Mapping[str, int]`), distinct entity types (`distinct_types`), conflict metrics (`has_conflicts`, `conflict_pairs`, `conflicting_detections`), and duplicate group counts (`duplicate_groups`).
  - High-level convenience helper `detection_report(text, *, detectors=None)` executing raw detection via `detect()` and returning an aggregate `DetectionReport` without automatic conflict resolution.
  - Public exports `DetectionReport`, `detection_report`, and `report_detections` from `fa_redact` and `fa_redact.reporting`.

### Important Behavior
- **Default Detectors Frozen:** Default detectors executed by `detect()`, `redact()`, and `PseudonymizationSession.pseudonymize()` remain strictly `(IranianNationalIDDetector, IranianMobileNumberDetector, IranianIBANDetector)`.
- **Opt-In Detectors:** `EmailDetector`, `BankCardDetector`, `PatternDetector`, and `PersianNERDetector` remain strictly opt-in and are never activated automatically in default pipelines.
- **Explicit Detector Overrides:** Explicit `detectors=[...]` arguments replace default detectors rather than merging with them; passing `detectors=[]` explicitly runs no detectors.
- **Conflict Default Policy:** Default transformation conflict policy remains `"reject"`; raw `detect()` continues preserving overlapping, nested, and duplicate evidence.
- **Zero Mandatory Dependencies:** Base `fa-redact` package preserves zero mandatory runtime dependencies (`dependencies = []`). Optional NER capabilities require `fa-redact[ner]`.

### Limitations
- **Clinical Profile Scope & Anti-Claims:** `ClinicalRedactionProfile` is a convenience composition layer; it does **not** guarantee complete clinical de-identification, HIPAA Safe Harbor compliance, GDPR compliance, or absence of residual identifiers. It does not perform role inference (patient, doctor, relative) and is not certified as a medical device.
- **Personal Name Detection Scope:** Personal name detection is not performed unless an explicit `person_detector` (such as `PersianNERDetector`) is supplied. News-domain benchmark results (PEYMA test split exact-span F1 = 99.19%) represent held-out journalistic corpus evidence and do not guarantee clinical PERSON extraction recall or universal Persian name accuracy.
- **Experimental NER Boundary:** `PersianNERDetector` is experimental and opt-in, requiring caller-supplied local model files (`local_files_only=True`). No models are bundled or automatically downloaded. Inputs exceeding model token length fail loudly rather than silently truncating.
- **Institutional & Clinical Identifiers:** No universal MRN, Patient ID, Encounter ID, date, date-of-birth, postal address, or health insurance number detectors are built in; institutional patterns require application-specific `PatternRule` definitions.
- **Structured Data Scope:** Structured data helpers target explicitly selected paths only and do not perform blind recursive scanning or automatic schema-level PII field inference.
- **CLI In-Place Editing:** CLI does not perform in-place destructive file editing; separate input and output destinations are required.
- **Metadata Visibility:** `DetectionReport` is value-free by design, but entity-type labels and aggregate counts are metadata; custom detector authors must keep `Detection.type` schema-level and avoid encoding sensitive data in type names.

## [0.2.0] - 2026-09-06

### Added
- Explicit detection conflict resolution function `resolve_detection_conflicts(detections, *, policy="reject", type_priority=None)` resolving overlapping, nested, and duplicate detections with deterministic output sorting by `(start, end, type)` (Phase 16).
- `ConflictPolicy` type alias supporting explicit policies: `"reject"`, `"longest"`, and `"priority"` (Phase 16).
- Explicit `reject` policy (conservative default) rejecting any overlapping, nested, or duplicate detections with privacy-safe error messages (Phase 16).
- Explicit `longest` policy greedily prioritizing longer spans, collapsing exact duplicate detections, and raising `ValueError` on ambiguous equal-length overlapping spans (Phase 16).
- Explicit `priority` policy resolving conflicts based on user-supplied entity type hierarchy (`type_priority`), requiring all conflicting entity types to have configured priority (Phase 16).
- `conflict_policy` and `type_priority` parameter support in `redact()` and `PseudonymizationSession.pseudonymize()` with atomic rollback on failure (Phase 16).
- Public root exports `ConflictPolicy` and `resolve_detection_conflicts` from the `fa_redact` package namespace (Phase 16).
- Configurable `PatternRule` immutable frozen dataclass supporting custom regex patterns, placeholder-safe entity types (`^[A-Z][A-Z0-9_]{0,63}$`), normalized/original source selection, integer and named capture-group span selection, and standard library `re` flags (Phase 15).
- `PatternDetector` executing user-configured `PatternRule` collections across source texts, caching compiled regular expressions once at initialization, and producing deterministic `Detection` sequences sorted by `(start, end, type)` (Phase 15).
- Institution-specific identifier detection (e.g. MRN, Patient ID, Admission ID, Encounter ID, Case ID) with position-preserving Persian and Arabic-Indic digit normalization support (Phase 15).
- Context-aware capture group support (`group=int` or `group=str`) enabling prefix/context matching while isolating identifier spans (Phase 15).
- Opt-in pattern detection support in `detect()`, `redact()`, and `PseudonymizationSession.pseudonymize()` via explicit `detectors=[PatternDetector(...)]` usage (Phase 15).
- Public root exports `PatternDetector` and `PatternRule` from the `fa_redact` package namespace (Phase 15).
- 16-digit payment card (PAN) validator (`is_valid_bank_card_number`) supporting compact 16-digit electronic format with standard Luhn checksum validation and defensive all-identical digit sequence rejection (Phase 14).
- `BankCardDetector` scanning position-preserving normalized text for 16-digit candidate sequences and producing `BANK_CARD` detections with Persian and Arabic-Indic digit support (Phase 14).
- Opt-in bank card detection support in `detect()`, `redact()`, and `PseudonymizationSession.pseudonymize()` via explicit `detectors=[BankCardDetector()]` usage (Phase 14).
- Typed `[BANK_CARD_<INDEX>]` placeholder generation during redaction and pseudonymization when `BankCardDetector` is explicitly enabled (Phase 14).
- Public root exports `BankCardDetector` and `is_valid_bank_card_number` from the `fa_redact` package namespace (Phase 14).
- Iranian IBAN (Sheba) validator (`is_valid_iranian_iban`) supporting compact electronic format (`IR` + 24 digits = 26 characters) with streaming MOD-97 checksum validation (Phase 13).
- `IranianIBANDetector` scanning position-preserving normalized text for Iranian IBAN candidates and producing `IR_IBAN` detections with Persian and Arabic-Indic digit support (Phase 13).
- Inclusion of `IranianIBANDetector` in the default detector set across `detect()`, `redact()`, and `PseudonymizationSession` (Phase 13).
- Typed `[IR_IBAN_<INDEX>]` placeholder generation during redaction and pseudonymization with cross-script entity identity normalization (Phase 13).
- Public root exports `IranianIBANDetector` and `is_valid_iranian_iban` from the `fa_redact` package namespace (Phase 13).
- Conservative ASCII Internet Email address validator (`is_valid_email`) supporting dot-atom local parts and DNS-style domain names up to 254 characters (Phase 12).
- `EmailDetector` scanning original source text for ASCII email candidates and producing `EMAIL` detections (Phase 12).
- Opt-in email detection support in `detect()`, `redact()`, and `PseudonymizationSession.pseudonymize()` via explicit `detectors=[EmailDetector()]` usage (Phase 12).
- Typed `[EMAIL_<INDEX>]` placeholder generation during redaction and pseudonymization when `EmailDetector` is explicitly enabled (Phase 12).
- Public root exports `EmailDetector` and `is_valid_email` from the `fa_redact` package namespace (Phase 12).

### Changed
- Note: Default conflict policy across `redact()` and `PseudonymizationSession.pseudonymize()` remains `reject`; `detect()` behavior is unchanged and continues preserving raw overlapping and duplicate detections (Phase 16).
- Note: No universal MRN, Patient ID, Encounter ID, or other institution-specific patterns are built in; `PatternDetector` is strictly opt-in and requires application-supplied rules (Phase 15).
- Note: `BankCardDetector` and `EmailDetector` remain strictly opt-in in Phase 14/15 and are not included in the default detector set to prevent unhandled overlaps and avoid false positives on generic numeric sequences without BIN/issuer context (Phase 14/15).
- No BIN/IIN lookup or issuer verification is performed; validation confirms structural 16-digit format and Luhn checksum only (Phase 14).
- `_DEFAULT_DETECTORS` pipeline set remains `(IranianNationalIDDetector, IranianMobileNumberDetector, IranianIBANDetector)` (Phase 13/14/15/16).

## [0.1.0] - 2026-09-05

### Fixed
- Prevent cross-call placeholder collisions in `PseudonymizationSession` by reserving placeholder-shaped literal tokens observed across current and historical inputs, preventing subsequent aliases from colliding with prior literal text while maintaining atomic state updates (Phase 8.1).

### Added
- `PseudonymizationSession` stateful class with `pseudonymize()`, `restore()`, and `mapping` snapshot property (Phase 8).
- Stable cross-call entity mapping and per-type counter persistence across multiple messages in a session (Phase 8).
- First-observed raw representation retention as semantic restoration target (Phase 8).
- Single-pass non-cascading regex restoration preventing recursive placeholder evaluation (Phase 8).
- Atomic session state updates ensuring partial failures leave session state completely untouched (Phase 8).
- Session isolation guaranteeing separate `PseudonymizationSession` instances maintain distinct states (Phase 8).
- Public export of `PseudonymizationSession` from root `fa_redact` package namespace (Phase 8).
- Safe placeholder-based redaction function `redact(text, *, detectors=...)` replacing detected PII spans with deterministic typed placeholders (Phase 7).
- Referential consistency in `redact()` mapping matching `(type, normalized_value)` pairs to identical placeholders within a single call (Phase 7).
- Original placeholder collision avoidance skipping pre-existing literal placeholder substrings (Phase 7).
- Explicit overlap and duplicate rejection raising privacy-conscious `ValueError` without leaking PII values or surrounding text (Phase 7).
- Public export of `redact` from root `fa_redact` package namespace (Phase 7).
- High-level detection pipeline function `detect(text, *, detectors=...)` orchestrating position-preserving text normalization and entity detector execution (Phase 6).
- Public export of `detect` and `Detector` protocol at the root `fa_redact` package namespace (Phase 6).
- Deterministic multi-detector result sorting by source-text character offset and entity type `(start, end, type)` (Phase 6).
- Iranian mobile number validator (`is_valid_mobile_number`) supporting domestic, `+98`, and `0098` formats with official 2026 CRA mobile NDC prefix validation (Phase 5).
- `IranianMobileNumberDetector` detecting domestic and international mobile candidates in position-preserving normalized text and generating `IR_MOBILE` detections (Phase 5).
- Strict Iranian National ID (Code Melli) modulo-11 checksum validator (`is_valid_national_id`) supporting ASCII, Persian, and Arabic-Indic digit formats (Phase 4).
- `IranianNationalIDDetector` scanning position-preserving normalized text for 10-digit candidates and generating `IR_NATIONAL_ID` detections (Phase 4).
- Immutable `Detection` data model preserving raw and normalized value representations, with span validation and `from_texts()` safe factory (Phase 3).
- `Detector` structural typing protocol defining standard contract for entity detectors (Phase 3).
- Position-preserving Persian and Arabic-Indic text normalization (`normalize_digits`, `normalize_letters`, `normalize_text`) preserving exact Unicode string lengths and offsets (Phase 2).
- Initial project foundation and repository scaffolding (Phase 1).
- Package metadata and build configuration in `pyproject.toml` with `src/` layout.
- Version export `fa_redact.__version__`.
- Type marker (`py.typed`) and static typing configuration (`mypy`).
- Linting and code formatting configuration (`ruff`).
- Initial unit tests and test framework setup (`pytest`).
- Initial documentation and MIT license.
