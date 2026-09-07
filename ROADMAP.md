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

---

## Active Phase

### Phase 25 — Synthetic Benchmark & Evaluation Corpus Tooling
*Status: `ACTIVE / IN PROGRESS`*

Build a deterministic, offline, standard-library-only synthetic regression corpus and evaluation runner for fa-redact detectors under `research/`:
- Create an immutable `SyntheticDetectionCase` model with exact character offsets and strict validation.
- Provide a safe substring span-builder helper `_span_for` for deterministic index resolution.
- Build curated 100% synthetic test suites covering:
  - Default direct identifiers (`IR_NATIONAL_ID`, `IR_MOBILE`, `IR_IBAN`) with script/normalization variants and negative controls.
  - Opt-in `EMAIL` detection (positive syntax variants, punctuation boundaries, negative controls).
  - Opt-in `BANK_CARD` detection (positive Luhn numbers, Persian/Arabic-Indic digits, negative controls).
  - Configurable institutional `PatternRule` / `PatternDetector` (synthetic MRN/Patient ID examples, contextual capture groups, normalized Persian digits).
  - Multi-identifier mixed documents.
- Implement an offline benchmark runner producing micro-averaged overall, per-type, and per-category exact-span metrics and identifying failed case IDs without PII/text leakage.
- Generate a reproducible, metadata-only result JSON artifact.
- Maintain zero new runtime dependencies, Python >=3.10 support, and strict research-only isolation.

---

## Later Candidates

The following topics represent potential future directions after the core planned phases:

- **Optional Structured Serialization:** Format adapters for specific healthcare interchange formats.
- **Additional Iranian Identifier Types:** Research into other standardized national numbers (e.g., postal codes, registration numbers) where unambiguous formats and checksums exist.
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
