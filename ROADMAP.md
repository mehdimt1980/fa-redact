# fa-redact Roadmap

> This roadmap outlines past milestones, current unreleased development, and planned future phases.
> For current branch state and development workflow, see [PROJECT_STATUS.md](PROJECT_STATUS.md).

---

## Roadmap Principles

- **Privacy-First Architecture:** Minimize risk of data exposure at every layer. Value-free reporting, sensitive mapping isolation, and leak-free error handling are fundamental defaults.
- **Deterministic & Offline Behavior:** Detection and redaction must produce reproducible, predictable outputs without relying on network lookups or external cloud services.
- **Conservative Defaults:** Fail-loud on unhandled ambiguities (e.g., `conflict_policy="reject"` by default) rather than guessing user intent.
- **Standard-Library-Only Core:** The core `fa-redact` package maintains zero external runtime dependencies.
- **Optional Dependencies Only When Justified:** Any heavy ML, NLP, or framework integrations must remain strictly optional extras and must not compromise core lightweight execution.
- **Incremental & Phased Delivery:** Every major phase is implemented in an isolated branch, covered by thorough tests, reviewed in a single PR, and verified on CI before closing.
- **Clear Regulatory & Clinical Boundaries:** Anti-claims are maintained rigorously. We do not claim automated HIPAA/GDPR compliance, medical device certification, or complete clinical de-identification.

---

## Released Foundation

### v0.1.0 — Foundation & Direct Identifiers
*Status: `RELEASED` (Published on PyPI and GitHub Releases)*

Established the project baseline, core architecture, and first Iranian direct identifier detectors:

- **Phase 1 — Package Foundation:** Scaffolding, `pyproject.toml`, packaging layout, type marker (`py.typed`), linting/formatting configs.
- **Phase 2 — Position-Preserving Normalization:** 1-to-1 Unicode character mapping for Persian/Arabic digits and letter variants without string length change (`len(normalized) == len(original)`).
- **Phase 3 — Detection Model & Protocol:** Immutable `Detection` dataclass preserving raw/normalized values and offsets; `Detector` structural typing protocol.
- **Phase 4 — Iranian National ID:** Strict 10-digit modulo-11 checksum validator (`is_valid_national_id`) and detector (`IranianNationalIDDetector`).
- **Phase 5 — Iranian Mobile Number:** 2026 CRA National Numbering Plan prefix validator (`is_valid_mobile_number`) and detector (`IranianMobileNumberDetector`).
- **Phase 6 — High-Level Pipeline:** `detect()` orchestrating normalization, multi-detector aggregation, and deterministic sorting `(start, end, type)`.
- **Phase 7 — Stateless Redaction:** `redact()` replacing detected spans with typed placeholders, referential consistency, and literal collision avoidance.
- **Phase 8 — Stateful Pseudonymization:** `PseudonymizationSession` managing cross-turn entity persistence, atomic state updates, and single-pass non-cascading `restore()`.
- **Phase 8.1 — Historical Literal Token Reservation:** Collision prevention across multi-turn session calls.
- **Phase 9 — CI & Release Readiness:** Matrix testing (Python 3.10–3.13), quality checks, and twine validation.
- **Phase 10 — Trusted Publishing:** GitHub Actions OIDC Trusted Publishing workflow for PyPI.
- **Phase 11 — Bilingual Documentation:** Complete English and Persian documentation alignment.

---

### v0.2.0 — Extended Identifiers, Configurable Rules & Conflict Resolution
*Status: `RELEASED` (Published on PyPI and GitHub Releases)*

Expanded identifier support, introduced institution-specific pattern configuration, and added explicit conflict resolution:

- **Phase 12 — Conservative ASCII Email:** Syntactic dot-atom/domain validator (`is_valid_email`) and opt-in detector (`EmailDetector`).
- **Phase 13 — Iranian IBAN / Sheba:** 26-character MOD-97 checksum validator (`is_valid_iranian_iban`) and default detector (`IranianIBANDetector`).
- **Phase 14 — Bank Card / PAN:** 16-digit payment card Luhn checksum validator (`is_valid_bank_card_number`) and opt-in detector (`BankCardDetector`).
- **Phase 15 — Configurable Institutional Identifiers:** Immutable `PatternRule` and `PatternDetector` supporting custom regexes, normalized matching, and context-aware capture groups.
- **Phase 16 — Explicit Detection Conflict Resolution:** `resolve_detection_conflicts()` with `"reject"`, `"longest"`, and `"priority"` policies; parameter support in `redact()` and `PseudonymizationSession.pseudonymize()`.
- **Phase 17 — Release Preparation & Publication:** v0.2.0 release documentation, verification, and PyPI publication.

**Key Behavioral Defaults in v0.2.0:**
- Default `detect()` detectors: `IR_NATIONAL_ID`, `IR_MOBILE`, `IR_IBAN`.
- Opt-in detectors: `EmailDetector`, `BankCardDetector`, `PatternDetector`.
- Default conflict policy: `"reject"`.

---

### v0.3.0 — Detection Reports, CLI, Structured Data, Opt-in Persian NER & Clinical Profiles
*Status: `RELEASED` (Published on PyPI and GitHub Releases)*

Consolidated privacy-safe aggregate reporting, a CLI interface, structured dictionary helpers, an opt-in Persian NER prototype, and clinical redaction profiles:

- **Phase 18 — Privacy-Safe Detection Report:** `DetectionReport` immutable data model, `report_detections()`, and `detection_report()` summarizing total detections, type counts, and conflict indicators without storing or leaking raw PII, spans, or hashes.
- **Phase 19 — CLI:** Command-line interface `fa-redact` (and `python -m fa_redact`) with `detect`, `report`, and `redact` subcommands over streams and files with overwrite protection.
- **Phase 20 — Structured Data Helpers:** Non-destructive field-targeted processing (`detect_fields()`, `redact_fields()`, `report_fields()`) preserving non-target keys and data types with record-wide referential consistency.
- **Phase 21 — Persian Names / NER Research & Evaluation:** Research deliverable, exact-span entity evaluation harness, and synthetic Persian NER challenge suite.
- **Phase 21.1 — Persian NER Empirical Benchmark & Prototype:** Reproducible benchmark on PEYMA test split (99.19% exact-span F1) verifying deterministic character offset reconstruction.
- **Phase 21.2 — Opt-in Persian NER Implementation Prototype:** Strictly opt-in `PersianNERDetector` for local offline models, fail-loud long-text policy, and zero mandatory runtime dependencies (`fa-redact[ner]`).
- **Phase 22 — Clinical De-identification Layer:** High-level `ClinicalRedactionProfile` and `clinical_profile(...)` composing direct identifiers, opt-in email/card detectors, institutional `PatternRule` sets, and optional person detectors with document workflow presets (`outpatient_note`, `discharge_summary`, `referral_letter`).
- **Phase 23 — v0.3.0 Release Preparation & Publication:** Package version alignment, CHANGELOG `0.3.0` cut, distribution audits, isolated wheel smoke tests, and PyPI/GitHub release publication.

---

## Post-v0.3.0 Development

### Phase 24 — Batch Processing Helpers
*Status: `COMPLETED`*

Added lightweight, lazy streaming batch-processing helpers over Python iterables of strings:
- Implemented `detect_many()`, `redact_many()`, and `report_many()` in `src/fa_redact/batch.py`.
- Enforced lazy streaming without materializing the document collection in memory.
- Snapshotted caller-supplied mutable configuration (`detectors`, `type_priority`) immutably at helper creation time.
- Treated each document as an independent call (`redact_many` restarts placeholder counters per document without cross-document session state).
- Returned one value-free `DetectionReport` per document in `report_many()`.
- Maintained zero new runtime dependencies, Python >=3.10 support, and position/offset safety guarantees.

### Phase 25 — Synthetic Benchmark & Evaluation Corpus Tooling
*Status: `COMPLETED`*

Built a deterministic, offline, standard-library-only synthetic regression corpus and evaluation runner for fa-redact detectors under `research/`:
- Created an immutable `SyntheticDetectionCase` model with exact character offsets and strict validation.
- Provided a safe substring span-builder helper `_span_for` for deterministic index resolution.
- Built curated 100% synthetic test suites covering default direct identifiers (`IR_NATIONAL_ID`, `IR_MOBILE`, `IR_IBAN`), email (`EMAIL`), bank cards (`BANK_CARD`), and configurable institutional `PatternRule` / `PatternDetector` fixtures.
- Implemented an offline benchmark runner producing micro-averaged overall, per-type, and per-category exact-span metrics without PII/text leakage.
- Generated a reproducible, metadata-only result JSON artifact.
- Maintained zero new runtime dependencies, Python >=3.10 support, and strict research-only isolation.

---

### Phase 26 — Privacy-Safe Structured Serialization
*Status: `COMPLETED`*

Provided small, explicit, standard-library-only serialization helpers for fa-redact detection metadata and DetectionReport objects in `src/fa_redact/serialization.py`:
- Implemented `detection_to_dict()`, `detections_to_list()`, and `dumps_detections()` exporting structural metadata (`type`, `start`, `end`) without raw or normalized values.
- Implemented `report_to_dict()`, `reports_to_dict()`, `dumps_report()`, and `dumps_reports()` exporting aggregate metrics with value-free and span-free privacy guarantees.
- Refactored CLI `detect` and `report` subcommands to reuse shared serialization helpers while preserving byte-for-byte backward compatibility.
- Enforced strict negative scope: no generic arbitrary-object serializer, no raw PII export, no deserialization, no unselected record serialization, and no FHIR/HL7 adapters.
- Maintained zero new runtime dependencies (`dependencies = []`), Python >=3.10 support, and package version `0.3.0`.

---

### Phase 27 — Additional Iranian Identifier Research & Decision Gate
*Status: `COMPLETED`*

Researched candidate additional Iranian identifiers to determine suitability for deterministic, offline, privacy-first implementation in fa-redact:
- Evaluated candidate identifiers: Iranian Legal Entity National ID (*شناسه ملی اشخاص حقوقی*), Iranian Postal Code (*کد پستی ده رقمی*), Company Registration Number (*شماره ثبت شرکت‌ها*), and Economic/Tax Identifier (*کد اقتصادی*).
- Resolved checksum algorithm disagreements across technical implementations and empirical public data.
- Established an 8-dimension deterministic scoring rubric and decision bands: Iranian Legal Entity National ID scored 15/16 (CONDITIONAL GO, opt-in detector).
- Documented research limitation: no primary statutory publication of the arithmetic checksum formula was identified; Variant A consensus prime-weight formula confirmed across reviewed implementations and empirical samples.
- Maintained zero production source changes, zero new runtime dependencies (`dependencies = []`), package version `0.3.0`, and default detectors unchanged.

---

## Active Phase

### Phase 28 — Opt-in Iranian Legal Entity National ID Implementation
*Status: `ACTIVE / IN PROGRESS`*

Implement strictly opt-in Iranian Legal Entity National ID (*شناسه ملی اشخاص حقوقی*) validator (`is_valid_iranian_legal_entity_id`) and detector (`IranianLegalEntityIDDetector`) with canonical entity type `IR_LEGAL_ENTITY_ID`:
- Implement Phase 27 Variant A consensus checksum formula (`[29, 27, 23, 19, 17, 29, 27, 23, 19, 17]`, `d[9] + 2`, modulo 11, remainder 10 $\to$ 0).
- Reject all-identical 11-digit pseudo-values and malformed candidates defensively.
- Support ASCII, Persian, and Arabic-Indic digit scripts via position-preserving normalization.
- Preserve exact source character offsets and surface representations (`Detection.value` vs. `Detection.normalized_value`).
- Maintain strictly opt-in integration: do NOT add to `_DEFAULT_DETECTORS` or default clinical profiles.
- Zero network or registry lookups (offline mathematical validation only).
- Zero new runtime dependencies (`dependencies = []`), Python >=3.10 support, and package version `0.3.0`.

---

## Later Candidates

The following topics represent potential future directions after the core planned phases:

- **Performance Profiling & Optimization:** Micro-benchmarking regex execution and normalization throughput on large corpora.

---

## Explicitly Out of Scope for Now

To maintain focus, safety, and architectural integrity, the following are explicitly out of scope:

- **Automatic Regulatory Certification:** No claims or automated guarantees of HIPAA, GDPR, or Iranian data protection law compliance.
- **Automatic Database / HIS / FHIR Integration:** No direct connectors to database systems, hospital information systems (HIS), or EHR APIs.
- **Network / Registry Lookups:** No online verification of National IDs, bank accounts, or phone numbers in core validators.
- **Mandatory Machine Learning Dependencies:** Core package will not require torch, transformers, spacy, or other heavy ML runtimes.
- **Automatic Telemetry or Analytics:** Zero network telemetry, usage tracking, or remote error reporting.
- **Silent Conflict Resolution or Auto-Activation:** No hidden detector activation or unrequested heuristic conflict resolution.
