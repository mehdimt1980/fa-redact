# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
