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

## Current Unreleased Development

### Phase 18 — Privacy-Safe Detection Report
*Status: `MERGED / UNRELEASED` (Merged into `main` via PR #17, commit `4ce102f95ff683d957f55bea79d393bff8976787`)*

Introduced aggregate, value-free detection reporting:
- `DetectionReport` immutable data model capturing total counts, deterministic type breakdowns, conflict counts, and duplicate metrics.
- Pure aggregation function `report_detections(detections)`.
- High-level pipeline helper `detection_report(text, detectors=...)`.
- Value-free guarantee: reports contain no raw values, normalized values, source text, character spans, snippets, or PII hashes.
- Exported publicly from `fa_redact`.

---

### Phase 19 — CLI
*Status: `MERGED / UNRELEASED` (Merged into `main` via PR #19, commit `5fe894d23424bdb3825bac75ccfbc6c250e79c19`)*

Provided a conservative command-line interface over existing `fa-redact` capabilities:
- Command-line entry point `fa-redact` and module `python -m fa_redact`.
- Subcommands `detect`, `report`, and `redact` across `stdin`/`stdout` streams and file paths.
- Privacy-conscious diagnostics to `stderr` without exposing input text, detected PII, or internal state.
- In-place overwrite protection and zero external runtime dependencies.

---

### Phase 20 — Structured Data Helpers
*Status: `MERGED / UNRELEASED` (Merged into `main` via PR #20, commit `5e1023a2e3f9a910cc669569525652098262b2ea`)*

Provided conservative helpers for processing explicitly selected fields within structured dictionaries, mappings, or JSON-like records:
- Explicit field targeting via `detect_fields()`, `redact_fields()`, and `report_fields()`.
- Dot-separated path navigation with strict syntax validation and duplicate path rejection.
- Record-wide referential consistency during redaction across multiple targeted string fields.
- Non-destructive processing preserving unselected keys, non-string types, booleans, numbers, and lists.
- Zero external runtime dependencies (no pandas, polars, or dataframe requirements).

---

## Active Phase

### Phase 21 — Persian Names / NER Research & Evaluation
*Status: `ACTIVE / RESEARCH IN PROGRESS`*

Investigate and design named entity recognition (NER) for Persian personal names and unstructured medical entities:
- Acknowledge that name recognition is probabilistic and qualitatively distinct from rule-based/checksum detection.
- Conduct empirical evaluation against Persian datasets with rigorous precision/recall, exact-span entity scoring, and false-positive analysis.
- If machine learning models or tokenizers are required, package them strictly as **optional dependencies / extras** to ensure core `fa-redact` remains lightweight and zero-dependency.
- Do not select or hardcode any external NLP framework or model until research is completed.

---

## Planned Phases

### Phase 22 — Clinical De-identification Layer
*Status: `FUTURE`*

Provide high-level composite policies and presets for Persian healthcare text workflows:
- Compose built-in and institutional detectors into coherent clinical profiles.
- Offer standardized redaction templates for outpatient notes, discharge summaries, and referral letters.
- Explicit invariant: must NOT be presented as guaranteed clinical de-identification or automated regulatory compliance.

---

## Later Candidates

The following topics represent potential future directions after the core planned phases:

- **Batch Processing Helpers:** Safe multi-document or chunked streaming utilities.
- **Benchmark & Evaluation Corpus Tooling:** Offline evaluation harnesses using synthetic test suites.
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
