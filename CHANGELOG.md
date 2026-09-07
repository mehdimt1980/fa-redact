# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Batch Processing Helpers (Phase 24):**
  - Lazy, streaming batch-processing helpers `detect_many()`, `redact_many()`, and `report_many()` in `fa_redact.batch` and exported from top-level `fa_redact`.
  - Sequential, one-document-at-a-time processing preserving exact input order without materializing the document collection in memory (`len()`, `list()`, or `tuple()` conversions are avoided).
  - Support for any Python `Iterable[str]` including generators, iterators, lists, tuples, and one-shot streams.
  - Immutable configuration snapshotting: caller-supplied mutable sequences (`detectors`, `type_priority`) are snapshotted to immutable tuples at helper invocation time, preventing caller mutations from affecting in-flight iteration.
  - Independent per-document redaction semantics: `redact_many()` treats each document as an independent call, restarting placeholder numbering from `1` per document without maintaining cross-document pseudonymization state.
  - Privacy-safe aggregate reporting: `report_many()` yields one value-free `DetectionReport` per document.
  - Zero mandatory runtime dependencies preserved in the base package (`dependencies = []`).

### Limitations
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
