# fa-redact

[![PyPI version](https://img.shields.io/pypi/v/fa-redact.svg)](https://pypi.org/project/fa-redact/)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/mehdimt1980/fa-redact/actions/workflows/ci.yml/badge.svg)](https://github.com/mehdimt1980/fa-redact/actions/workflows/ci.yml)

**Languages:** [English](#english) | [فارسی](#persian)

---

<a id="english"></a>
## English

`fa-redact` is a lightweight, zero-dependency, privacy-first Python toolkit for Persian/Iranian Personally Identifiable Information (PII) detection, redaction, and pseudonymization, designed especially for healthcare and AI/LLM applications.

> **Status: v0.1.0 (Alpha) — available on PyPI**  
> `fa-redact` is publicly available on [PyPI](https://pypi.org/project/fa-redact/) and [GitHub Releases](https://github.com/mehdimt1980/fa-redact/releases/tag/v0.1.0).

---

### Table of Contents

- [Overview](#overview)
- [Why fa-redact?](#why-fa-redact)
- [Installation](#installation)
- [Quick Start](#quick-start)
  - [1. Detect PII](#1-detect-pii)
  - [2. Redact PII (Stateless)](#2-redact-pii-stateless)
  - [3. Stateful Pseudonymization for AI/LLMs](#3-stateful-pseudonymization-for-aillms)
- [Detailed Capabilities](#detailed-capabilities)
  - [1. Position-Preserving Normalization](#1-position-preserving-normalization)
  - [2. Detection Model & Pipeline](#2-detection-model--pipeline)
  - [3. Iranian National ID Validation & Detection](#3-iranian-national-id-validation--detection)
  - [4. Iranian Mobile Number Validation & Detection](#4-iranian-mobile-number-validation--detection)
  - [5. Iranian IBAN / Sheba Validation & Detection (Unreleased)](#5-iranian-iban--sheba-validation--detection-unreleased)
  - [6. Conservative ASCII Email Validation & Detection (Opt-in / Unreleased)](#6-conservative-ascii-email-validation--detection-opt-in--unreleased)
  - [7. Bank Card / PAN Validation & Detection (Opt-in / Unreleased)](#7-bank-card--pan-validation--detection-opt-in--unreleased)
  - [8. Redaction Semantics](#8-redaction-semantics)
  - [9. Stateful Pseudonymization Sessions](#9-stateful-pseudonymization-sessions)
- [Custom Detectors](#custom-detectors)
- [Healthcare & AI/LLM Usage Pattern](#healthcare--aillm-usage-pattern)
- [Current Coverage & Limitations](#current-coverage--limitations)
- [Privacy and Security Model](#privacy-and-security-model)
- [Privacy-Safe Test Data Policy](#privacy-safe-test-data-policy)
- [Development & Quality Checks](#development--quality-checks)
- [Release Process](#release-process)
- [License](#license)

---

### Overview

In healthcare, enterprise, and AI workflows, sending raw Persian clinical notes or customer communications to external Large Language Models (LLMs) or third-party APIs poses significant privacy risks. `fa-redact` addresses these challenges by providing:

1. **Position-Preserving Normalization**: Maps Persian and Arabic digits and letters 1-to-1 to canonical representations without altering string length or offset positions.
2. **Algorithmic Validation**: Implements checksum rules and prefix checks for Iranian identifiers (National IDs and mobile numbers) rather than relying on loose regular expressions.
3. **Safe Placeholder Redaction**: Deterministically substitutes detected spans with typed placeholders.
4. **Stateful Pseudonymization & Local Restoration**: Generates stable aliases across conversational turns and restores original values locally inside your trusted boundary.

---

### Why fa-redact?

- **Handling Persian Text Peculiarities**: Persian text frequently mixes Persian digits (`۰-۹`), Arabic-Indic digits (`٠-٩`), and ASCII digits (`0-9`), alongside letter variants like Arabic Yeh (`ي`) and Kaf (`ك`). Simple regex patterns fail on mixed-script variations, while naive string replacements drift character offsets.
- **Offset Integrity**: `fa-redact` ensures `len(normalized) == len(original)`, guaranteeing that slice offsets `text[start:end]` map directly back to the original source text.
- **Privacy-First AI Integrations**: Mask supported direct identifiers before sending prompts to external LLMs, then restore LLM outputs locally without exposing raw PII outside your trusted perimeter.
- **Zero Runtime Dependencies**: Written entirely in pure Python (3.10+) with full typing (`py.typed`).

---

### Installation

Install the package directly from PyPI:

```bash
pip install fa-redact
```

For development or building from source:

```bash
git clone https://github.com/mehdimt1980/fa-redact.git
cd fa-redact
pip install -e ".[dev]"
```

---

### Quick Start

#### 1. Detect PII

Identify sensitive spans with exact source offsets and normalized values:

```python
from fa_redact import detect

text = "بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره ۰۹۱۲۳۴۵۶۷۸۹ مراجعه کرد."
detections = detect(text)

for d in detections:
    print(
        f"Type: {d.type} | Value: {d.value} | Normalized: {d.normalized_value} | Span: [{d.start}:{d.end}]"
    )
    assert text[d.start : d.end] == d.value
```

#### 2. Redact PII (Stateless)

Sanitize text by replacing detected spans with deterministic, typed placeholders. Repeated identical identifiers within the same call receive the same placeholder:

```python
from fa_redact import redact

text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱، تماس: ۰۹۱۲۳۴۵۶۷۸۹، تماس مجدد: 09123456789"
safe_text = redact(text)
print(safe_text)
# Output: "کد ملی: [IR_NATIONAL_ID_1]، تماس: [IR_MOBILE_1]، تماس مجدد: [IR_MOBILE_1]"
```

#### 3. Stateful Pseudonymization for AI/LLMs

Maintain consistent entity mappings across conversation turns and restore placeholders locally:

```python
from fa_redact import PseudonymizationSession

session = PseudonymizationSession()

# 1. Pseudonymize prompt locally inside your trusted boundary:
prompt = "کد ملی بیمار ۱۲۳۴۵۶۷۸۹۱ و شماره تماس ۰۹۱۲۳۴۵۶۷۸۹ است."
pseudonymized_prompt = session.pseudonymize(prompt)
print(pseudonymized_prompt)
# Output: "کد ملی بیمار [IR_NATIONAL_ID_1] و شماره تماس [IR_MOBILE_1] است."

# 2. Send ONLY pseudonymized_prompt to external LLM. Simulated LLM response:
llm_response = "جهت هماهنگی با بیمار با [IR_MOBILE_1] تماس حاصل فرمایید."

# 3. Restore placeholders locally:
restored = session.restore(llm_response)
print(restored)
# Output: "جهت هماهنگی با بیمار با ۰۹۱۲۳۴۵۶۷۸۹ تماس حاصل فرمایید."
```

---

### Detailed Capabilities

#### 1. Position-Preserving Normalization

`fa-redact` provides pure, deterministic normalization where each character maps 1-to-1 to a normalized code point (`len(normalized) == len(original)`):

```python
from fa_redact import normalize_digits, normalize_letters, normalize_text

# Normalizes Persian (۰-۹) and Arabic-Indic (٠-٩) digits to ASCII (0-9)
normalize_digits("کد بیمار: ۱۲۳٤٥")
# Returns: "کد بیمار: 12345"

# Normalizes Arabic letter variants (ي -> ی, ك -> ک)
normalize_letters("پزشك و دكتر")
# Returns: "پزشک و دکتر"

# Full position-preserving normalization
normalize_text("كد ملي: ۰۰۱٢٣٤٥٦٧٨")
# Returns: "کد ملی: 0012345678"
```

*What is not normalized:* Whitespace, punctuation, zero-width non-joiners (ZWNJ), diacritics, and arbitrary unicode characters are preserved as-is so that source offsets remain perfectly aligned.

#### 2. Detection Model & Pipeline

Identified spans are represented by the immutable `Detection` dataclass:

- `type`: Identifier category (e.g., `IR_NATIONAL_ID`, `IR_MOBILE`).
- `value`: Exact substring as written in the original input text.
- `normalized_value`: Canonical normalized form of the span.
- `start` / `end`: Zero-indexed Python string slice boundaries (`text[start:end] == value`).

The detection pipeline aggregates detector results and sorts them deterministically by `(start, end, type)`. It intentionally preserves overlaps and duplicate detections. Overlap rejection is applied only when producing replacement text via `redact()` or `PseudonymizationSession.pseudonymize()`, where overlapping or nested spans will raise a `ValueError`.

#### 3. Iranian National ID Validation & Detection

Validates and detects 10-digit Iranian National IDs (`کد ملی` / Code Melli):

```python
from fa_redact import IranianNationalIDDetector, is_valid_national_id

# Algorithmic test vectors (not personal data)
is_valid_national_id("1234567891")  # True
is_valid_national_id("۱۲۳۴۵۶۷۸۹۱")  # True (Persian digits)
is_valid_national_id("1234567890")  # False (invalid check digit)
is_valid_national_id("1111111111")  # False (repeated digits rejected)
```

- **Modulo-11 Checksum**: Applies the implemented modulo-11 checksum rule for Iranian National IDs.
- **Repeated-Digit Rejection**: Rejects pseudo-values like `0000000000` or `1111111111`.
- **Exact Length & Formatting**: Requires exactly 10 digits in compact format; does not strip spaces, remove hyphens, or auto-pad.
- **Verification Notice**: Validation confirms mathematical format only without querying official registries. Checksum validity does not establish whether an identifier has been officially issued to an individual.

#### 4. Iranian Mobile Number Validation & Detection

Validates and detects Iranian mobile numbers using the bundled 2026 CRA/ITU mobile-service NDC allocation snapshot:

```python
from fa_redact import IranianMobileNumberDetector, is_valid_mobile_number

# Supported compact domestic and international formats
is_valid_mobile_number("09123456789")  # True (domestic)
is_valid_mobile_number("۰۹۱۲۳۴۵۶۷۸۹")  # True (Persian digits)
is_valid_mobile_number("+989123456789")  # True (+98 format)
is_valid_mobile_number("00989351234567")  # True (0098 format)
is_valid_mobile_number("09412345678")  # False (fixed non-geographical)
```

- **Prefix-Aware Allocation**: Validates against prefixes allocated for mobile services in the bundled National Numbering Plan snapshot.
- **Exclusion of Non-Mobile Prefixes**: Non-mobile prefixes such as `094` (fixed non-geographic) and `09950` (Public Trunk) are rejected.
- **Strict Formatting**: Only compact forms (`09xxxxxxxxx`, `+989xxxxxxxxx`, `00989xxxxxxxxx`) are accepted. The validator does not strip spaces, remove hyphens, or auto-format.
- **Verification Notice**: Prefix validation confirms structural numbering-plan compliance only; it does not verify active SIM status, subscriber identity, carrier ownership, or number portability status.

#### 5. Iranian IBAN / Sheba Validation & Detection (Unreleased)

> [!NOTE]
> **Unreleased / Development Version (Phase 13)**: Iranian IBAN / Sheba validation and detection are introduced in the unreleased development cycle and are not part of published PyPI release `0.1.0`.

`fa-redact` provides an offline, deterministic Iranian International Bank Account Number (IBAN / شماره شبا) validator (`is_valid_iranian_iban`) and detector (`IranianIBANDetector`). An Iranian IBAN in compact electronic form contains 26 characters: `IR`, followed by 2 check digits and a 22-digit BBAN (or `IR` followed by 24 numeric digits):

```python
from fa_redact import (
    IranianIBANDetector,
    PseudonymizationSession,
    detect,
    is_valid_iranian_iban,
    redact,
)

# 1. Standalone Validation (Exact 26 chars: uppercase 'IR' + 24 digits, MOD-97)
is_valid_iranian_iban("IR641234567890123456789012")  # True
is_valid_iranian_iban("IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲")  # True (Persian digits)
is_valid_iranian_iban("ir641234567890123456789012")  # False (lowercase 'ir' rejected)
is_valid_iranian_iban("IR 64 1234 5678 9012 3456 7890 12")  # False (spaces rejected)
is_valid_iranian_iban("IR001234567890123456789012")  # False (invalid checksum)

# 2. Default Detection (Included in default detector set)
text = "شماره شبا واریز: IR641234567890123456789012 و تماس ۰۹۱۲۳۴۵۶۷۸۹"
detections = detect(text)
# Returns: [Detection(type='IR_IBAN', value='IR641234567890123456789012', ...), Detection(type='IR_MOBILE', ...)]

# 3. Default Redaction & Pseudonymization
safe_text = redact(text)
# Output: "شماره شبا واریز: [IR_IBAN_1] و تماس [IR_MOBILE_1]"

session = PseudonymizationSession()
pseudonymized = session.pseudonymize("واریز به شبا IR641234567890123456789012")
# Output: "واریز به شبا [IR_IBAN_1]"

restored = session.restore("تایید واریز به [IR_IBAN_1]")
# Output: "تایید واریز به IR641234567890123456789012"
```

- **MOD-97-10 Checksum Algorithm**: Validates the standard ISO 7064 MOD 97-10 checksum by rearranging to `BBAN (22 digits) + 1827 (IR) + CheckDigits (2 digits)` (representing `22-digit BBAN + 1827 + 2 check digits`) and verifying `remainder == 1`.
- **Default Detector Inclusion**: Unlike `EmailDetector`, `IranianIBANDetector` is included in `_DEFAULT_DETECTORS` because its structured boundary (`IR` followed by 24 digits) has no syntactic collision with National IDs or mobile numbers.
- **Position-Preserving & Digit Normalization**: Supports Persian (`۰-۹`) and Arabic-Indic (`٠-٩`) digits across the 24 numeric characters following `IR` (the 2 check digits plus the 22-digit BBAN), preserving the raw surface script in `Detection.value` and mapping to canonical ASCII in `Detection.normalized_value`.
- **Electronic Compact Format Only**: Only compact format without spaces, hyphens, or formatting separators is accepted. Lowercase prefix (`ir`) is strictly rejected.
- **Privacy & Financial Disclaimer**: `is_valid_iranian_iban` performs purely local, offline mathematical checksum validation. It does not perform bank API lookups, bank branch routing, or account status verification, and does not verify whether an account exists or is active.

#### 6. Conservative ASCII Email Validation & Detection (Opt-in / Unreleased)

> [!NOTE]
> **Unreleased / Development Version (Phase 12)**: Email validation and detection are introduced in the unreleased development cycle and are not part of published PyPI release `0.1.0`.

`fa-redact` provides a conservative, zero-dependency ASCII email address validator (`is_valid_email`) and detector (`EmailDetector`):

```python
from fa_redact import (
    EmailDetector,
    PseudonymizationSession,
    detect,
    is_valid_email,
    redact,
)

# 1. Standalone Validation
is_valid_email("user.name@example.com")  # True
is_valid_email("doctor@sub.hospital.ir")  # True
is_valid_email("user@localhost")  # False (single-label domain rejected)
is_valid_email("user+tag@invalid_domain.com")  # False (underscore in domain)
is_valid_email("user@مثال.ایران")  # False (non-ASCII / EAI unsupported)

# 2. Opt-in Detection (Pass EmailDetector explicitly)
text = "مکاتبه با دکتر احمدی: dr.ahmadi@hospital.ir و تماس 09123456789"
detections = detect(text, detectors=[EmailDetector()])
# Returns: [Detection(type='EMAIL', value='dr.ahmadi@hospital.ir', ...)]

# 3. Opt-in Redaction & Pseudonymization
safe_text = redact(text, detectors=[EmailDetector()])
# Output: "مکاتبه با دکتر احمدی: [EMAIL_1] و تماس 09123456789"

session = PseudonymizationSession()
pseudonymized = session.pseudonymize(
    "تماس با info@clinic.ir یا dr.ahmadi@hospital.ir انجام شد.",
    detectors=[EmailDetector()],
)
# Output: "تماس با [EMAIL_1] یا [EMAIL_2] انجام شد."

restored = session.restore("پیام به [EMAIL_1] ارسال شد.")
# Output: "پیام به info@clinic.ir ارسال شد."
```

- **Opt-in Architecture**: `EmailDetector` is intentionally **opt-in** in Phase 12 and is not included in the default detector set. Numeric-looking email local parts (such as `09123456789@example.com` or `1234567891@example.com`) can produce overlapping spans with mobile number or National ID detectors; while `detect()` permits overlaps, downstream redaction and pseudonymization fail-loud on overlaps until general conflict resolution is implemented.
- **Per-Call Detector Configuration**: `PseudonymizationSession` stores pseudonym mappings and counters, not a persistent detector configuration. The detector set is selected independently for each `pseudonymize()` call.
- **Conservative ASCII Specification**: Validates dot-atom local parts (`1-64` chars) and DNS-style domain names (`1-253` total domain chars, `1-63` chars per label, `2-63` chars for TLD, total address `<= 254` characters).
- **Unsupported Complex/Obsolete Forms**: Quoted local parts (`"john doe"@example.com`), IP domain literals (`user@[192.168.1.1]`), comments, folding whitespace, single-label domains (`user@localhost`), and internationalized/Unicode email addresses (EAI / RFC 6530+) are rejected.
- **Privacy & Verification Disclaimer**: `is_valid_email` performs purely local, offline syntactic validation. It performs no DNS queries, MX record lookups, mailbox verification, or network requests, and logs no PII. Syntactic validity does not verify that a mailbox exists or is deliverable.

#### 7. Redaction Semantics

- **Exact Span Reconstruction**: `redact()` rebuilds the output from the original Detection spans, preserving untouched source slices exactly and replacing only detected spans. It does not perform global value-based `str.replace()`.
- **Typed Placeholders**: Placeholders follow the format `[<TYPE>_<INDEX>]` (e.g., `[IR_NATIONAL_ID_1]`, `[IR_MOBILE_1]`, `[IR_IBAN_1]`, `[EMAIL_1]`).
- **Deterministic Numbering**: Identifiers receive sequential numbering based on their order of first appearance.
- **Collision Avoidance**: If an input already contains a literal string matching the placeholder syntax, newly generated placeholders increment past the colliding index.
- **Fail-Loud on Overlap**: If overlapping or duplicate spans are passed to `redact()`, it raises a `ValueError`.

#### 8. Stateful Pseudonymization Sessions

`PseudonymizationSession` manages persistent mappings across multi-turn AI interactions:

- **Local Sensitive Mapping**: `session.mapping` contains `{placeholder: original_raw_value}`. Keep this mapping strictly inside your trusted boundary.
- **Cross-Call Identity**: Entities are tracked by `(type, normalized_value)`. For example, `۰۹۱۲۳۴۵۶۷۸۹` in turn 1 and `09123456789` in turn 2 both resolve to `[IR_MOBILE_1]`.
- **Domestic vs. International Limitation**: `09123456789` and `+989123456789` have different normalized strings and are not canonicalized into the same identity in v0.1.0.
- **First-Observed Representative Restoration**: Placeholders are restored using the first-observed raw representation. Restoration is semantic placeholder restoration and is not guaranteed to reconstruct the exact original surface representation of every occurrence byte-for-byte.
- **Non-Cascading Restoration**: `restore()` performs an escaped single-pass replacement, preventing recursive expansion if restored values contain placeholder syntax.
- **Atomic Updates**: If a call fails during processing, the session state, mappings, and counters remain unmodified.
- **Historical Literal Token Reservation**: Literal placeholder-like tokens observed in prior calls remain reserved so they are never assigned to real PII in later calls.
- **Unknown Placeholders**: Unmapped placeholders (e.g., `[IR_MOBILE_99]`) are left untouched without error.

---

### Custom Detectors

`fa-redact` uses Python's structural typing (protocols). Any class implementing the two-argument `detect(self, original_text: str, normalized_text: str) -> Sequence[Detection]` method can be passed to `detect()`, `redact()`, or `session.pseudonymize()`:

```python
import re
from collections.abc import Sequence

from fa_redact import Detection, detect


class MedicalRecordNumberDetector:
    """Example custom detector for synthetic institutional MRNs."""

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        detections: list[Detection] = []

        for match in re.finditer(r"\bMRN-\d{6}\b", normalized_text):
            detections.append(
                Detection.from_texts(
                    type="MRN",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=match.start(),
                    end=match.end(),
                )
            )

        return detections


# Note: Passing an explicit detector list replaces the default detector set for that call.
text = "پرونده با MRN-123456 ثبت شد."
detections = detect(text, detectors=[MedicalRecordNumberDetector()])
```

> [!NOTE]
> Passing `detectors=[...]` explicitly **replaces** the default detector list for that call. If you wish to use built-in detectors alongside custom ones, pass all desired detectors explicitly.

---

### Healthcare & AI/LLM Usage Pattern

```text
Local Hospital / Trusted Boundary
  │
  ├── 1. Raw clinical text with sensitive identifiers
  │      ↓
  ├── 2. session.pseudonymize(raw_text)
  │      ↓
  ├── 3. Pseudonymized prompt (supported identifiers replaced)
  │
  ▼  (Transmit ONLY sanitized text to External AI / Cloud)
External LLM API (e.g., Clinical Summary / Diagnostics)
  ▲
  │  (Receive response containing placeholders)
  ▼
Local Hospital / Trusted Boundary
  │
  └── 4. session.restore(llm_response)
         ↓
      5. Final clinical report with restored original identifiers
```

> [!WARNING]
> **This is not complete clinical de-identification.** `fa-redact` v0.1.0 detects only Iranian National IDs and mobile numbers. It does not detect personal names, free-text addresses, dates, or other protected health categories by default.

---

### Current Coverage & Limitations

| Identifier Type | Published (v0.1.0) | Development (Unreleased) | Notes |
| :--- | :---: | :---: | :--- |
| **Iranian National ID (`کد ملی`)** | ✅ Supported | ✅ Default | Strict 10-digit modulo-11 checksum validation |
| **Iranian Mobile Number** | ✅ Supported | ✅ Default | Prefix-aware validation against 2026 CRA numbering plan |
| **Iranian IBAN / Sheba (`شبا`)** | ❌ Not Supported | 🧪 Supported (Default) | Strict 26-char MOD-97 checksum validation (`IR` + 24 digits) |
| **Email Addresses** | ❌ Not Supported | 🧪 Supported (Opt-in) | Conservative ASCII email validation and detection (`detectors=[EmailDetector()]`) |
| **Personal Names** | ❌ Not Supported | ❌ Not Supported | Planned for future versions (requires NER/contextual models) |
| **Postal Addresses** | ❌ Not Supported | ❌ Not Supported | Unstructured spatial entities |
| **Medical Record Numbers (MRN)** | ❌ Not Supported | ❌ Not Supported | Institution-specific (use custom detectors) |
| **Health Insurance Numbers** | ❌ Not Supported | ❌ Not Supported | Institution-specific |
| **Bank Card Numbers (PAN)** | ❌ Not Supported | ❌ Not Supported | Planned for future release |
| **Dates of Birth** | ❌ Not Supported | ❌ Not Supported | Planned for future release |

---

### Privacy and Security Model

> [!WARNING]
> - **Scope Limitation**: `fa-redact` detects and redacts only the specific PII types supported by its enabled detectors (National IDs and mobile numbers in v0.1.0). It does **not** provide complete automated clinical de-identification.
> - **Sensitive Mapping Notice**: `session.mapping` contains raw, sensitive PII. Treat session instances as sensitive in-memory objects and never transmit mappings to external services.
> - **Not Production Clinical Software**: `fa-redact` is an open-source library and is **not** certified as a medical device.
> - **No Inherent Regulatory Compliance**: Using this package does not by itself establish compliance with HIPAA, GDPR, or other privacy regulations.
> - **No Identity Verification**: Validation checks confirm format and checksum validity only; they do not authenticate individuals or check registry records.
> - **Imperfect Detection**: Heuristic and rule-based detectors may yield false positives or false negatives on malformed or atypical inputs.

---

### Privacy-Safe Test Data Policy

All examples, test fixtures, and documentation in `fa-redact` are constructed from **synthetic test vectors, algorithmic patterns, and non-personal sample data**. No real patient records, clinical charts, credentials, or personal datasets are used or included in the repository.

---

### Development & Quality Checks

Run the test suite:
```bash
python -m pytest
```

Check code formatting and linting:
```bash
ruff check .
ruff format --check .
```

Run static type checking:
```bash
mypy src
mypy tests
```

Build and validate distribution packages:
```bash
python -m build
python -m twine check dist/*
```

For guidelines on contributing, see [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

---

### Release Process

For release procedures and PyPI publishing setup using GitHub Actions OIDC Trusted Publishing, see [RELEASING.md](RELEASING.md).

---

### License

This project is licensed under the [MIT License](LICENSE).

---

<a id="persian"></a>
## فارسی

`fa-redact` یک کتابخانهٔ پایتونی سبک، مستقل (بدون وابستگی خارجی / Zero-dependency) و مبتنی بر حریم خصوصی (Privacy-first) است که با هدف **تشخیص (Detection)**، **پنهان‌سازی (Redaction)** و **نام‌مستعارسازی (Pseudonymization)** اطلاعات هویتی و حساس در متون فارسی و داده‌های مرتبط با ایران طراحی شده است.

> **وضعیت نسخه: v0.1.0 (آلفا) — منتشر شده در PyPI**  
> این بسته هم‌اکنون از طریق مخزن رسمی [PyPI](https://pypi.org/project/fa-redact/) و [گیت‌هاب](https://github.com/mehdimt1980/fa-redact/releases/tag/v0.1.0) در دسترس عموم قرار دارد.

---

### فهرست مطالب

- [نمای کلی](#نمای-کلی-overview)
- [چرا fa-redact؟](#چرا-fa-redact-motivation)
- [نصب](#نصب-installation)
- [شروع سریع](#شروع-سریع-quick-start)
  - [۱. تشخیص اطلاعات هویتی (detect)](#۱-تشخیص-اطلاعات-هویتی-detect)
  - [۲. پنهان‌سازی بدون‌حالت (redact)](#۲-پنهان‌سازی-بدون‌حالت-redact)
  - [۳. نام‌مستعارسازی و بازگردانی برای هوش مصنوعی (PseudonymizationSession)](#۳-نام‌مستعارسازی-و-بازگردانی-برای-هوش-مصنوعی-pseudonymizationsession)
- [قابلیت‌های تفصیلی](#قابلیت‌های-تفصیلی)
  - [۱. نرم‌سازی با حفظ موقعیت کاراکترها](#۱-نرم‌سازی-با-حفظ-موقعیت-کاراکترها-position-preserving-normalization)
  - [۲. مدل داده و پایپ‌لاین تشخیص](#۲-مدل-داده-و-پایپ‌لاین-تشخیص)
  - [۳. اعتبارسنجی و تشخیص کد ملی ایران](#۳-اعتبارسنجی-و-تشخیص-کد-ملی-ایران)
  - [۴. اعتبارسنجی و تشخیص شماره موبایل ایران](#۴-اعتبارسنجی-و-تشخیص-شماره-موبایل-ایران)
  - [۵. اعتبارسنجی و تشخیص شماره شبا / IBAN ایران (در حال توسعه)](#۵-اعتبارسنجی-و-تشخیص-شماره-شبا--iban-ایران-در-حال-توسعه)
  - [۶. اعتبارسنجی و تشخیص آدرس ایمیل اسکی (اختیاری / در حال توسعه)](#۶-اعتبارسنجی-و-تشخیص-آدرس-ایمیل-اسکی-اختیاری--در-حال-توسعه)
  - [۷. بازسازی دقیق بر اساس span در پنهان‌سازی](#۷-بازسازی-دقیق-بر-اساس-span-در-پنهان‌سازی)
  - [۸. ویژگی‌های امنیتی و رفتاری نشست نام‌مستعارسازی](#۸-ویژگی‌های-امنیتی-و-رفتاری-نشست-نام‌مستعارسازی)
- [تشخیص‌دهنده‌های سفارشی (Custom Detectors)](#تشخیص‌دهنده‌های-سفارشی-custom-detectors)
- [کاربرد در حوزهٔ سلامت و هوش مصنوعی](#کاربرد-در-حوزهٔ-سلامت-و-هوش-مصنوعی-healthcare--aillm)
- [جدول پوشش و محدودیت‌ها در نسخه v0.1.0](#جدول-پوشش-و-محدودیت‌ها-در-نسخه-v010)
- [مدل حریم خصوصی و سلب مسئولیت‌های امنیتی](#مدل-حریم-خصوصی-و-سلب-مسئولیت‌های-امنیتی)
- [سیاست داده‌های آزمایشی امن](#سیاست-داده‌های-آزمایشی-امن)
- [توسعه و کنترل کیفیت](#توسعه-و-کنترل-کیفیت)
- [مجوز](#مجوز-license)

---

### نمای کلی (Overview)

در سیستم‌های درمانی، سازمانی و کاربردهای نوین هوش مصنوعی، ارسال متن‌های حاوی اطلاعات شناسایی‌کنندهٔ شخصی (Personally Identifiable Information یا به اختصار PII) به مدل‌های زبانی بزرگ (LLM) یا سرویس‌های ابری خارجی می‌تواند حریم خصوصی بیماران و کاربران را به خطر بیندازد. 

کتابخانهٔ `fa-redact` با ارائهٔ ابزارهای سبک و کارآمد، متن را پیش از خروج از محیط امن شما پردازش کرده و شناسه‌های حساس پشتیبانی‌شده را با نشان‌گذارهای جایگزین (Placeholders) تعویض می‌کند. پس از دریافت پاسخ از هوش مصنوعی، می‌توان نشان‌گذارها را در محیط محلی و امن خود به مقادیر اصلی بازگرداند (Restoration).

---

### چرا fa-redact؟ (Motivation)

پردازش متون فارسی در زمینهٔ امنیت داده و پالایش متون، چالش‌های منحصربه‌فردی دارد:

1. **تنوع ارقام و حروف**: در متون فارسی، شماره‌ها ممکن است با ارقام فارسی (`۰-۹`)، ارقام عربی (`٠-٩`) یا ارقام لاتین (`0-9`) نوشته شده باشند. همچنین تفاوت حروف مانند «ي» و «ك» عربی با «ی» و «ک» فارسی مانع عملکرد صحیح الگوهای ساده می‌شود.
2. **حفظ موقعیت کاراکترها (Offsets)**: روش‌های مرسوم نرم‌سازی متن اغلب طول رشته را تغییر می‌دهند (مثلاً با حذف فاصله‌ها یا اعراب)؛ این کار باعث جابه‌جایی ایندکس‌های کاراکتری شده و جایگزینی دقیق در متن اصلی را غیرممکن می‌سازد. `fa-redact` تضمین می‌کند که طول رشته قبل و بعد از نرم‌سازی یکسان باشد (`len(normalized) == len(original)`).
3. **اعتبارسنجی الگوریتمی**: به‌جای استفاده از رجکس‌های حدسی، شناسه‌های ملی و شماره‌های موبایل با قواعد کنترلی و پیش‌شماره‌های رگولاتوری ایران بررسی می‌شوند.
4. **حفظ یکپارچگی ارجاعات در هوش مصنوعی**: در مکالمات چندمرحله‌ای با LLMها، یک موجودیت مشخص همواره به یک نام‌مستعار یکسان نگاشت می‌شود تا ساختار معنایی متن برای مدل حفظ شود.
5. **بدون وابستگی و کاملاً تایپ‌شده**: بدون نیاز به بسته‌های جانبی سنگین، کاملاً با پایتون خالص (+3.10) پیاده‌سازی شده و از تایپینگ کامل (`py.typed`) پشتیبانی می‌کند.

---

### نصب (Installation)

نصب آخرین نسخهٔ پایدار از طریق مخزن رسمی PyPI:

```bash
pip install fa-redact
```

نصب برای توسعه‌دهندگان و از روی کد منبع:

```bash
git clone https://github.com/mehdimt1980/fa-redact.git
cd fa-redact
pip install -e ".[dev]"
```

---

### شروع سریع (Quick Start)

#### ۱. تشخیص اطلاعات هویتی (detect)

شناسایی بخش‌های حساس متن به همراه موقعیت دقیق کاراکتری و مقدار نرمال‌شده:

```python
from fa_redact import detect

text = "بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره ۰۹۱۲۳۴۵۶۷۸۹ مراجعه کرد."
detections = detect(text)

for item in detections:
    print(f"نوع شناسه: {item.type}")
    print(f"مقدار در متن اصلی: {item.value}")
    print(f"مقدار نرمال‌شده: {item.normalized_value}")
    print(f"موقعیت کاراکتری: [{item.start}:{item.end}]")

    # اطمینان از تطابق دقیق موقعیت با متن اصلی:
    assert text[item.start : item.end] == item.value
```

فیلدهای شیء `Detection`:
- `type`: نوع شناسهٔ شناسایی‌شده (مانند `IR_NATIONAL_ID` یا `IR_MOBILE`).
- `value`: مقدار دقیق همان‌طور که در متن ورودی نوشته شده است.
- `normalized_value`: مقدار نرمال‌شده و یکپارچهٔ شناسه.
- `start` و `end`: موقعیت شروع و پایان شناسه در متن ورودی (`text[start:end] == value`).

#### ۲. پنهان‌سازی بدون‌حالت (redact)

جایگزینی شناسه‌ها با نشان‌گذارهای نوع‌دار و امن. در هر فراخوانی، شناسه‌های تکراری نشان‌گذار یکسانی دریافت می‌کنند:

```python
from fa_redact import redact

text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱، تماس: ۰۹۱۲۳۴۵۶۷۸۹، تماس مجدد: 09123456789"
safe_text = redact(text)
print(safe_text)
# خروجی: "کد ملی: [IR_NATIONAL_ID_1]، تماس: [IR_MOBILE_1]، تماس مجدد: [IR_MOBILE_1]"
```

- تابع `redact()` بدون‌حالت (Stateless) است و نگاشتی برای بازگردانی ذخیره نمی‌کند.
- شماره‌گذاری در هر فراخوانی از `1` آغاز می‌شود.

#### ۳. نام‌مستعارسازی و بازگردانی برای هوش مصنوعی (PseudonymizationSession)

مدیریت حالت در تعاملات چندمرحله‌ای با مدل‌های زبانی (LLM) و بازگردانی محلی پاسخ‌ها:

```python
from fa_redact import PseudonymizationSession

# ایجاد یک نشست جدید
session = PseudonymizationSession()

# ۱. پنهان‌سازی متن حساس پیش از ارسال به سرویس خارجی:
prompt = "کد ملی بیمار ۱۲۳۴۵۶۷۸۹۱ و شماره تماس ۰۹۱۲۳۴۵۶۷۸۹ است."
pseudonymized_prompt = session.pseudonymize(prompt)
print(pseudonymized_prompt)
# خروجی: "کد ملی بیمار [IR_NATIONAL_ID_1] و شماره تماس [IR_MOBILE_1] است."

# ۲. ارسال فقط متن نام‌مستعارسازی‌شده (pseudonymized_prompt) به مدل زبانی. پاسخ فرضی مدل:
llm_response = "جهت هماهنگی با بیمار با [IR_MOBILE_1] تماس حاصل فرمایید."

# ۳. بازگردانی مقادیر واقعی به صورت محلی در محیط امن شما:
restored = session.restore(llm_response)
print(restored)
# خروجی: "جهت هماهنگی با بیمار با ۰۹۱۲۳۴۵۶۷۸۹ تماس حاصل فرمایید."
```

> [!WARNING]
> **هشدار امنیتی**: شیء `session.mapping` حاوی جدول نگاشت شناسه‌های اصلی و اطلاعات هویتی است. این نگاشت یک دادهٔ کاملاً حساس است؛ آن را در حافظهٔ محلی امن نگه دارید و هرگز همراه پرامپت به سرویس‌های خارجی یا LLM ارسال نکنید.

---

### قابلیت‌های تفصیلی

#### ۱. نرم‌سازی با حفظ موقعیت کاراکترها (Position-Preserving Normalization)

در `fa-redact` نرم‌سازی به شیوه‌ای کاملاً قطعی و نگاشت یک‌به‌یک کاراکترها انجام می‌شود تا ایندکس کاراکترها هیچ تغییری نکند (`len(normalized) == len(original)`):

```python
from fa_redact import normalize_digits, normalize_letters, normalize_text

# تبدیل ارقام فارسی (۰-۹) و عربی (٠-٩) به ارقام اسکی (0-9)
normalize_digits("کد بیمار: ۱۲۳٤٥")
# خروجی: "کد بیمار: 12345"

# تبدیل حروف عربی به فارسی (ي -> ی ، ك -> ک)
normalize_letters("پزشك و دكتر")
# خروجی: "پزشک و دکتر"

# نرم‌سازی جامع با حفظ طول رشته
normalize_text("كد ملي: ۰۰۱٢٣٤٥٦٧٨")
# خروجی: "کد ملی: 0012345678"
```

این توابع فاصله‌ها، نیم‌فاصله‌ها، اعراب یا علائم نگارشی را حذف نمی‌کنند تا آفست‌ها با دقت صد در صد حفظ شوند.

#### ۲. مدل داده و پایپ‌لاین تشخیص

تابع `detect()` نتایج تشخیص‌دهنده‌ها را جمع‌آوری و بر اساس `(start, end, type)` مرتب می‌کند. این لایه عمداً همپوشانی یا تشخیص‌های تکراری را حذف یا رد نمی‌کند.

کنترل همپوشانی زمانی اعمال می‌شود که قرار است متن واقعاً تغییر کند؛ یعنی در `redact()` و `PseudonymizationSession.pseudonymize()`. در این دو API، وجود spanهای همپوشان، تودرتو یا تکراری باعث `ValueError` می‌شود تا از جایگزینی‌های اشتباه و مخدوش شدن داده‌های محرمانه جلوگیری شود.

#### ۳. اعتبارسنجی و تشخیص کد ملی ایران

تشخیص و اعتبارسنجی کد ملی ۱۰ رقمی با قاعدهٔ کنترل Modulo-11 پیاده‌سازی‌شده برای کد ملی ایران:

```python
from fa_redact import IranianNationalIDDetector, is_valid_national_id

# مقادیر نمونهٔ الگوریتمی (غیرواقعی):
is_valid_national_id("1234567891")  # True (معتبر)
is_valid_national_id("۱۲۳۴۵۶۷۸۹۱")  # True (پشتیبانی از ارقام فارسی)
is_valid_national_id("1234567890")  # False (رقم کنترلی نامعتبر)
is_valid_national_id("1111111111")  # False (رد ارقام تکراری جعلی)
```

- **بررسی چکسام**: اعمال قاعدهٔ کنترلی Modulo-11 کد ملی ایران.
- **رد کدهای تکراری جعلی**: کدهایی مانند `0000000000` یا `1111111111` که فرمول چکسام را پاس می‌کنند اما نامعتبرند، رد می‌شوند.
- **طول و قالب دقیق**: ورودی باید دقیقاً ۱۰ رقم در قالب فشرده باشد؛ فاصله‌ها یا خط تیره حذف نمی‌شوند و صفرهای ابتدایی به‌طور خودکار اضافه نمی‌شوند.
- **سلب مسئولیت استعلام**: این اعتبارسنجی صرفاً ساختار ریاضی را تایید می‌کند و استعلامی از سامانه‌های ثبت احوال یا احراز هویت انجام نمی‌دهد.

#### ۴. اعتبارسنجی و تشخیص شماره موبایل ایران

اعتبارسنجی بر اساس snapshot شماره‌گذاری ۲۰۲۶ CRA/ITU و پیش‌شماره‌هایی انجام می‌شود که در آن برای خدمات موبایل تخصیص یافته‌اند:

```python
from fa_redact import IranianMobileNumberDetector, is_valid_mobile_number

# قالب‌های فشردهٔ داخلی و بین‌المللی پشتیبانی‌شده
is_valid_mobile_number("09123456789")  # True (قالب داخلی)
is_valid_mobile_number("۰۹۱۲۳۴۵۶۷۸۹")  # True (ارقام فارسی)
is_valid_mobile_number("+989123456789")  # True (قالب بین‌المللی با +98)
is_valid_mobile_number("00989351234567")  # True (قالب بین‌المللی با 0098)
is_valid_mobile_number("09412345678")  # False (شماره ثابت غیرجغرافیایی)
```

- **تفکیک پیش‌شماره‌های خدمات سیار**: بررسی پیش‌شماره‌ها بر اساس snapshot طرح شماره‌گذاری کشوری.
- **رد پیش‌شماره‌های غیرموبایل**: پیش‌شماره‌هایی نظیر `094` (ثابت غیرجغرافیایی) یا `09950` (ترانک عمومی) به عنوان موبایل پذیرفته نمی‌شوند.
- **قالب فشرده**: فقط قالب‌های فشرده (`09xxxxxxxxx`، `+989xxxxxxxxx`، `00989xxxxxxxxx`) پذیرفته می‌شوند و حذف فاصله، پرانتز یا خط تیره انجام نمی‌شود.
- **سلب مسئولیت مالکیت**: اعتبارسنجی ساختاری است و وضعیت فعال بودن سیم‌کارت، هویت مشترک، اپراتور فعلی یا ترابردپذیری را بررسی نمی‌کند.

#### ۵. اعتبارسنجی و تشخیص شماره شبا / IBAN ایران (در حال توسعه)

> [!NOTE]
> **نسخهٔ در حال توسعه (Phase 13)**: اعتبارسنجی و تشخیص شماره شبا در چرخهٔ توسعهٔ منتشرنشده اضافه شده و در نسخهٔ فعلی منتشرشده در PyPI (`0.1.0`) وجود ندارد.

کتابخانهٔ `fa-redact` تابع اعتبارسنجی مستقل `is_valid_iranian_iban` و تشخیص‌دهندهٔ `IranianIBANDetector` را برای شماره شبا / شناسه حساب بانکی ایران (IBAN) به صورت کاملاً آفلاین، قطعی و بدون وابستگی خارجی ارائه می‌دهد. ساختار شماره شبا در قالب فشرده الکترونیکی شامل ۲۶ کاراکتر است: پیشوند `IR`، به همراه ۲ رقم کنترلی و BBAN بیست‌ودورقمی (یا `IR` به همراه ۲۴ رقم عددی):

```python
from fa_redact import (
    IranianIBANDetector,
    PseudonymizationSession,
    detect,
    is_valid_iranian_iban,
    redact,
)

# ۱. اعتبارسنجی مستقل (دقیقاً ۲۶ کاراکتر: IR بزرگ + ۲۴ رقم با الگوریتم MOD-97):
is_valid_iranian_iban("IR641234567890123456789012")  # True (معتبر)
is_valid_iranian_iban("IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲")  # True (پشتیبانی از ارقام فارسی)
is_valid_iranian_iban("ir641234567890123456789012")  # False (رد حروف کوچک ir)
is_valid_iranian_iban("IR 64 1234 5678 9012 3456 7890 12")  # False (رد فاصله)
is_valid_iranian_iban("IR001234567890123456789012")  # False (چکسام نامعتبر)

# ۲. تشخیص پیش‌فرض (قرارگیری در مجموعهٔ تشخیص‌دهنده‌های پیش‌فرض):
text = "شماره شبا واریز: IR641234567890123456789012 و تماس ۰۹۱۲۳۴۵۶۷۸۹"
detections = detect(text)
# خروجی: [Detection(type='IR_IBAN', ...), Detection(type='IR_MOBILE', ...)]

# ۳. پنهان‌سازی و نام‌مستعارسازی پیش‌فرض:
safe_text = redact(text)
# خروجی: "شماره شبا واریز: [IR_IBAN_1] و تماس [IR_MOBILE_1]"

session = PseudonymizationSession()
pseudonymized = session.pseudonymize("واریز به شبا IR641234567890123456789012")
# خروجی: "واریز به شبا [IR_IBAN_1]"

restored = session.restore("تایید واریز به [IR_IBAN_1]")
# خروجی: "تایید واریز به IR641234567890123456789012"
```

- **الگوریتم چکسام MOD-97-10**: اعتبارسنجی استاندارد بین‌المللی ISO 7064 MOD 97-10 از طریق بازآرایی رشته به فرمت `BBAN (۲۲ رقم) + 1827 (IR) + ارقام کنترلی (۲ رقم)` و بررسی شرط `باقیمانده == 1`.
- **حضور در پایپ‌لاین پیش‌فرض**: برخلاف `EmailDetector`، تشخیص‌دهندهٔ `IranianIBANDetector` در مجموعهٔ پیش‌فرض (`_DEFAULT_DETECTORS`) قرار دارد؛ زیرا ساختار مشخص آن (`IR` به همراه ۲۴ رقم) هیچ‌گونه تداخل یا ابهام سینتکسی با کدهای ملی یا شماره‌های موبایل ایجاد نمی‌کند.
- **حفظ موقعیت کاراکتری و پشتیبانی از ارقام متنوع**: امکان استفاده از ارقام فارسی (`۰-۹`) و عربی (`٠-٩`) در ۲۴ نویسهٔ عددی پس از `IR` وجود دارد؛ این بخش شامل ۲ رقم کنترلی و BBAN بیست‌ودورقمی است. نگاشت در `Detection.value` بر اساس متن ورودی حفظ شده و مقدار یکپارچه در `Detection.normalized_value` قرار می‌گیرد.
- **قالب فشردهٔ الکترونیکی**: صرفاً فرمت الکترونیکی فشرده بدون فاصله، خط تیره یا جداکننده پذیرفته می‌شود. پیشوند `ir` با حروف کوچک نیز پذیرفته نمی‌شود.
- **سلب مسئولیت بانکی و حریم خصوصی**: تابع `is_valid_iranian_iban` صرفاً صحت ساختار ریاضی چکسام را به صورت محلی و آفلاین بررسی می‌کند. این تابع هیچ‌گونه استعلام بانکی، بررسی صحت شماره حساب، اتصال به شبکهٔ شتاب یا پایا انجام نمی‌دهد و فعال بودن حساب بانکی را تایید نمی‌کند.

#### ۶. اعتبارسنجی و تشخیص آدرس ایمیل اسکی (اختیاری / در حال توسعه)

> [!NOTE]
> **نسخهٔ در حال توسعه (Phase 12)**: اعتبارسنجی و تشخیص آدرس ایمیل در چرخهٔ توسعهٔ منتشرنشده اضافه شده و در نسخهٔ فعلی منتشرشده در PyPI (`0.1.0`) وجود ندارد.

کتابخانهٔ `fa-redact` تابع اعتبارسنجی مستقل `is_valid_email` و تشخیص‌دهندهٔ `EmailDetector` را برای آدرس‌های ایمیل استاندارد اسکی به صورت بدون وابستگی ارائه می‌دهد:

```python
from fa_redact import (
    EmailDetector,
    PseudonymizationSession,
    detect,
    is_valid_email,
    redact,
)

# ۱. اعتبارسنجی ساختاری مستقل:
is_valid_email("user.name@example.com")  # True (معتبر)
is_valid_email("doctor@sub.hospital.ir")  # True (معتبر)
is_valid_email("user@localhost")  # False (رد دامنه‌های تک‌بخشی)
is_valid_email("user+tag@invalid_domain.com")  # False (رد آندرلاین در دامنه)
is_valid_email("user@مثال.ایران")  # False (عدم پشتیبانی از ایمیل‌های غیر اسکی)

# ۲. تشخیص با فعال‌سازی اختیاری (Opt-in):
text = "مکاتبه با دکتر احمدی: dr.ahmadi@hospital.ir و تماس 09123456789"
detections = detect(text, detectors=[EmailDetector()])
# خروجی: [Detection(type='EMAIL', value='dr.ahmadi@hospital.ir', ...)]

# ۳. پنهان‌سازی و نام‌مستعارسازی اختیاری:
safe_text = redact(text, detectors=[EmailDetector()])
# خروجی: "مکاتبه با دکتر احمدی: [EMAIL_1] و تماس 09123456789"

session = PseudonymizationSession()
pseudonymized = session.pseudonymize(
    "تماس با info@clinic.ir یا dr.ahmadi@hospital.ir انجام شد.",
    detectors=[EmailDetector()],
)
# خروجی: "تماس با [EMAIL_1] یا [EMAIL_2] انجام شد."

restored = session.restore("پیام به [EMAIL_1] ارسال شد.")
# خروجی: "پیام به info@clinic.ir ارسال شد."
```

- **معماری اختیاری (Opt-in)**: کلاس `EmailDetector` در فاز ۱۲ به صورت اختیاری ارائه شده و در مجموعهٔ پیش‌فرض قرار ندارد. ایمیل‌هایی با بخش محلی عددی (مانند `09123456789@example.com`) ممکن است با تشخیص‌دهنده‌های موبایل یا کد ملی همپوشانی ایجاد کنند. از آنجا که `redact()` و `pseudonymize()` در صورت وجود همپوشانی خطا می‌دهند، فعال‌سازی ایمیل تا زمان پیاده‌سازی مکانیزم حل تعارض به صورت صریح و اختیاری خواهد بود.
- **پیکربندی تشخیص‌دهنده‌ها در هر فراخوانی (Per-Call Detectors)**: کلاس `PseudonymizationSession` وضعیت نگاشت و شمارنده‌های نام‌مستعارسازی را نگه می‌دارد، اما مجموعهٔ تشخیص‌دهنده‌ها را در خود ذخیره نمی‌کند. تشخیص‌دهنده‌ها در سازندهٔ `PseudonymizationSession` تنظیم نمی‌شوند و برای هر فراخوانی `pseudonymize()` باید در صورت نیاز آرگومان `detectors=[...]` به‌صورت صریح ارسال شود.
- **قالب استاندارد اسکی (Conservative ASCII)**: اعتبارسنجی بخش محلی dot-atom (حداکثر ۶۴ کاراکتر)، نام دامنهٔ ساختاریافته مطابق DNS (حداکثر ۲۵۳ کاراکتر دامنه، ۱ تا ۶۳ کاراکتر برای هر برچسب، حداقل ۲ کاراکتر برای TLD و حداکثر ۲۵۴ کاراکتر برای کل آدرس).
- **قالب‌های پشتیبانی‌نشده**: ساختارهای پیچیده یا منسوخ مانند رشته‌های کوتیشن‌دار (`"john doe"@example.com`)، دامنه‌های لیترال IP (`user@[192.168.1.1]`)، کامنت‌ها، فاصله‌های شکسته‌شده (folding whitespace)، دامنه‌های تک‌بخشی (`user@localhost`) و ایمیل‌های بین‌المللی غیر اسکی (EAI / RFC 6530+) پذیرفته نمی‌شوند.
- **سلب مسئولیت و حریم خصوصی**: تابع `is_valid_email` صرفاً ساختار نگارشی را به صورت محلی و آفلاین بررسی می‌کند. این تابع هیچ‌گونه درخواست شبکه، استعلام DNS یا بررسی وجود صندوق پستی (Mailbox) انجام نمی‌دهد و هیچ داده‌ای را لاگ نمی‌کند. صحت ساختاری به منزلهٔ وجود واقعی آدرس ایمیل نیست.

#### ۷. بازسازی دقیق بر اساس span در پنهان‌سازی

خروجی بر اساس بازه‌های دقیق `Detection` از متن اصلی ساخته می‌شود؛ فقط همان spanهای تشخیص‌داده‌شده جایگزین می‌شوند و بخش‌های دیگر متن بدون تغییر کپی می‌شوند. پیاده‌سازی از `str.replace()` سراسری بر اساس مقدار استفاده نمی‌کند.

#### ۸. ویژگی‌های امنیتی و رفتاری نشست نام‌مستعارسازی

کلاس `PseudonymizationSession` رفتارهای امنیتی زیر را تضمین می‌کند:

- **ایزوله‌سازی نشست‌ها (Mapping Isolation)**: هر نشست دارای حافظه و نگاشت مستقل است.
- **یکپارچگی هویت در چند مرحله (Cross-Call Identity)**: هویت یک موجودیت بر اساس `(type, normalized_value)` ردیابی می‌شود. بنابراین `۰۹۱۲۳۴۵۶۷۸۹` در نوبت اول و `09123456789` در نوبت دوم هر دو به `[IR_MOBILE_1]` متصل می‌شوند.
- **محدودیت تفاوت فرمت داخلی و بین‌المللی**: مقادیر `09123456789` و `+989123456789` دارای رشته‌های نرمال‌شدهٔ متفاوتی هستند و در نسخهٔ v0.1.0 به یک هویت یکسان تبدیل نمی‌شوند.
- **بازگردانی به اولین نمایش دیده‌شده (First-Observed Representative)**: تابع `restore()` یک بازگردانی معنایی بر اساس placeholder انجام می‌دهد و تضمین نمی‌کند که شکل نویسه‌ای دقیق تک‌تک occurrenceهای متن اولیه به‌صورت byte-for-byte بازسازی شود.
- **بازگردانی غیرآبشاری (Non-Cascading Restore)**: بازگردانی در یک مرحله و با فرار کاراکترهای خاص انجام می‌شود تا اگر مقدار بازگردانده‌شده شبیه به نشان‌گذار باشد، بازگردانی بازگشتی و ناخواسته رخ ندهد.
- **به‌روزرسانی اتمیک (Atomic Updates)**: اگر در حین پردازش خطایی رخ دهد، وضعیت نشست و شمارنده‌ها دست‌نخورده باقی می‌مانند.
- **محافظت در برابر تداخل تاریخی با نشان‌گذارهای متنی**: اگر در متون قبلی عبارتی مانند `[IR_MOBILE_2]` به عنوان متن عادی وجود داشته باشد، سیستم آن شماره را رزرو کرده و برای شناسه‌های واقعی جدید اختصاص نمی‌دهد.
- **عدم دستکاری نشان‌گذارهای ناشناخته**: نشان‌گذارهایی که در نگاشت نشست ثبت نشده‌اند (مانند `[IR_MOBILE_99]`) بدون خطا و دست‌نخورده باقی می‌مانند.

---

### تشخیص‌دهنده‌های سفارشی (Custom Detectors)

معماری `fa-redact` مبتنی بر پروتکل‌های ساختاری پایتون (Duck Typing) است. شما می‌توانید کلاسی با متد دوآرگومانی پیاده‌سازی کنید:

```python
import re
from collections.abc import Sequence

from fa_redact import Detection, detect


class MedicalRecordNumberDetector:
    """نمونه تشخیص‌دهنده سفارشی برای شماره پرونده پزشکی بیمارستانی (MRN)."""

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        detections: list[Detection] = []

        for match in re.finditer(r"\bMRN-\d{6}\b", normalized_text):
            detections.append(
                Detection.from_texts(
                    type="MRN",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=match.start(),
                    end=match.end(),
                )
            )

        return detections


# توجه: پاس دادن فهرست اختصاصی تشخیص‌دهنده‌ها، مجموعهٔ پیش‌فرض را برای آن فراخوانی جایگزین می‌کند.
text = "پرونده با MRN-123456 ثبت شد."
detections = detect(text, detectors=[MedicalRecordNumberDetector()])
```

در این پروتکل:
- `original_text`: متن اصلی و دست‌نخورده است.
- `normalized_text`: نسخهٔ نرمال‌شده با طول دقیقاً برابر است.
- تشخیص‌دهنده باید spanها را طوری برگرداند که offsetها در هر دو رشته یکسان باشند (استفاده از `Detection.from_texts()` این موضوع را تضمین می‌کند).
- پاس دادن `detectors=[...]` مجموعهٔ تشخیص‌دهنده‌های پیش‌فرض را برای آن فراخوانی جایگزین می‌کند و به‌طور خودکار به آن‌ها افزوده نمی‌شود.

---

### کاربرد در حوزهٔ سلامت و هوش مصنوعی (Healthcare & AI/LLM)

```text
محیط محلی و امن بیمارستان / سازمان
  │
  ├── ۱. متن پرونده حاوی شناسه‌های حساس بیمار
  │      ↓
  ├── ۲. session.pseudonymize(raw_text)
  │      ↓
  ├── ۳. پرامپت نام‌مستعارسازی‌شده (فقط شناسه‌های پشتیبانی‌شده جایگزین شده‌اند)
  │
  ▼  (ارسال صرفاً متن پالایش‌شده به هوش مصنوعی خارج از سازمان)
سرویس مدل زبانی بزرگ (LLM API)
  ▲
  │  (دریافت پاسخ شامل نشان‌گذارها)
  ▼
محیط محلی و امن بیمارستان / سازمان
  │
  └── ۴. session.restore(llm_response)
         ↓
      ۵. گزارش نهایی با شناسه‌های واقعی و بازگردانی‌شده
```

> [!WARNING]
> **این فرایند به معنی ناشناس‌سازی یا de-identification کامل متن بالینی نیست.** `fa-redact` در نسخهٔ v0.1.0 صرفاً کد ملی و شماره موبایل ایران را پوشش می‌دهد و داده‌هایی نظیر نام اشخاص، آدرس‌ها، تاریخ‌ها یا سایر رده‌های سلامت حفاظت‌شده را به‌طور پیش‌فرض تشخیص نمی‌دهد.

---

### جدول پوشش و محدودیت‌ها

| نوع شناسه هویتی | وضعیت در v0.1.0 (منتشر شده) | نسخه در حال توسعه (Unreleased) | توضیحات |
| :--- | :---: | :---: | :--- |
| **کد ملی ایران** | ✅ پشتیبانی می‌شود | ✅ پیش‌فرض | اعتبارسنجی دقیق ۱۰ رقمی با قاعدهٔ چکسام Modulo-11 |
| **شماره تلفن همراه ایران** | ✅ پشتیبانی می‌شود | ✅ پیش‌فرض | اعتبارسنجی پیش‌شماره‌های مصوب رگولاتوری ایران (CRA 2026) |
| **شماره شبا (IBAN)** | ❌ پشتیبانی نمی‌شود | 🧪 پشتیبانی می‌شود (پیش‌فرض) | اعتبارسنجی دقیق ۲۶ کاراکتری با قاعدهٔ چکسام MOD-97 (`IR` + ۲۴ رقم) |
| **آدرس ایمیل** | ❌ پشتیبانی نمی‌شود | 🧪 پشتیبانی می‌شود (اختیاری) | اعتبارسنجی و تشخیص ایمیل‌های اسکی محافظه‌کارانه (`detectors=[EmailDetector()]`) |
| **نام اشخاص** | ❌ پشتیبانی نمی‌شود | ❌ پشتیبانی نمی‌شود | نیازمند مدل‌های پردازش زبان طبیعی و بازشناسی موجودیت‌های نام‌دار (NER) |
| **آدرس پستی و موقعیت مکانی** | ❌ پشتیبانی نمی‌شود | ❌ پشتیبانی نمی‌شود | موجودیت‌های غیرساختاریافته |
| **شماره پرونده پزشکی (MRN)** | ❌ پشتیبانی نمی‌شود | ❌ پشتیبانی نمی‌شود | فرمت سازمانی (قابل تعریف با Custom Detector) |
| **شماره بیمه درمانی** | ❌ پشتیبانی نمی‌شود | ❌ پشتیبانی نمی‌شود | فرمت سازمانی |
| **شماره کارت بانکی (PAN)** | ❌ پشتیبانی نمی‌شود | ❌ پشتیبانی نمی‌شود | برنامه‌ریزی‌شده برای نسخه‌های آتی |
| **تاریخ تولد و زمان‌ها** | ❌ پشتیبانی نمی‌شود | ❌ پشتیبانی نمی‌شود | برنامه‌ریزی‌شده برای نسخه‌های آتی |

---

### مدل حریم خصوصی و سلب مسئولیت‌های امنیتی

> [!WARNING]
> - **محدودیت دامنهٔ پوشش**: این بسته در نسخهٔ فعلی (v0.1.0) صرفاً کد ملی و شماره موبایل ایران را پوشش می‌دهد و به هیچ وجه سیستم دی‌ایدنتیفیکیشن (De-identification) کامل پرونده‌های پزشکی بالینی نیست.
> - **حساسیت نگاشت**: نگاشت `session.mapping` حاوی PII واقعی است و باید با بالاترین تدابیر امنیتی در حافظهٔ محلی نگهداری شود.
> - **عدم گواهی پزشکی**: `fa-redact` یک نرم‌افزار تجهیزات پزشکی (Medical Device) تأییدشده نیست.
> - **عدم انطباق خودکار با مقررات**: استفاده از این ابزار به خودی خود انطباق کامل با قوانین بین‌المللی نظیر HIPAA یا GDPR را تضمین نمی‌کند.
> - **عدم استعلام هویت**: توابع اعتبارسنجی صرفاً ساختار ریاضی را بررسی می‌کنند و استعلام هویتی انجام نمی‌دهند.
> - **احتمال خطای الگوریتمی**: هیچ سیستم مبتنی بر قاعده بدون خطا نیست؛ ممکن است در ورودی‌های غیرمعمول با خطای مثبت یا منفی کاذب (False Positives / False Negatives) مواجه شوید.

---

### سیاست داده‌های آزمایشی امن

کلیهٔ مثال‌ها، داک‌ها و تست‌های موجود در این مخزن بر پایهٔ **داده‌های مصنوعی، الگوهای الگوریتمی و بردارهای تستی غیرشخصی** تولید شده‌اند. هیچ‌گونه اطلاعات واقعی هویتی، پرونده پزشکی، یا داده‌های محرمانهٔ کاربران در این مخزن استفاده یا ذخیره نشده است.

---

### توسعه و کنترل کیفیت

اجرای تست‌های خودکار:
```bash
python -m pytest
```

بررسی سبک کدنویسی و لینتینگ:
```bash
ruff check .
ruff format --check .
```

بررسی ایستا و تایپ‌چکینگ:
```bash
mypy src
mypy tests
```

بیلد پکیج و بررسی صحت توزیع‌ها:
```bash
python -m build
python -m twine check dist/*
```

برای آگاهی از نحوهٔ مشارکت در پروژه، راهنماهای [CONTRIBUTING.md](CONTRIBUTING.md) و [SECURITY.md](SECURITY.md) را مطالعه فرمایید.

---

### مجوز (License)

این پروژه تحت [مجوز MIT](LICENSE) منتشر شده است.
