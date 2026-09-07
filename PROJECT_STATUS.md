# fa-redact — Project Status

> Repository state is authoritative. Always verify the current branch,
> HEAD, CI, and relevant source files before making changes.

---

## Current State

- **Latest published release:** `v0.2.0`
- **Current source version:** `0.3.0`
- **Development status:** `v0.3.0 RELEASE PREPARATION` (Phases 18, 19, 20, 21, 21.1, and 22 merged; v0.3.0 release candidate preparation in progress)
- **Last closed phase:** Phase 22 — Clinical De-identification Layer
- **Current active phase:** Phase 23 — v0.3.0 Release Preparation (In Progress)
- **Runtime dependencies:** zero (Python Standard Library only)
- **Supported Python:** `>=3.10`
- **Development Status classifier:** `Development Status :: 3 - Alpha`

---

## Current Default Detection Behavior

Default detectors executed by `detect()`, `redact()`, and `PseudonymizationSession.pseudonymize()` (when `detectors` parameter is omitted or `None`):

- `IR_NATIONAL_ID` (`IranianNationalIDDetector`)
- `IR_MOBILE` (`IranianMobileNumberDetector`)
- `IR_IBAN` (`IranianIBANDetector`)

The following built-in detectors remain strictly **opt-in**:

- `EmailDetector` (`EMAIL`)
- `BankCardDetector` (`BANK_CARD`)
- `PatternDetector` (user-configured entity types via `PatternRule`)
- `PersianNERDetector` (`PERSON`, opt-in experimental detector using local ML models)

### Detector Selection Rules

- Explicitly passing `detectors=[...]` **replaces** the default detector set for that call; it does not augment defaults.
- Passing `detectors=[]` explicitly runs no detectors.

---

## Public Capabilities

### Normalization
- Converts Persian digits (`۰-۹`) and Arabic-Indic digits (`٠-٩`) to ASCII digits (`0-9`).
- Converts selected Arabic letter variants (`ي`, `ك`) to Persian canonical forms (`ی`, `ک`).
- Position-preserving guarantee: maps exactly one input Unicode code point to one output code point (`len(normalized_text) == len(original_text)`).
- Source text character offsets (`start`, `end`) remain exact across original and normalized representations.

### Detection
- Detects Iranian National IDs (10-digit modulo-11 checksum validation).
- Detects Iranian Mobile Numbers (2026 CRA National Numbering Plan prefix validation).
- Detects Iranian IBANs / Sheba (26-character MOD-97 checksum validation).
- Opt-in detection for ASCII Email addresses (syntactic dot-atom / domain validation).
- Opt-in detection for 16-digit Bank Cards / PAN (Luhn MOD-10 checksum validation).
- Opt-in configurable `PatternDetector` executing user-defined `PatternRule` regex specifications.
- `detect()` represents the raw evidence layer: preserves overlaps, nested spans, and exact duplicate detections without silent filtering.

### Transformation
- **Stateless Redaction (`redact`):** Replaces detected spans with deterministic typed placeholders (e.g., `[IR_NATIONAL_ID_1]`, `[IR_MOBILE_1]`, `[IR_IBAN_1]`). Enforces referential consistency within a single call and avoids collisions with pre-existing placeholder literals.
- **Stateful Pseudonymization (`PseudonymizationSession`):** Maintains stable entity aliases across multiple conversational turns, supports non-cascading local restoration (`session.restore()`) using first-observed raw representations, reserves historical placeholder-like literals, and enforces atomic state updates on failure.

### Conflict Resolution
- Explicit conflict resolution function: `resolve_detection_conflicts(detections, policy=...)`.
- Supported policies:
  - `"reject"` (conservative default): fails loudly with privacy-safe `ValueError` on any overlap or duplicate.
  - `"longest"`: greedily selects longer spans, collapses exact duplicates, and fails on ambiguous equal-length overlaps.
  - `"priority"`: resolves conflicts based on user-supplied entity type priority hierarchy (`type_priority=[...]`).
- `redact()` and `PseudonymizationSession.pseudonymize()` default to `conflict_policy="reject"`.
- Raw `detect()` does not perform conflict resolution.

### Reporting
- Privacy-safe aggregate reporting model: `DetectionReport`, `report_detections()`, and convenience helper `detection_report()`.
- Reports aggregate metrics (counts, distinct types, conflict indicators, duplicate groups) without storing, returning, or persisting original source text, raw values, normalized values, character spans, snippets, or PII hashes.
- Entity-type names and counts remain aggregate metadata.

### CLI
- Conservative, privacy-conscious command-line interface `fa-redact` with `detect`, `report`, and `redact` subcommands.
- Standard I/O streaming (`stdin` / `stdout`) and file-based processing with overwrite protection.
- Value-free JSON reporting and raw metadata streaming without terminal or error PII leakage.

### Structured Data Helpers
- Non-destructive processing of explicitly selected string paths within Python mappings/records: `detect_fields()`, `redact_fields()`, and `report_fields()`.
- Dot-separated path navigation (e.g. `"note"`, `"meta.contact"`, `"patient.info.note"`) with strict path syntax validation and duplicate path rejection.
- Record-wide referential consistency in `redact_fields()` across multiple targeted fields within a single record.
- Preserves all unselected keys, non-string values, booleans, numbers, None, and lists without blind recursive traversal.

---

## Core Architectural Invariants

1. **Zero Runtime Dependencies:** The core package relies strictly on the Python Standard Library.
2. **Supported Python:** Python support remains strictly `>=3.10`.
3. **Position-Preserving Normalization:** Normalization must preserve exact string lengths (`len(normalized_text) == len(original_text)`). Never insert, delete, or collapse characters during normalization.
4. **Exact Source Offsets:** Detection slice offsets (`start`, `end`) always index directly into original source text.
5. **Safe Factory Construction:** `Detection.from_texts()` should be preferred when constructing detections from source and normalized text.
6. **Raw Detection Layer:** `detect()` is the raw evidence layer; it must preserve overlaps, nested detections, and duplicate spans.
7. **Conservative Transformation Defaults:** `redact()` and `PseudonymizationSession.pseudonymize()` default to conservative conflict rejection (`conflict_policy="reject"`).
8. **Explicit Conflict Resolution:** Conflict resolution is opt-in policy and must be explicit.
9. **Explicit Detector Override:** Explicit `detectors=[...]` arguments replace default detectors rather than merging with them.
10. **Deterministic & Offline:** Built-in validators and detectors must remain purely deterministic, offline, and local.
11. **No Network or Database Coupling:** Core validators and detectors must never perform network requests or database queries.
12. **No Speculative Architecture:** Avoid speculative abstraction layers, dynamic plugin registries, or premature framework coupling.

---

## Privacy & Safety Invariants

- **No Issuance or Identity Claims:** Checksum or prefix validity proves mathematical format only; it does not verify that an identifier exists, has been officially issued, or belongs to an individual.
- **National ID Limitation:** Modulo-11 checksum validation does not verify Civil Registration Organization issuance.
- **Mobile Number Limitation:** Prefix validation does not verify SIM registration, carrier ownership, active service, or number portability.
- **IBAN Limitation:** MOD-97 validation does not verify bank account existence, status, or balance.
- **Email Limitation:** Syntactic validation does not verify mailbox existence, MX records, or deliverability.
- **Bank Card Limitation:** Luhn validation does not verify cardholder identity, card activation, expiry, CVV2, or financial issuer.
- **Pattern Rules Trust Boundary:** `PatternRule` regular expressions are trusted application configuration. Standard library `re` does not enforce execution timeouts; never execute unreviewed regexes from untrusted tenants.
- **No Universal Healthcare Formats:** There is no universal MRN, Patient ID, or Encounter ID format. `PatternDetector` requires explicit application configuration.
- **Conflict Resolution Trade-offs:** Conflict resolution heuristics (`longest`, `priority`) discard overlapping candidates and may expose non-winning partial substrings. `reject` remains the recommended conservative default.
- **Sensitive Mapping Protection:** `PseudonymizationSession.mapping` contains sensitive raw PII and must never be exposed outside the trusted local perimeter.
- **Reporting Scope:** `DetectionReport` omits raw values, but aggregate counts and entity types are metadata that may require governance in operational environments.
- **Schema-Level Entity Types:** Custom `Detection.type` names must remain schema-level labels (e.g., `MRN`, `PATIENT_ID`) and must never contain patient identifiers or sensitive values.
- **No Complete Clinical De-Identification Claims:** `fa-redact` does NOT perform complete clinical de-identification. Personal-name extraction is NOT enabled by default. Experimental free-text PERSON extraction is available only when `PersianNERDetector` is explicitly configured with a trusted local compatible model. Address removal and other unsupported PHI categories remain outside current coverage. PERSON extraction does not infer patient/doctor/relative role, and `fa-redact` provides no clinical or compliance guarantees.
- **No Compliance Claims:** Do not claim automated GDPR compliance, HIPAA Safe Harbor compliance, medical device certification, or production clinical suitability.

---

## Release Invariants

- **Release Tags:** Release tags use lowercase `v<version>` syntax (e.g., `v0.2.0`).
- **Release Trigger:** Releases are triggered solely by publishing a GitHub Release targeting `main`.
- **Trusted Publishing / OIDC:** PyPI publication uses GitHub Actions OIDC Trusted Publishing; no long-lived PyPI API tokens or passwords belong in repository secrets.
- **Single Build Artifact:** Build distribution artifacts once and publish the identical verified artifacts to PyPI.
- **No Overwrites / No `skip-existing`:** Package uploads must fail loudly if an artifact version already exists.
- **Version Alignment:** Git tag, `pyproject.toml` version, runtime `fa_redact.__version__`, and distribution wheel metadata must agree exactly.
- **Fail-Loud CI:** Release workflow steps must remain strictly fail-loud.
- **Separate Review Gates:** Release preparation PRs and actual GitHub Release publication are distinct operational review gates.
- For operational release instructions and checklists, consult [RELEASING.md](RELEASING.md).

---

## Development Workflow

- **Phase Isolation Rule:** `One development phase = one feature branch = one PR = one review cycle.`
- **Fresh Context Preferred:** For AI-assisted development, each major development phase should preferably begin in a fresh chat/session.
- **Required Pre-Phase Reading:** Before implementing any phase, the developer or AI agent MUST read:
  - `PROJECT_STATUS.md`
  - `ROADMAP.md`
  - `CHANGELOG.md`
  - `README.md`
  - `CONTRIBUTING.md`
  - Relevant source modules and test files.
- **Repository Authority:** The repository Git history, source files, tests, and CI configurations are authoritative. Conversation memory, assistant summaries, pasted reports, and local scratch files are NOT authoritative evidence.

---

## Independent Verification Rule

> A Codex/AI completion report is not sufficient evidence that a phase passed.

Before marking a development phase as CLOSED, independently verify:
1. Actual Git branch and HEAD commit.
2. Pull Request state and merged commit.
3. Changed file diff.
4. Relevant source code and test implementations.
5. Local quality suite execution (pytest, ruff, mypy, build, twine).
6. GitHub Actions PR CI status.
7. Resulting `main` branch commit and subsequent `main` CI run.

Only after all verification steps succeed should a phase be declared CLOSED.

---

## Phase Lifecycle & Gates

A development phase transitions through three discrete states:

```text
[ IN PROGRESS ] ──▶ [ MERGE-READY ] ──▶ [ CLOSED ]
```

### 1. IN PROGRESS
- Active implementation, test development, and local review on a dedicated feature branch (`feat/...`, `research/...`, or `docs/...`).

### 2. MERGE-READY
- Implementation is complete.
- Local quality suite passes cleanly (`pytest`, `ruff`, `mypy`, `build`, `twine`).
- Pull Request is opened and GitHub Actions PR CI passes on all supported Python versions (3.10, 3.11, 3.12, 3.13).
- Has NOT yet been merged to `main`.

### 3. CLOSED
- Pull Request is merged into `main`.
- Resulting `main` commit is verified.
- Post-merge GitHub Actions CI on `main` has passed successfully.

*(A phase is never considered CLOSED merely because branch CI is green.)*

---

## Last Closed Phase

- **Phase:** Phase 22 — Clinical De-identification Layer
- **Status:** `CLOSED`
- **PR:** #24
- **Merge Commit:** `c7bff32cad01f642198b8505c02799ce33235cff`
- **Verified Post-Merge Main CI:** Run `34089912023` (push to `main`, conclusion: success, 5 jobs passed)
- **Phase 22 Baseline:** 825 passing tests.
- **Unreleased Scope:** Phase 18, 19, 20, 21, 21.1, 21.2, and 22 are merged into `main` and prepared for release in `v0.3.0`.
- **Key Phase 22 Result:**
  - High-level composition layer: `ClinicalRedactionProfile`, `ClinicalTextTemplate`, and `clinical_profile(...)` factory.
  - Standardized clinical text templates: `outpatient_note`, `discharge_summary`, `referral_letter`.
  - Explicit institutional `PatternRule` composition.
  - `EmailDetector` included in clinical profiles by default (`include_email=True`).
  - `BankCardDetector` explicit opt-in (`include_bank_card=False` by default).
  - Explicit `person_detector` parameter (opt-in; no automatic `PersianNERDetector` instantiation).
  - No role inference (patient, physician, relative).
  - Profile convenience methods delegate to existing core APIs (`detect`, `redact`, `report`, `detect_fields`, `redact_fields`, `report_fields`).
  - Conservative default conflict policy preserved (`conflict_policy="reject"`).
  - Zero mandatory runtime dependencies preserved in core package.
  - Explicit anti-claims: no complete clinical de-identification guarantee, no HIPAA/GDPR compliance claims, not a certified medical device.
- **Stable Historical Anchors:**
  - `v0.2.0` release commit: `227577deeb899de9593efb296659822f1ec0bf20`
  - Phase 18 merge commit: `4ce102f95ff683d957f55bea79d393bff8976787` (PR #17)
  - Phase 19 merge commit: `5fe894d23424bdb3825bac75ccfbc6c250e79c19` (PR #19)
  - Phase 20 merge commit: `5e1023a2e3f9a910cc669569525652098262b2ea` (PR #20)
  - Phase 21 merge commit: `9ff013e1b4dddf7f2bd5f21cdf9c9feed480266c` (PR #21)
  - Phase 21.1 merge commit: `bf1a71b2e675466cb1bf7ef0ab60eaf5f0bbef0f` (PR #22)
  - Phase 21.2 merge commit: `836ae09e6a44c9f234e6cc43492f1e0b70e6b4ac` (PR #23)
  - Phase 22 merge commit: `c7bff32cad01f642198b8505c02799ce33235cff` (PR #24)
- *(Note: Run `git rev-parse HEAD` on `main` to inspect the active HEAD commit).*

---

## Active Phase

- **Phase:** Phase 23 — v0.3.0 Release Preparation
- **Status:** `IN PROGRESS`
- **Scope:** Prepare `v0.3.0` minor release encompassing public capabilities from Phases 18–22 (Detection Reports, CLI, Structured Data Helpers, Persian NER evaluation/prototype, Clinical Redaction Profiles). Update package version to `0.3.0`, cut CHANGELOG `0.3.0` entry, align bilingual documentation and coverage tables, expand release wheel smoke test in `.github/workflows/release.yml`, update `RELEASING.md`, audit distribution contents, and open release preparation PR against `main`. Release publication remains a separate explicit gate after PR merge.

---

## Status-Update Responsibility

At the conclusion of future development phases:

1. **Before Merge (in the feature PR):**
   - Update `CHANGELOG.md` under `[Unreleased]`.
   - Update `README.md` (English and Persian sections) if public capabilities changed.
2. **After Merge & Main CI Verification (or start of next phase):**
   - Update `PROJECT_STATUS.md` and `ROADMAP.md` to record the closed phase and set the next planned phase.
   - `PROJECT_STATUS.md` and `ROADMAP.md` must be updated before starting a subsequent major phase.

---

## Starting a New AI/Developer Session

Follow these steps when initiating a fresh development session:

1. Check out and update `main`:
   ```bash
   git checkout main
   git pull --ff-only origin main
   git status
   git rev-parse HEAD
   ```
2. Read `PROJECT_STATUS.md`.
3. Read `ROADMAP.md`.
4. Read the `[Unreleased]` section of `CHANGELOG.md`.
5. Inspect relevant source modules in `src/fa_redact/` and test files in `tests/`.
6. Verify current GitHub PR / CI / release status.
7. Create an isolated feature branch for exactly one planned phase:
   ```bash
   git checkout -b feat/<phase-name>
   ```

### Canonical Starter Prompt for New Sessions

```text
Open mehdimt1980/fa-redact.

Treat the repository as the authoritative project context.

Read PROJECT_STATUS.md, ROADMAP.md, CHANGELOG.md,
README.md, and the relevant current source/tests.

Verify the current main HEAD and CI state before making changes.

We are starting the next planned phase.
Do not rely on prior chat memory as project state.
```
