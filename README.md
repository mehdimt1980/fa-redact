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

> **Status: Alpha**  
> Package version in this source tree: `v0.2.0`.  
> Published releases are available on [PyPI](https://pypi.org/project/fa-redact/) and [GitHub Releases](https://github.com/mehdimt1980/fa-redact/releases). The PyPI badge above reflects the latest published PyPI version.

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
  - [5. Iranian IBAN / Sheba Validation & Detection](#5-iranian-iban--sheba-validation--detection)
  - [6. Conservative ASCII Email Validation & Detection (Opt-in)](#6-conservative-ascii-email-validation--detection-opt-in)
  - [7. Bank Card / PAN Validation & Detection (Opt-in)](#7-bank-card--pan-validation--detection-opt-in)
  - [8. Configurable Institutional / Healthcare Identifiers (Opt-in)](#8-configurable-institutional--healthcare-identifiers-opt-in)
  - [9. Explicit Detection Conflict Resolution (Opt-in)](#9-explicit-detection-conflict-resolution-opt-in)
  - [10. Privacy-Safe Detection Reports (Unreleased)](#10-privacy-safe-detection-reports-unreleased)
  - [11. Redaction Semantics](#11-redaction-semantics)
  - [12. Stateful Pseudonymization Sessions](#12-stateful-pseudonymization-sessions)
  - [13. Command-Line Interface (CLI) (Unreleased)](#13-command-line-interface-cli-unreleased)
  - [14. Structured Data Helpers (Unreleased)](#14-structured-data-helpers-unreleased)
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
redacted_text = redact(text)
print(redacted_text)
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

#### 5. Iranian IBAN / Sheba Validation & Detection

> [!NOTE]
> **Introduced in v0.2.0**: Iranian IBAN validation and detection (`IranianIBANDetector` and `is_valid_iranian_iban`) are included in `fa-redact` v0.2.0 as part of the default detector set.

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
redacted_text = redact(text)
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

#### 6. Conservative ASCII Email Validation & Detection (Opt-in)

> [!NOTE]
> **Introduced in v0.2.0**: Email validation and detection (`EmailDetector` and `is_valid_email`) are introduced in `fa-redact` v0.2.0 as an opt-in detector.

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
redacted_text = redact(text, detectors=[EmailDetector()])
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

#### 7. Bank Card / PAN Validation & Detection (Opt-in)

> [!NOTE]
> **Introduced in v0.2.0**: Bank card validation and detection (`BankCardDetector` and `is_valid_bank_card_number`) are introduced in `fa-redact` v0.2.0 as an opt-in detector.

`fa-redact` provides an offline, deterministic 16-digit payment card (Primary Account Number / PAN) validator (`is_valid_bank_card_number`) and detector (`BankCardDetector`):

```python
from fa_redact import (
    BankCardDetector,
    PseudonymizationSession,
    detect,
    is_valid_bank_card_number,
    redact,
)

# 1. Standalone Validation (Exact 16 digits, Luhn MOD-10 checksum)
is_valid_bank_card_number("1234567890123452")  # True (valid synthetic card)
is_valid_bank_card_number("۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۲")  # True (Persian digits)
is_valid_bank_card_number("١٢٣٤٥٦٧٨٩٠١٢٣٤٥٢")  # True (Arabic-Indic digits)
is_valid_bank_card_number("1234 5678 9012 3452")  # False (spaces rejected)
is_valid_bank_card_number("1234-5678-9012-3452")  # False (hyphens rejected)
is_valid_bank_card_number("0000000000000000")  # False (all-identical rejected)
is_valid_bank_card_number("1234567890123453")  # False (checksum mismatch)

# 2. Opt-in Detection (Pass BankCardDetector explicitly)
text = "شماره کارت: 1234567890123452"
detections = detect(text, detectors=[BankCardDetector()])
# Returns: [Detection(type='BANK_CARD', value='1234567890123452', ...)]

# 3. Opt-in Redaction & Pseudonymization
redacted_text = redact(text, detectors=[BankCardDetector()])
# Output: "شماره کارت: [BANK_CARD_1]"

session = PseudonymizationSession()
pseudonymized = session.pseudonymize(
    "واریز به کارت ۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۲ انجام شد.",
    detectors=[BankCardDetector()],
)
# Output: "واریز به کارت [BANK_CARD_1] انجام شد."

restored = session.restore("تایید واریز به [BANK_CARD_1]")
# Output: "تایید واریز به ۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۲"
```

- **Opt-in Architecture**: `BankCardDetector` is intentionally **opt-in** and is not included in the default detector set (`_DEFAULT_DETECTORS`).
- **Standard Luhn MOD-10 Checksum**: Validates 16-digit payment card numbers using the standard Luhn algorithm (doubling digits at odd offsets from the right, subtracting 9 if the product exceeds 9, and verifying `sum % 10 == 0`).
- **Position-Preserving Digit Normalization**: Accepts ASCII (`0-9`), Persian (`۰-۹`), and Arabic-Indic (`٠-٩`) digits. Preserves the exact surface script in `Detection.value` and normalizes to canonical ASCII in `Detection.normalized_value`.
- **Defensive Sequence Filtering**: Trivial all-identical sequences (such as `0000000000000000` through `9999999999999999`) are defensively rejected regardless of their Luhn checksum status.
- **Strict Electronic Compact Format**: Only compact 16-digit strings without spaces, hyphens, or formatting separators are accepted. The validator does not strip whitespace, remove hyphens, or clean up formatting.
- **Issuer Neutrality**: `BankCardDetector` uses issuer-neutral terminology and entities (`BANK_CARD`). The library does not maintain an Iranian BIN/IIN registry and does not verify whether a card was issued by an Iranian bank or any specific card network.
- **Privacy & Financial Disclaimer**: `is_valid_bank_card_number` performs purely local, offline mathematical checksum validation. It does not perform payment gateway verification, card activation status checks, CVV2/expiry checks, or account balance lookups. Checksum validity does not prove that a payment card exists, is active, or belongs to a specific cardholder.

#### 8. Configurable Institutional / Healthcare Identifiers (Opt-in)

> [!NOTE]
> **Introduced in v0.2.0**: Configurable institutional identifier detection (`PatternRule` and `PatternDetector`) is introduced in `fa-redact` v0.2.0 as an opt-in detector.

MRNs (Medical Record Numbers), Patient IDs, Admission IDs, Encounter IDs, Case IDs, and similar clinical/enterprise identifiers are institution-specific. `fa-redact` does not pretend there is one universal regex for them, nor does it hardcode synthetic assumptions into package defaults.

Instead, `fa-redact` provides a lightweight, immutable configuration layer (`PatternRule` and `PatternDetector`) allowing hospitals and applications to supply their own identifier patterns:

```python
import re
from fa_redact import (
    PatternDetector,
    PatternRule,
    PseudonymizationSession,
    detect,
    redact,
)

# 1. Define institution-specific identifier rules
hospital_detector = PatternDetector(
    [
        # Standard full-match identifier (MRN)
        PatternRule(
            type="MRN",
            pattern=r"(?<!\w)MRN-[0-9]{6}(?!\w)",
        ),
        # Context-aware rule extracting only the ID using a capture group
        PatternRule(
            type="PATIENT_ID",
            pattern=r"Patient\s*ID\s*:\s*(?P<id>PAT-[A-Z]{2}-[0-9]{8})",
            group="id",
            flags=re.IGNORECASE,
        ),
        # Admission ID
        PatternRule(
            type="ADMISSION_ID",
            pattern=r"(?<!\w)ADM-20[0-9]{2}-[0-9]{6}(?!\w)",
        ),
        # Encounter ID
        PatternRule(
            type="ENCOUNTER_ID",
            pattern=r"(?<!\w)ENC-[0-9]{10}(?!\w)",
        ),
    ]
)

# 2. Detect with normalized Persian digits matching ASCII regexes
text = "پرونده: MRN-۱۲۳۴۵۶ و Patient ID: PAT-TE-12345678"
detections = detect(text, detectors=[hospital_detector])
# Returns:
# - Detection(type='MRN', value='MRN-۱۲۳۴۵۶', normalized_value='MRN-123456', span=[8:18])
# - Detection(type='PATIENT_ID', value='PAT-TE-12345678', normalized_value='PAT-TE-12345678', span=[33:48])

# 3. Redact (leaving context labels like 'Patient ID: ' untouched)
redacted = redact(text, detectors=[hospital_detector])
# Output: "پرونده: [MRN_1] و Patient ID: [PATIENT_ID_1]"

# 4. Stateful Pseudonymization across mixed scripts
session = PseudonymizationSession()
# Turn 1: Persian digits
turn1 = session.pseudonymize("پرونده: MRN-۱۲۳۴۵۶", detectors=[hospital_detector])
# Output: "پرونده: [MRN_1]"

# Turn 2: ASCII digits (resolves to same [MRN_1] identity)
turn2 = session.pseudonymize("پیگیری پرونده MRN-123456", detectors=[hospital_detector])
# Output: "پیگیری پرونده [MRN_1]"

# Restore recovers first-observed Persian representation locally
restored = session.restore("پاسخ به [MRN_1]")
# Output: "پاسخ به MRN-۱۲۳۴۵۶"
```

- **Opt-in Architecture**: `PatternDetector` is strictly **opt-in** and is not included in `_DEFAULT_DETECTORS`. Explicit `detectors=[hospital_detector]` replaces default detectors for that call.
- **Position-Preserving Digit Normalization**: By default (`source="normalized"`), patterns match against position-preserving normalized text. A single ASCII regex such as `MRN-[0-9]{6}` matches Persian (`MRN-۱۲۳۴۵۶`), Arabic-Indic (`MRN-١٢٣٤٥٦`), and ASCII (`MRN-123456`) forms, preserving surface script in `Detection.value` and mapping to identical `(type, normalized_value)` pseudonym identities.
- **Raw Matching Mode**: For institutions requiring candidate matching strictly on unnormalized text, `source="original"` is supported.
- **Context-Aware Capture Groups**: Supports integer indices (`group=1`) and named capture groups (`group="id"`), allowing the detector to match context prefixes (e.g. `Patient ID: `) while extracting only the identifier into the detection span. Nonparticipating capture groups fail loud with a `ValueError`.
- **Regex Boundary Ownership**: `PatternDetector` does not wrap configured patterns with word boundaries (`\b` or `(?<!\w)`). Institutions own full regex semantics.
- **Pre-Compiled & Immutable**: `PatternRule` is an immutable frozen dataclass. Rules are compiled once during `PatternDetector` construction.

> [!WARNING]
> - **Synthetic Demonstration Patterns Only**: The example patterns shown above (`MRN-[0-9]{6}`, `PAT-AB-...`) are purely synthetic demonstration examples. They are **not** healthcare standards.
> - **Trusted Configuration Security Notice**: Pattern rules are trusted application configuration. Python's standard `re` engine does not provide a built-in match timeout. Do not execute arbitrary unreviewed regexes supplied by untrusted users, tenants, LLMs, or external configuration sources.
> - **Offline Syntactic Matching Only**: A regex match proves only that configured syntax matched. It does not perform HIS/FHIR lookups, database queries, or network requests, and does not verify that a patient, encounter, admission, or hospital record exists.

#### 9. Explicit Detection Conflict Resolution (Opt-in)

> [!NOTE]
> **Introduced in v0.2.0**: Explicit conflict resolution (`ConflictPolicy` and `resolve_detection_conflicts`) is introduced in `fa-redact` v0.2.0.

`detect()` always returns raw detector evidence and intentionally preserves overlapping and duplicate detections. This design allows callers to audit and inspect raw matches without hidden priority heuristics.

By default, downstream functions (`redact()` and `PseudonymizationSession.pseudonymize()`) operate under `conflict_policy="reject"`, failing loudly if any overlapping, nested, or duplicate detections exist:

```python
from fa_redact import BankCardDetector, EmailDetector, redact

text = "ایمیل: 1234567890123452@example.com"
detectors = [EmailDetector(), BankCardDetector()]

# Default reject policy: raises ValueError because EMAIL and BANK_CARD spans overlap
# redact(text, detectors=detectors)  # -> ValueError: Overlapping detections at spans [7:35] (EMAIL) and [7:23] (BANK_CARD)
```

For callers who understand the ambiguity and choose to resolve conflicts explicitly, `fa-redact` provides two opt-in resolution policies:

##### 1. Longest Span Policy (`conflict_policy="longest"`)

Greedily selects the longest matching span and discards shorter overlapping candidates. Exact duplicates are collapsed into one. Ambiguous equal-length overlapping spans raise a `ValueError`:

```python
# Longest policy selects the full EMAIL span (length 28) over BANK_CARD (length 16)
redacted_longest = redact(text, detectors=detectors, conflict_policy="longest")
# Output: "ایمیل: [EMAIL_1]"
```

##### 2. Explicit Type Priority Policy (`conflict_policy="priority"`)

Resolves conflicts based on an explicit user-configured sequence of entity types in descending priority order (`type_priority=[...]`). Higher priority types win over lower priority types regardless of span length:

```python
# Priority: BANK_CARD > EMAIL
card_first = redact(
    text,
    detectors=detectors,
    conflict_policy="priority",
    type_priority=["BANK_CARD", "EMAIL"],
)
# Output: "ایمیل: [BANK_CARD_1]@example.com"

# Priority: EMAIL > BANK_CARD
email_first = redact(
    text,
    detectors=detectors,
    conflict_policy="priority",
    type_priority=["EMAIL", "BANK_CARD"],
)
# Output: "ایمیل: [EMAIL_1]"
```

##### Standalone Conflict Resolver for Auditing

Callers can inspect and resolve raw detections independently before redaction:

```python
from fa_redact import detect, resolve_detection_conflicts

raw_detections = detect(text, detectors=detectors)
# Returns 2 overlapping detections: EMAIL and BANK_CARD

resolved_detections = resolve_detection_conflicts(
    raw_detections,
    policy="longest",
)
# Returns 1 detection: EMAIL
```

> [!WARNING]
> - **Heuristic Policy Disclaimer**: Conflict resolution is heuristic policy, not entity verification. Resolving a conflict does not verify the real-world semantic identity of a string.
> - **Substring Exposure Risk**: Selecting `longest` or `priority` may discard a detection that covers characters extending outside the winning detection. For example, selecting a shorter `BANK_CARD` over an `EMAIL` leaves `@example.com` unredacted in the output.
> - **Conservative Recommendation**: In cases of uncertainty or high-risk privacy requirements, keep the default `reject` policy.

#### 10. Privacy-Safe Detection Reports (Unreleased)

> [!NOTE]
> **Unreleased / Development**: Privacy-safe detection reporting (`DetectionReport`, `detection_report`, and `report_detections`) is in active development in this repository and is not included in published release v0.2.0.

`fa-redact` provides a dedicated value-free reporting layer that summarizes detection evidence without retaining, storing, or returning detected PII values, normalized values, source text, character offsets, spans, snippets, or PII hashes.

##### 1. Basic Detection Report

Generate a value-free summary directly from text using built-in or custom detectors:

```python
from fa_redact import detection_report

text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱، همراه: ۰۹۱۲۳۴۵۶۷۸۹"
report = detection_report(text)

print(report.total_detections)  # 2
print(dict(report.counts))  # {'IR_MOBILE': 1, 'IR_NATIONAL_ID': 1}
print(report.distinct_types)  # 2
print(report.has_conflicts)  # False
print(report.conflict_pairs)  # 0
print(report.conflicting_detections)  # 0
print(report.duplicate_groups)  # 0
```

##### 2. Raw Evidence & Conflict Observability

`detection_report()` runs raw detector evidence without automatic conflict resolution. This exposes whether ambiguities or conflicts exist across active detectors:

```python
from fa_redact import (
    BankCardDetector,
    EmailDetector,
    detection_report,
)

text = "ایمیل: 1234567890123452@example.com"
report = detection_report(
    text,
    detectors=[
        EmailDetector(),
        BankCardDetector(),
    ],
)

print(report.total_detections)  # 2
print(dict(report.counts))  # {'BANK_CARD': 1, 'EMAIL': 1}
print(report.has_conflicts)  # True
print(report.conflict_pairs)  # 1
print(report.conflicting_detections)  # 2
```

##### 3. Standalone Report Before & After Resolution

Callers can summarize already-produced `Detection` sequences using `report_detections()`, enabling transparent pre- and post-resolution comparison:

```python
from fa_redact import (
    detect,
    report_detections,
    resolve_detection_conflicts,
)

# 1. Raw detector evidence
raw_detections = detect(text, detectors=detectors)
raw_report = report_detections(raw_detections)
# raw_report.has_conflicts is True, raw_report.total_detections == 2

# 2. Resolved detections under explicit policy
resolved_detections = resolve_detection_conflicts(raw_detections, policy="longest")
resolved_report = report_detections(resolved_detections)
# resolved_report.has_conflicts is False, resolved_report.total_detections == 1
```

> [!IMPORTANT]
> - **Value-Free Design**: `DetectionReport` is value-free by design: it does not retain source text, raw values, normalized values, offsets, snippets, or PII hashes.
> - **Aggregate Metadata Scope**: Entity-type labels (e.g. `IR_NATIONAL_ID`, `MRN`) and aggregate counts are still metadata. Applications must decide whether those metrics themselves require access control, retention limits, or restricted logging in their operational context.
> - **Custom Entity Type Label Notice**: Custom detector authors must keep `Detection.type` schema-level and non-sensitive. Use names such as `MRN`, `PATIENT_ID`, or `CUSTOM_ID`; never place a patient's actual name, identifier, or source value inside the type label.
> - **No Compliance Claims**: `DetectionReport` does not establish automated de-identification, anonymization, GDPR compliance, HIPAA compliance, or safe unrestricted telemetry.

#### 11. Redaction Semantics

- **Exact Span Reconstruction**: `redact()` rebuilds the output from the original Detection spans, preserving untouched source slices exactly and replacing only detected spans. It does not perform global value-based `str.replace()`.
- **Typed Placeholders**: Placeholders follow the format `[<TYPE>_<INDEX>]` (e.g., `[IR_NATIONAL_ID_1]`, `[IR_MOBILE_1]`, `[IR_IBAN_1]`, `[EMAIL_1]`, `[BANK_CARD_1]`, `[MRN_1]`).
- **Deterministic Numbering**: Identifiers receive sequential numbering based on their order of first appearance.
- **Collision Avoidance**: If an input already contains a literal string matching the placeholder syntax, newly generated placeholders increment past the colliding index.
- **Fail-Loud on Overlap by Default**: Under default `conflict_policy="reject"`, if overlapping or duplicate spans are passed to `redact()`, it raises a `ValueError`.

#### 12. Stateful Pseudonymization Sessions

`PseudonymizationSession` manages persistent mappings across multi-turn AI interactions:

- **Local Sensitive Mapping**: `session.mapping` contains `{placeholder: original_raw_value}`. Keep this mapping strictly inside your trusted boundary.
- **Cross-Call Identity**: Entities are tracked by `(type, normalized_value)`. For example, `۰۹۱۲۳۴۵۶۷۸۹` in turn 1 and `09123456789` in turn 2 both resolve to `[IR_MOBILE_1]`.
- **Domestic vs. International Limitation**: `09123456789` and `+989123456789` have different normalized strings and are not canonicalized into the same identity in v0.2.0.
- **First-Observed Representative Restoration**: Placeholders are restored using the first-observed raw representation. Restoration is semantic placeholder restoration and is not guaranteed to reconstruct the exact original surface representation of every occurrence byte-for-byte.
- **Non-Cascading Restoration**: `restore()` performs an escaped single-pass replacement, preventing recursive expansion if restored values contain placeholder syntax.
- **Atomic Updates**: If a call fails during processing, the session state, mappings, and counters remain unmodified.
- **Historical Literal Token Reservation**: Literal placeholder-like tokens observed in prior calls remain reserved so they are never assigned to real PII in later calls.
- **Unknown Placeholders**: Unmapped placeholders (e.g., `[IR_MOBILE_99]`) are left untouched without error.

#### 13. Command-Line Interface (CLI) (Unreleased)

> [!NOTE]
> **Unreleased / Development**: The command-line interface (`fa-redact` and `python -m fa_redact`) is in active development in this repository and is not included in published release v0.2.0.

`fa-redact` provides a conservative, privacy-conscious command-line interface using only the Python standard library (`argparse`). The CLI exposes detection, redaction, and aggregate reporting without modifying core library semantics.

##### 1. Command Help & Version

```bash
# View general CLI help
fa-redact --help

# View installed CLI version
fa-redact --version
```

##### 2. Stdin and File Redaction

```bash
# Redact from standard input (streaming)
echo "کد ملی بیمار ۱۲۳۴۵۶۷۸۹۱ و موبایل ۰۹۱۲۳۴۵۶۷۸۹ است." | fa-redact redact
# Output: "کد ملی بیمار [IR_NATIONAL_ID_1] و موبایل [IR_MOBILE_1] است."

# Redact from input file to stdout
fa-redact redact clinical_note.txt

# Redact from input file to an explicit output file
fa-redact redact clinical_note.txt -o sanitized_note.txt
```

##### 3. Privacy-Safe Aggregate Detection Report

Generate a value-free JSON report containing entity counts and conflict indicators:

```bash
# Generate safe aggregate report from file
fa-redact report clinical_note.txt

# Pipe report output directly to JSON tools
fa-redact report clinical_note.txt | jq .
```

##### 4. Detection Metadata (Value-Free)

Output structured detection slice metadata (`type`, `start`, `end`) as JSON:

```bash
fa-redact detect clinical_note.txt
```

> [!IMPORTANT]
> `fa-redact detect` outputs **only** structural offsets (`type`, `start`, `end`) and intentionally **never** emits detected identifier values, normalized values, source text, context snippets, or PII hashes.

##### 5. Explicit Detector Selection

Explicitly passing `--detectors` **replaces** the default detector set:

```bash
# Run only the opt-in email and bank card detectors
fa-redact redact input.txt --detectors email,bank_card

# Run no detectors (passes text through untouched)
fa-redact redact input.txt --detectors none
```

##### 6. Redaction Conflict Resolution Policies

Configure how overlapping or duplicate detections are handled during redaction:

```bash
# Default 'reject' policy (fails loud with privacy-safe error on conflicts)
fa-redact redact input.txt --conflict-policy reject

# 'longest' policy (greedily prefers longer candidate spans)
fa-redact redact input.txt --detectors email,bank_card --conflict-policy longest

# 'priority' policy (resolves conflicts by explicit entity type hierarchy)
fa-redact redact input.txt --detectors email,bank_card --conflict-policy priority --priority BANK_CARD,EMAIL
```

> [!WARNING]
> - **In-Place File Safety**: `fa-redact` rejects overwriting the source file in-place (`input` and `output` cannot point to the same file).
> - **Privacy-Safe Diagnostics**: Error messages sent to `stderr` never leak source text, detected values, or snippets.
> - **No Complete De-Identification**: Supported CLI detectors do NOT constitute complete clinical de-identification, free-text name extraction, or address removal.
> - **No Compliance Guarantees**: Using the CLI does NOT guarantee automated GDPR, HIPAA, or healthcare regulatory compliance.

---

#### 14. Structured Data Helpers (Unreleased)

`fa-redact` provides conservative, non-destructive helpers for scanning, redacting, and summarizing explicitly selected string fields inside Python mappings and JSON-like dictionaries:

- `redact_fields(record, fields, ...)`: Returns a transformed dictionary copy with detected PII replaced by typed placeholders.
- `detect_fields(record, fields, ...)`: Returns a dictionary mapping each path to its list of `Detection` instances.
- `report_fields(record, fields, ...)`: Returns a dictionary mapping each path to a privacy-safe `DetectionReport`.

##### Key Architectural Guarantees

1. **Explicit Field Targeting**: Only paths explicitly listed in `fields` are inspected or modified. `fa-redact` **never** performs blind recursive scanning of whole objects and never infers sensitive fields from schema key names. Unselected fields are never scanned, redacted, or reserved.
2. **Record-Wide Referential Consistency**: A single `redact_fields()` call maintains consistent entity mappings across all selected fields in the record. If the same entity (matching type and normalized value) appears in multiple selected fields, it receives the exact same placeholder. Placeholder allocation follows deterministic selected-field order.
3. **Cross-Field Literal Collision Avoidance**: Placeholder-like tokens (e.g. `[EMAIL_1]`) present as literal text in earlier selected fields are reserved so subsequent real entity occurrences receive safe, non-colliding placeholder numbers.
4. **Immutability & Non-Destructive Copying**: Input mappings and nested objects are never mutated in place. Transformed copies are returned as plain Python `dict` instances.
5. **Type Preservation**: All non-target values (integers, floats, booleans, `None`, lists, unaffected sub-mappings, and unselected strings) are preserved untouched.
6. **Dot-Separated Path Syntax**: Target fields are specified using simple dot-separated keys (e.g. `"note"`, `"metadata.contact"`).
7. **Fail-Loud Conservative Semantics**: Missing paths, non-mapping intermediate containers, non-string leaf values, or duplicate field paths fail loudly with clear exceptions.
8. **Error Privacy**: Exception messages never echo or leak sensitive field contents or surrounding record data.

##### Example Usage

```python
from fa_redact import EmailDetector, detect_fields, redact_fields, report_fields

record = {
    "patient_id": "کد ملی ۱۲۳۴۵۶۷۸۹۱",
    "note": "تماس با ۰۹۱۲۳۴۵۶۷۸۹ جهت هماهنگی",
    "summary": "بیمار ۰۹۱۲۳۴۵۶۷۸۹ مراجعه مجدد داشت.",
    "age": 42,
    "active": True,
    "metadata": {
        "contact_iban": "شبا IR641234567890123456789012",
        "visit_count": 3,
    },
}

# 1. Redact explicitly selected fields with record-wide referential consistency:
redacted = redact_fields(record, ["note", "summary", "metadata.contact_iban"])
print(redacted["note"])
# Output: "تماس با [IR_MOBILE_1] جهت هماهنگی"
print(redacted["summary"])
# Output: "بیمار [IR_MOBILE_1] مراجعه مجدد داشت." (same placeholder across fields)
print(redacted["metadata"]["contact_iban"])
# Output: "شبا [IR_IBAN_1]"

# Non-target fields and original record remain completely untouched:
assert record["note"] == "تماس با ۰۹۱۲۳۴۵۶۷۸۹ جهت هماهنگی"
assert redacted["age"] == 42
assert redacted["active"] is True

# 2. Detect PII in selected fields (raw evidence layer):
detections = detect_fields(record, ["patient_id", "note"])
for path, dets in detections.items():
    print(f"Path: {path} -> Found {len(dets)} detections")

# 3. Privacy-safe aggregate reporting per field:
reports = report_fields(record, ["note", "metadata.contact_iban"])
print(reports["note"].counts)
# Output: {'IR_MOBILE': 1}
```

> [!WARNING]
> - **Explicit Targeting as Safety Boundary**: Structured helpers do not automatically scan arbitrary schemas. The application caller must explicitly decide which fields are candidate text fields.
> - **Path Names as Metadata**: `report_fields()` keys summaries by caller-supplied field paths. While `DetectionReport` values are strictly value-free, path names themselves are metadata; avoid encoding sensitive identifiers into path/field names.
> - **List Indexing & Wildcards**: List element traversal (e.g. `items.0.note`) and wildcards (`*`, `**`) are not supported in this phase.
> - **No De-identification / Compliance Claims**: Using structured helpers does not guarantee HIPAA Safe Harbor or GDPR de-identification compliance.

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
> **This is not complete clinical de-identification.** `fa-redact` detects only supported direct identifiers (National IDs, mobile numbers, and IBANs by default, plus opt-in detectors). It does not detect personal names, free-text addresses, dates, or other protected health categories by default.

---

### Current Coverage & Limitations

| Identifier / Capability | v0.1.0 | v0.2.0 | Notes |
| :--- | :---: | :---: | :--- |
| **Iranian National ID (`کد ملی`)** | ✅ Supported | ✅ Default | Strict 10-digit modulo-11 checksum validation |
| **Iranian Mobile Number** | ✅ Supported | ✅ Default | Prefix-aware validation against 2026 CRA numbering plan |
| **Iranian IBAN / Sheba (`شبا`)** | ❌ Not Supported | ✅ Default | Strict 26-char MOD-97 checksum validation (`IR` + 24 digits) |
| **Email Addresses** | ❌ Not Supported | 🧪 Opt-in | Conservative ASCII email validation and detection (`detectors=[EmailDetector()]`) |
| **16-digit Bank Card (PAN)** | ❌ Not Supported | 🧪 Opt-in | 16-digit compact PAN + Luhn checksum validation (`detectors=[BankCardDetector()]`) |
| **Institutional / Healthcare IDs (MRN, Patient ID)** | ❌ Not Supported | 🧪 Opt-in | Configurable via user-defined `PatternRule` / `PatternDetector` |
| **Explicit Conflict Resolution** | ❌ Not Supported | 🧪 Opt-in Policy | Resolves overlaps/duplicates via `"longest"` or `"priority"` policy |
| **Personal Names** | ❌ Not Supported | ❌ Not Supported | Planned for future versions (requires NER/contextual models) |
| **Postal Addresses** | ❌ Not Supported | ❌ Not Supported | Unstructured spatial entities |
| **Dates of Birth / Timestamps** | ❌ Not Supported | ❌ Not Supported | Planned for future versions |
| **Health Insurance Numbers** | ❌ Not Supported | ❌ Not Supported | Institution-specific |

---

### Privacy and Security Model

> [!WARNING]
> - **Scope Limitation**: `fa-redact` detects and redacts only the specific PII types supported by its enabled detectors (National IDs, mobile numbers, and IBANs by default, plus explicitly configured opt-in detectors). It does **not** provide complete automated clinical de-identification.
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

For guidelines on contributing, see [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). For current development status and planned phases, see [PROJECT_STATUS.md](PROJECT_STATUS.md) and [ROADMAP.md](ROADMAP.md).

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

> **وضعیت: آلفا (Alpha)**  
> نسخه بسته در این درخت منبع: `v0.2.0`  
> نسخه‌های منتشرشده در [PyPI](https://pypi.org/project/fa-redact/) و [گیت‌هاب](https://github.com/mehdimt1980/fa-redact/releases) در دسترس هستند. نشان (Badge) بالای صفحه آخرین نسخهٔ منتشرشده در PyPI را نمایش می‌دهد.

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
  - [۵. اعتبارسنجی و تشخیص شماره شبا / IBAN ایران](#۵-اعتبارسنجی-و-تشخیص-شماره-شبا--iban-ایران)
  - [۶. اعتبارسنجی و تشخیص آدرس ایمیل اسکی (اختیاری)](#۶-اعتبارسنجی-و-تشخیص-آدرس-ایمیل-اسکی-اختیاری)
  - [۷. اعتبارسنجی و تشخیص شماره کارت بانکی / PAN (اختیاری)](#۷-اعتبارسنجی-و-تشخیص-شماره-کارت-بانکی--pan-اختیاری)
  - [۸. شناسه‌های سازمانی / درمانی قابل پیکربندی (اختیاری)](#۸-شناسه‌های-سازمانی--درمانی-قابل-پیکربندی-اختیاری)
  - [۹. حل صریح تعارض تشخیص‌ها (اختیاری)](#۹-حل-صریح-تعارض-تشخیص‌ها-اختیاری)
  - [۱۰. گزارش امن‌تر از نظر حریم خصوصی برای تشخیص‌ها (در حال توسعه / منتشرنشده)](#۱۰-گزارش-امنتر-از-نظر-حریم-خصوصی-برای-تشخیصها-در-حال-توسعه--منتشرنشده)
  - [۱۱. بازسازی دقیق بر اساس span در پنهان‌سازی](#۱۱-بازسازی-دقیق-بر-اساس-span-در-پنهان‌سازی)
  - [۱۲. ویژگی‌های امنیتی و رفتاری نشست نام‌مستعارسازی](#۱۲-ویژگی‌های-امنیتی-و-رفتاری-نشست-نام‌مستعارسازی)
  - [۱۳. رابط خط فرمان (CLI) (در حال توسعه / منتشرنشده)](#۱۳-رابط-خط-فرمان-cli-در-حال-توسعه--منتشرنشده)
  - [۱۴. پردازش داده‌های ساخت‌یافته (در حال توسعه / منتشرنشده)](#۱۴-پردازش-داده‌های-ساخت‌یافته-در-حال-توسعه--منتشرنشده)
- [تشخیص‌دهنده‌های سفارشی (Custom Detectors)](#تشخیص‌دهنده‌های-سفارشی-custom-detectors)
- [کاربرد در حوزهٔ سلامت و هوش مصنوعی](#کاربرد-در-حوزهٔ-سلامت-و-هوش-مصنوعی-healthcare--aillm)
- [جدول پوشش و قابلیت‌ها](#جدول-پوشش-و-قابلیت‌ها)
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
redacted_text = redact(text)
print(redacted_text)
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

#### ۵. اعتبارسنجی و تشخیص شماره شبا / IBAN ایران

> [!NOTE]
> **معرفی‌شده در نسخهٔ v0.2.0**: اعتبارسنجی و تشخیص شماره شبا (`IranianIBANDetector` و `is_valid_iranian_iban`) در نسخهٔ v0.2.0 به مجموعهٔ تشخیص‌دهنده‌های پیش‌فرض اضافه شده است.

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
redacted_text = redact(text)
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

#### ۶. اعتبارسنجی و تشخیص آدرس ایمیل اسکی (اختیاری)

> [!NOTE]
> **معرفی‌شده در نسخهٔ v0.2.0**: اعتبارسنجی و تشخیص آدرس ایمیل (`EmailDetector` و `is_valid_email`) در نسخهٔ v0.2.0 به صورت اختیاری (Opt-in) ارائه شده است.

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
redacted_text = redact(text, detectors=[EmailDetector()])
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

#### ۷. اعتبارسنجی و تشخیص شماره کارت بانکی / PAN (اختیاری)

> [!NOTE]
> **معرفی‌شده در نسخهٔ v0.2.0**: اعتبارسنجی و تشخیص شماره کارت بانکی (`BankCardDetector` و `is_valid_bank_card_number`) در نسخهٔ v0.2.0 به صورت اختیاری (Opt-in) ارائه شده است.

کتابخانهٔ `fa-redact` تابع اعتبارسنجی مستقل `is_valid_bank_card_number` و تشخیص‌دهندهٔ `BankCardDetector` را برای شماره‌های ۱۶ رقمی کارت‌های پرداخت بانکی (Primary Account Number / PAN) به صورت کاملاً آفلاین و قطعی ارائه می‌دهد:

```python
from fa_redact import (
    BankCardDetector,
    PseudonymizationSession,
    detect,
    is_valid_bank_card_number,
    redact,
)

# ۱. اعتبارسنجی مستقل (دقیقاً ۱۶ رقم، الگوریتم چکسام Luhn):
is_valid_bank_card_number("1234567890123452")  # True (کارت معتبر آزمایشی)
is_valid_bank_card_number("۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۲")  # True (پشتیبانی از ارقام فارسی)
is_valid_bank_card_number("١٢٣٤٥٦٧٨٩٠١٢٣٤٥٢")  # True (پشتیبانی از ارقام عربی)
is_valid_bank_card_number("1234 5678 9012 3452")  # False (رد فاصله)
is_valid_bank_card_number("1234-5678-9012-3452")  # False (رد خط تیره)
is_valid_bank_card_number("0000000000000000")  # False (رد رشته‌های تماماً یکسان)
is_valid_bank_card_number("1234567890123453")  # False (عدم تطابق چکسام)

# ۲. تشخیص با فعال‌سازی اختیاری (Opt-in):
text = "شماره کارت: 1234567890123452"
detections = detect(text, detectors=[BankCardDetector()])
# خروجی: [Detection(type='BANK_CARD', value='1234567890123452', ...)]

# ۳. پنهان‌سازی و نام‌مستعارسازی اختیاری:
redacted_text = redact(text, detectors=[BankCardDetector()])
# خروجی: "شماره کارت: [BANK_CARD_1]"

session = PseudonymizationSession()
pseudonymized = session.pseudonymize(
    "واریز به کارت ۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۲ انجام شد.",
    detectors=[BankCardDetector()],
)
# خروجی: "واریز به کارت [BANK_CARD_1] انجام شد."

restored = session.restore("تایید واریز به [BANK_CARD_1]")
# خروجی: "تایید واریز به ۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۲"
```

- **معماری اختیاری (Opt-in)**: کلاس `BankCardDetector` به صورت اختیاری ارائه شده و در مجموعهٔ پیش‌فرض (`_DEFAULT_DETECTORS`) قرار ندارد.
- **الگوریتم چکسام Luhn (MOD-10)**: بررسی صحت شماره‌های ۱۶ رقمی کارت با الگوریتم استاندارد Luhn (دوبرابر کردن ارقام در جایگاه‌های فرد از راست، کسر ۹ در صورت بزرگ‌تر شدن از ۹ و بررسی `sum % 10 == 0`).
- **نرم‌سازی با حفظ موقعیت کاراکتری**: پشتیبانی از ارقام لاتین (`0-9`)، فارسی (`۰-۹`) و عربی (`٠-٩`). حفظ شکل ظاهری در `Detection.value` و تبدیل به ارقام استاندارد اسکی در `Detection.normalized_value`.
- **فیلتر دفاعی رشته‌های تکراری**: رشته‌های ۱۶ رقمی تماماً تکراری (`0000000000000000` تا `9999999999999999`) حتی در صورت تطابق ریاضی چکسام، رد می‌شوند.
- **قالب فشردهٔ الکترونیکی**: صرفاً رشته‌های ۱۶ رقمی پیوسته بدون فاصله، خط تیره یا جداکننده پذیرفته می‌شوند.
- **بی‌طرفی نسبت به صادرکننده (Issuer Neutrality)**: شناسه‌ها و نام‌گذاری‌ها به صورت خنثی (`BANK_CARD`) طراحی شده‌اند. این کتابخانه پایگاه داده BIN/IIN بانکی نگهداری نمی‌کند و تعلقی به یک بانک ایرانی یا شبکهٔ خاص را تایید نمی‌کند.
- **سلب مسئولیت بانکی و امنیتی**: معتبر بودن الگوریتم Luhn به معنی واقعی بودن کارت، فعال بودن آن، تعلق آن به بانک ایرانی، مالکیت آن توسط شخص مشخص یا وجود حساب مرتبط با آن نیست. این تابع صرفاً اعتبارسنجی محلی و آفلاین ریاضی انجام می‌دهد و هیچ‌گونه اتصال به درگاه پرداخت، استعلام CVV2 یا بررسی وضعیت حساب انجام نمی‌دهد.

#### ۸. شناسه‌های سازمانی / درمانی قابل پیکربندی (اختیاری)

> [!NOTE]
> **معرفی‌شده در نسخهٔ v0.2.0**: تشخیص شناسه‌های سازمانی و درمانی قابل پیکربندی (`PatternRule` و `PatternDetector`) در نسخهٔ v0.2.0 به صورت اختیاری (Opt-in) ارائه شده است.

شماره پرونده پزشکی (MRN)، شناسه بیمار، شناسه پذیرش، شناسه مراجعه / Encounter، شناسه پرونده و سایر شناسه‌های درمانی و سازمانی کاملاً وابسته به سازمان یا بیمارستان مربوطه هستند. **برای این شناسه‌ها قالب واحد و جهانی وجود ندارد** و کتابخانهٔ `fa-redact` الگوهای حدسی یا پیش‌فرض برای آن‌ها تعریف نمی‌کند.

به جای آن، لایهٔ پیکربندی سبک، تغییرناپذیر و مستقلی (`PatternRule` و `PatternDetector`) ارائه شده است تا سازمان یا بیمارستان بتواند الگوهای منظم (Regex) اختصاصی خود را تعریف کند:

```python
import re
from fa_redact import (
    PatternDetector,
    PatternRule,
    PseudonymizationSession,
    detect,
    redact,
)

# ۱. تعریف قواعد اختصاصی بیمارستان / سازمان
hospital_detector = PatternDetector(
    [
        # شماره پرونده پزشکی (MRN)
        PatternRule(
            type="MRN",
            pattern=r"(?<!\w)MRN-[0-9]{6}(?!\w)",
        ),
        # شناسه بیمار با استفاده از گروه نام‌دار جهت حفظ برچسب 'Patient ID: '
        PatternRule(
            type="PATIENT_ID",
            pattern=r"Patient\s*ID\s*:\s*(?P<id>PAT-[A-Z]{2}-[0-9]{8})",
            group="id",
            flags=re.IGNORECASE,
        ),
        # شناسه پذیرش
        PatternRule(
            type="ADMISSION_ID",
            pattern=r"(?<!\w)ADM-20[0-9]{2}-[0-9]{6}(?!\w)",
        ),
        # شناسه مراجعه / Encounter
        PatternRule(
            type="ENCOUNTER_ID",
            pattern=r"(?<!\w)ENC-[0-9]{10}(?!\w)",
        ),
    ]
)

# ۲. تشخیص بر روی متن با پشتیبانی از ارقام فارسی در متن اصلی
text = "پرونده: MRN-۱۲۳۴۵۶ و Patient ID: PAT-TE-12345678"
detections = detect(text, detectors=[hospital_detector])
# خروجی شامل:
# - Detection(type='MRN', value='MRN-۱۲۳۴۵۶', normalized_value='MRN-123456', span=[8:18])
# - Detection(type='PATIENT_ID', value='PAT-TE-12345678', normalized_value='PAT-TE-12345678', span=[33:48])

# ۳. پنهان‌سازی (حفظ برچسب متن 'Patient ID: ' و جایگزینی فقط بخش شناسه)
redacted = redact(text, detectors=[hospital_detector])
# خروجی: "پرونده: [MRN_1] و Patient ID: [PATIENT_ID_1]"

# ۴. نام‌مستعارسازی چندمرحله‌ای با ارقام فارسی و انگلیسی
session = PseudonymizationSession()
# مرحله اول: با ارقام فارسی
turn1 = session.pseudonymize("پرونده: MRN-۱۲۳۴۵۶", detectors=[hospital_detector])
# خروجی: "پرونده: [MRN_1]"

# مرحله دوم: با ارقام لاتین (به همان [MRN_1] متصل می‌شود)
turn2 = session.pseudonymize("پیگیری پرونده MRN-123456", detectors=[hospital_detector])
# خروجی: "پیگیری پرونده [MRN_1]"

# بازگردانی به اولین شکل دیده‌شده (ارقام فارسی):
restored = session.restore("پاسخ به [MRN_1]")
# خروجی: "پاسخ به MRN-۱۲۳۴۵۶"
```

- **معماری اختیاری (Opt-in)**: کلاس `PatternDetector` کاملاً اختیاری است و در `_DEFAULT_DETECTORS` قرار ندارد. ارسال `detectors=[hospital_detector]` تشخیص‌دهنده‌های پیش‌فرض را برای آن فراخوانی جایگزین می‌کند.
- **تطابق روی متن نرمال‌شده (پیش‌فرض)**: در حالت پیش‌فرض (`source="normalized"`), الگوها با متن نرمال‌شده مطابقت داده می‌شوند؛ بنابراین یک رجکس ساده اسکی مانند `MRN-[0-9]{6}` می‌تواند ارقام فارسی (`MRN-۱۲۳۴۵۶`)، عربی (`MRN-١٢٣٤٥٦`) و لاتین (`MRN-123456`) را تشخیص دهد و فرم ظاهری را در `Detection.value` و مقدار نرمال‌شده را در `Detection.normalized_value` حفظ نماید.
- **حالت تطابق متن خام (source="original")**: در صورت نیاز به بررسی دقیق بر روی متن دست‌نخورده، حالت `source="original"` نیز پشتیبانی می‌شود.
- **پشتیبانی از گروه‌های انتخابی (Capture Groups)**: امکان استفاده از اندیس عددی (`group=1`) یا گروه نام‌دار (`group="id"`) برای جدا کردن شناسه از کلمات مجاور یا برچسب‌ها. عدم شرکت گروه در تطابق با `ValueError` مواجه خواهد شد.
- **مالکیت مرزهای رجکس (Boundary Ownership)**: کتابخانه رجکس‌های تعریف‌شده توسط کاربر را در مرزهای کلمه مانند `\b` محصور نمی‌کند؛ کنترل کامل رفتار رجکس بر عهدهٔ سازمان پیکربندی‌کننده است.
- **کامپایل یکباره و تغییرناپذیری**: کلاس `PatternRule` یک dataclass منجمد (frozen) و تغییرناپذیر است و الگوها در زمان ساخت `PatternDetector` یک‌بار کامپایل و کش می‌شوند.

> [!WARNING]
> - **الگوهای تستی و نمایشی**: الگوهای مثال ارائه‌شده (`MRN-[0-9]{6}` و ...) صرفاً مثال‌های نمایشی و ساختگی هستند و استاندارد درمانی یا قانونی محسوب نمی‌شوند.
> - **هشدار امنیتی اعتماد به رجکس**: قواعد `PatternRule` باید بخشی از پیکربندی مورد اعتماد برنامه باشند. موتور استاندارد `re` پایتون timeout داخلی برای اجرای regex ندارد. نباید regex تأییدنشده یا تولیدشده توسط کاربران ناشناس یا LLM بدون بازبینی اجرا شود.
> - **سلب مسئولیت استعلام و پرونده**: تطابق رجکس صرفاً صحت ساختار متنی را نشان می‌دهد؛ هیچ‌گونه استعلام از سامانه‌های اطلاعات بیمارستانی (HIS)، سرورهای FHIR یا پایگاه‌های داده انجام نمی‌شود و وجود خارجی بیمار یا پرونده تایید نمی‌گردد.

#### ۹. حل صریح تعارض تشخیص‌ها (اختیاری)

> [!NOTE]
> **معرفی‌شده در نسخهٔ v0.2.0**: حل صریح تعارض تشخیص‌ها (`ConflictPolicy` و `resolve_detection_conflicts`) در نسخهٔ v0.2.0 ارائه شده است.

تابع `detect()` همواره شواهد خام تشخیص‌دهنده‌ها را بازمی‌گرداند و همپوشانی‌ها و رکوردهای تکراری را دقیقاً حفظ می‌کند تا امکان ممیزی و بازبینی شفاف وجود داشته باشد.

به‌صورت پیش‌فرض، توابع `redact()` و `session.pseudonymize()` با سیاست محافظه‌کارانهٔ `conflict_policy="reject"` اجرا می‌شوند و در صورت وجود هرگونه تداخل، همپوشانی یا تکرار، با خطای `ValueError` متوقف می‌شوند:

```python
from fa_redact import BankCardDetector, EmailDetector, redact

text = "ایمیل: 1234567890123452@example.com"
detectors = [EmailDetector(), BankCardDetector()]

# سیاست پیش‌فرض reject: به دلیل تداخل spanهای EMAIL و BANK_CARD خطا می‌دهد
# redact(text, detectors=detectors)  # -> ValueError
```

در صورت نیاز، سازمان یا برنامه می‌تواند با انتخاب یکی از سیاست‌های صریح، نحوهٔ حل تعارض را مشخص کند:

- **سیاست طولانی‌ترین بازه (`conflict_policy="longest"`)**: به‌صورت حریصانه طولانی‌ترین span را انتخاب کرده و تشخیص‌های کوتاه‌تر همپوشان را حذف می‌کند. موارد کاملاً تکراری در یکدیگر ادغام می‌شوند. در صورت وجود همپوشانی مبهم با طول مساوی، `ValueError` صادر می‌شود.
- **سیاست اولویت نوع موجودیت (`conflict_policy="priority"`)**: اولویت‌بندی بر اساس فهرست مشخص‌شده در `type_priority=[...]` انجام می‌شود و موجودیت با اولویت بالاتر برنده خواهد بود (حتی اگر طول span آن کوتاه‌تر باشد). تمامی انواع موجودیت‌های درگیر در تعارض باید در `type_priority` ذکر شده باشند.

```python
# انتخاب EMAIL به دلیل طول بیشتر
redacted_longest = redact(text, detectors=detectors, conflict_policy="longest")
# خروجی: "ایمیل: [EMAIL_1]"

# اولویت‌دهی به کارت بانکی بر روی ایمیل
redacted_priority = redact(
    text,
    detectors=detectors,
    conflict_policy="priority",
    type_priority=["BANK_CARD", "EMAIL"],
)
# خروجی: "ایمیل: [BANK_CARD_1]@example.com"
```

> [!WARNING]
> - **عدم قطعیت ماهیت شناسه**: حل تعارض صرفاً یک قاعدهٔ پالایش اکتشافی است و به معنی تشخیص قطعی ماهیت واقعی شناسه نیست.
> - **خطر باقی‌ماندن بخشی از شناسه در متن**: انتخاب `longest` یا `priority` ممکن است یک تشخیص همپوشان دیگر را حذف کند و بخشی از span آن تشخیص (مانند پسوند ایمیل) در متن باقی بماند.
> - **توصیهٔ امنیتی**: در صورت هرگونه تردید، استفاده از سیاست پیش‌فرض `reject` توصیه می‌شود.

#### ۱۰. گزارش امن‌تر از نظر حریم خصوصی برای تشخیص‌ها (در حال توسعه / منتشرنشده)

> [!NOTE]
> **در حال توسعه / منتشرنشده**: قابلیت گزارش‌گیری امن‌تر از نظر حریم خصوصی (`DetectionReport`، `detection_report` و `report_detections`) در این مخزن در حال توسعه است و در نسخهٔ منتشرشدهٔ v0.2.0 در PyPI وجود ندارد.

کتابخانهٔ `fa-redact` یک لایهٔ گزارش‌گیری تجمیعی و مستقل ارائه می‌دهد که شواهد خروجی تشخیص‌دهنده‌ها را بدون ذخیره‌سازی، نگهداری یا بازگرداندن مقادیر خام PII، مقادیر نرمال‌شده، متن منبع، بازه‌های کاراکتری (spans)، بخش‌های متنی مجاور (snippets) یا هش‌های PII خلاصه می‌کند.

##### ۱. گزارش تجمیعی پایه

تولید گزارش تجمیعی مستقیم از روی متن با استفاده از تشخیص‌دهنده‌های پیش‌فرض یا سفارشی:

```python
from fa_redact import detection_report

text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱، همراه: ۰۹۱۲۳۴۵۶۷۸۹"
report = detection_report(text)

print(report.total_detections)  # 2
print(dict(report.counts))  # {'IR_MOBILE': 1, 'IR_NATIONAL_ID': 1}
print(report.distinct_types)  # 2
print(report.has_conflicts)  # False
print(report.conflict_pairs)  # 0
print(report.conflicting_detections)  # 0
print(report.duplicate_groups)  # 0
```

##### ۲. مشاهده‌پذیری شواهد خام و تعارض تشخیص‌ها

تابع `detection_report()` شواهد خام تشخیص‌دهنده‌ها را بدون حل خودکار تعارض اجرا می‌کند. این امر به برنامه‌ها امکان می‌دهد وجود هرگونه تداخل یا تعارض بین تشخیص‌دهنده‌ها را شناسایی و ارزیابی نمایند:

```python
from fa_redact import (
    BankCardDetector,
    EmailDetector,
    detection_report,
)

text = "ایمیل: 1234567890123452@example.com"
report = detection_report(
    text,
    detectors=[
        EmailDetector(),
        BankCardDetector(),
    ],
)

print(report.total_detections)  # 2
print(dict(report.counts))  # {'BANK_CARD': 1, 'EMAIL': 1}
print(report.has_conflicts)  # True
print(report.conflict_pairs)  # 1
print(report.conflicting_detections)  # 2
```

##### ۳. گزارش‌گیری پیش و پس از حل صریح تعارض

کاربران می‌توانند با استفاده از `report_detections()`، دنبالهٔ اشیاء `Detection` را قبل و بعد از حل تعارض ممیزی و مقایسه نمایند:

```python
from fa_redact import (
    detect,
    report_detections,
    resolve_detection_conflicts,
)

# ۱. گزارش شواهد خام تشخیص‌دهنده‌ها
raw_detections = detect(text, detectors=detectors)
raw_report = report_detections(raw_detections)
# raw_report.has_conflicts برابر با True و raw_report.total_detections برابر با 2 است

# ۲. گزارش شواهد پس از حل صریح تعارض
resolved_detections = resolve_detection_conflicts(raw_detections, policy="longest")
resolved_report = report_detections(resolved_detections)
# resolved_report.has_conflicts برابر با False و resolved_report.total_detections برابر با 1 است
```

> [!IMPORTANT]
> - **طراحی بدون مقدار (Value-Free)**: ساختار `DetectionReport` به گونه‌ای طراحی شده که هیچ مقدار خام، مقدار نرمال‌شده، موقعیت کاراکتری، برش متنی یا هش PII را در خود نگه نمی‌دارد.
> - **محدودهٔ فراداده (Metadata)**: نبودن مقدار خام شناسه در گزارش به این معنی نیست که خود گزارش در همهٔ محیط‌ها دادهٔ غیرحساس محسوب می‌شود. وجود نوع شناسه (مانند `MRN` یا `IR_NATIONAL_ID`) و تعداد آن‌ها نیز ممکن است در برخی محیط‌های سازمانی فرادادهٔ حساس تلقی شود و نیازمند کنترل دسترسی و محدودیت ثبت لاگ باشد.
> - **هشدار برچسب نوع موجودیت**: توسعه‌دهندگان تشخیص‌دهنده‌های سفارشی باید فیلد `Detection.type` را صرفاً به عنوان یک نام دسته یا schema (مانند `MRN` یا `PATIENT_ID`) تعریف کنند و هرگز نام بیمار، شناسه یا مقادیر متنی را درون `Detection.type` قرار ندهند.
> - **عدم ادعای انطباق قانونی**: ساختار `DetectionReport` به خودی خود ناشناس‌سازی کامل بالینی، انطباق با GDPR یا HIPAA یا مجوز ارسال نامحدود تله‌متری را ایجاد نمی‌کند.

#### ۱۱. بازسازی دقیق بر اساس span در پنهان‌سازی

خروجی بر اساس بازه‌های دقیق `Detection` از متن اصلی ساخته می‌شود؛ فقط همان spanهای تشخیص‌داده‌شده جایگزین می‌شوند و بخش‌های دیگر متن بدون تغییر کپی می‌شوند. پیاده‌سازی از `str.replace()` سراسری بر اساس مقدار استفاده نمی‌کند.

#### ۱۲. ویژگی‌های امنیتی و رفتاری نشست نام‌مستعارسازی

کلاس `PseudonymizationSession` رفتارهای امنیتی زیر را تضمین می‌کند:

- **ایزوله‌سازی نشست‌ها (Mapping Isolation)**: هر نشست دارای حافظه و نگاشت مستقل است.
- **یکپارچگی هویت در چند مرحله (Cross-Call Identity)**: هویت یک موجودیت بر اساس `(type, normalized_value)` ردیابی می‌شود. بنابراین `۰۹۱۲۳۴۵۶۷۸۹` در نوبت اول و `09123456789` در نوبت دوم هر دو به `[IR_MOBILE_1]` متصل می‌شوند.
- **محدودیت تفاوت فرمت داخلی و بین‌المللی**: مقادیر `09123456789` و `+989123456789` دارای رشته‌های نرمال‌شدهٔ متفاوتی هستند و در نسخهٔ v0.2.0 به یک هویت یکسان تبدیل نمی‌شوند.
- **بازگردانی به اولین نمایش دیده‌شده (First-Observed Representative)**: تابع `restore()` یک بازگردانی معنایی بر اساس placeholder انجام می‌دهد و تضمین نمی‌کند که شکل نویسه‌ای دقیق تک‌تک occurrenceهای متن اولیه به‌صورت byte-for-byte بازسازی شود.
- **بازگردانی غیرآبشاری (Non-Cascading Restore)**: بازگردانی در یک مرحله و با فرار کاراکترهای خاص انجام می‌شود تا اگر مقدار بازگردانده‌شده شبیه به نشان‌گذار باشد، بازگردانی بازگشتی و ناخواسته رخ ندهد.
- **به‌روزرسانی اتمیک (Atomic Updates)**: اگر در حین پردازش خطایی رخ دهد، وضعیت نشست و شمارنده‌ها دست‌نخورده باقی می‌مانند.
- **محافظت در برابر تداخل تاریخی با نشان‌گذارهای متنی**: اگر در متون قبلی عبارتی مانند `[IR_MOBILE_2]` به عنوان متن عادی وجود داشته باشد، سیستم آن شماره را رزرو کرده و برای شناسه‌های واقعی جدید اختصاص نمی‌دهد.
- **عدم دستکاری نشان‌گذارهای ناشناخته**: نشان‌گذارهایی که در نگاشت نشست ثبت نشده‌اند (مانند `[IR_MOBILE_99]`) بدون خطا و دست‌نخورده باقی می‌مانند.

#### ۱۳. رابط خط فرمان (CLI) (در حال توسعه / منتشرنشده)

> [!NOTE]
> **در حال توسعه / منتشرنشده**: رابط خط فرمان (`fa-redact` و `python -m fa_redact`) در حال حاضر در مخزن در حال توسعه است و در نسخهٔ منتشرشدهٔ v0.2.0 موجود نیست.

کتابخانهٔ `fa-redact` یک رابط خط فرمان سبک، مستقل و مبتنی بر حریم خصوصی ارائه می‌دهد که بدون وابستگی خارجی (با استفاده از کتابخانهٔ استاندارد `argparse`)، امکان تشخیص، پنهان‌سازی و گزارش‌گیری را فراهم می‌سازد.

##### ۱. راهنما و مشاهدهٔ نسخه

```bash
# مشاهده راهنمای کلی CLI
fa-redact --help

# مشاهده نسخه نصب‌شده
fa-redact --version
```

##### ۲. پنهان‌سازی از طریق Stdin و فایل

```bash
# پنهان‌سازی از طریق ورودی استاندارد (جریان / Streaming)
echo "کد ملی بیمار ۱۲۳۴۵۶۷۸۹۱ و موبایل ۰۹۱۲۳۴۵۶۷۸۹ است." | fa-redact redact
# خروجی: "کد ملی بیمار [IR_NATIONAL_ID_1] و موبایل [IR_MOBILE_1] است."

# پنهان‌سازی فایل متنی و چاپ در خروجی استاندارد
fa-redact redact input.txt

# پنهان‌سازی فایل متنی و ذخیره در فایل مقصد
fa-redact redact input.txt -o redacted.txt
```

##### ۳. گزارش آماری امن از نظر حریم خصوصی

تولید گزارش آماری با ساختار JSON بدون ذخیره یا افشای مقادیر حساس:

```bash
# تولید گزارش آماری از فایل
fa-redact report input.txt
```

##### ۴. فراداده‌های تشخیص (بدون مقدار)

خروجی متادیتا و بازه‌های تشخیص (`type`, `start`, `end`) در قالب JSON:

```bash
fa-redact detect input.txt
```

> [!IMPORTANT]
> دستور `fa-redact detect` ساختار بازه‌ای (`type`, `start`, `end`) را نمایش می‌دهد و عمداً **هیچ مقدار خام، مقدار نرمال‌شده، برش متنی یا هش PII** را در خروجی بازنمی‌گرداند.

##### ۵. انتخاب صریح تشخیص‌دهنده‌ها

استفاده از گزینهٔ `--detectors` مجموعهٔ پیش‌فرض را **جایگزین** می‌کند:

```bash
# اجرای فقط تشخیص‌دهنده‌های ایمیل و کارت بانکی
fa-redact redact input.txt --detectors email,bank_card

# اجرای بدون هیچ تشخیص‌دهنده (عدم تغییر متن)
fa-redact redact input.txt --detectors none
```

##### ۶. سیاست‌های حل تعارض در پنهان‌سازی

```bash
# سیاست پیش‌فرض رد تعارض (خطای صریح و امن در صورت هم‌پوشانی)
fa-redact redact input.txt --conflict-policy reject

# سیاست طولانی‌ترین span
fa-redact redact input.txt --detectors email,bank_card --conflict-policy longest

# سیاست اولویت صریح انواع موجودیت
fa-redact redact input.txt --detectors email,bank_card --conflict-policy priority --priority BANK_CARD,EMAIL
```

> [!WARNING]
> - **امنیت عدم بازنویسی فایل درجا**: ابزار `fa-redact` بازنویسی مستقیم روی همان فایل ورودی را رد می‌کند تا از آسیب دیدن فایل منبع جلوگیری شود.
> - **پیام‌های خطای بدون نشت PII**: خطاهای صادرشده به `stderr` هرگز حاوی مقادیر حساس، متن اولیه یا برش‌های محرمانه نیستند.
> - **عدم ادعای ناشناس‌سازی بالینی کامل**: شناسه‌های پشتیبانی‌شده شامل نام اشخاص، آدرس‌های آزاد یا سوابق متنی کامل سلامت نمی‌شوند.
> - **عدم تضمین خودکار انطباق قانونی**: استفاده از CLI به خودی خود انطباق با GDPR یا HIPAA را ایجاد نمی‌کند.

---

#### ۱۴. پردازش داده‌های ساخت‌یافته (در حال توسعه / منتشرنشده)

کتابخانهٔ `fa-redact` توابع کمکی محافظه‌کارانه و غیرمخربی را برای تشخیص، پنهان‌سازی و گزارش‌گیری از فیلدهای متنی صریح در ساختارهای داده‌ای پایتون (دیکشنری‌ها و رکوردهای شبیه JSON) ارائه می‌دهد:

- `redact_fields(record, fields, ...)`: بازگرداندن نسخه‌ای کپی‌شده از داده با جایگزینی شناسه‌های حساس در فیلدهای صریح با جانگهدارها (بدون تغییر شیء ورودی).
- `detect_fields(record, fields, ...)`: بازگرداندن نگاشتی از مسیر هر فیلد به فهرستی از اشیاء `Detection`.
- `report_fields(record, fields, ...)`: بازگرداندن نگاشتی از مسیر هر فیلد به گزارش آماری امن `DetectionReport`.

##### اصول و تضمین‌های طراحی

۱. **هدف‌گیری صریح فیلدها (Explicit Field Targeting)**: تنها مسیرهایی که به صورت صریح در پارامتر `fields` مشخص شده‌اند پردازش می‌شوند. کتابخانه هرگز جستجوی بازگشتی کورکورانه روی کل شیء انجام نمی‌دهد و نام کلیدها را برای حدس زدن حساسیت فیلد تحلیل نمی‌کند. فیلدهای انتخاب‌نشده هرگز اسکن یا پنهان‌سازی نمی‌شوند.
۲. **یکپارچگی و ثبات انتساب در سطح کل رکورد (Referential Consistency)**: در یک فراخوانی `redact_fields()`، هویت نهادهای یکسان (با نوع و مقدار نرمال‌شده یکسان) در تمام فیلدهای صریح انتخاب‌شده ثابت می‌ماند و جانگهدار کاملاً یکسانی دریافت می‌کنند. ترتیب تخصیص شماره جانگهدارها مطابق ترتیب فیلدها در `fields` است.
۳. **رزرو توکن‌های جانگهدار در بین فیلدها**: توکن‌های شبیه جانگهدار (مانند `[EMAIL_1]`) که به عنوان متن از قبل در فیلدهای قبلی وجود دارند رزرو می‌شوند تا شناسه‌های واقعی در فیلدهای بعدی دچار تصادم شماره نشوند.
۴. **تغییرناپذیری و کپی غیرمخرب (Immutability)**: نگاشت‌ها و دیکشنری‌های ورودی کاربر هرگز درجا (in-place) دستکاری نمی‌شوند و ساختار خروجی به شکل یک `dict` استاندارد جدید بازگردانده می‌شود.
۵. **حفظ انواع داده‌های غیرهدف**: تمام داده‌های دست‌نخورده (اعداد صحیح، اعشاری، مقادیر بولی، `None`، لیست‌ها و رشته‌های انتخاب‌نشده) بدون تغییر باقی می‌مانند.
۶. **سینتکس مسیر نقطه‌ای (Dot-Separated Path)**: مسیردهی فیلدها با استفاده از نقطه‌گذاری استاندارد (مانند `"note"` یا `"metadata.contact"`) انجام می‌شود.
۷. **رفتار صریح در صورت خطا (Fail-Loud)**: در صورت وجود مسیرهای نامعتبر، کلیدهای مفقود، کانتینرهای میانی غیرنگاشتی، یا فیلدهای هدف غیررشته‌ای، بلافاصله خطای صریح صادر می‌شود.
۸. **حفظ حریم خصوصی در پیام‌های خطا**: متن و مقادیر حساس فیلدها هرگز در پیام‌های خطا منعکس نمی‌شوند.

##### نمونه کد

```python
from fa_redact import detect_fields, redact_fields, report_fields

record = {
    "patient_id": "کد ملی ۱۲۳۴۵۶۷۸۹۱",
    "note": "تماس با ۰۹۱۲۳۴۵۶۷۸۹ جهت هماهنگی",
    "summary": "بیمار ۰۹۱۲۳۴۵۶۷۸۹ مراجعه مجدد داشت.",
    "age": 42,
    "active": True,
    "metadata": {
        "contact_iban": "شبا IR641234567890123456789012",
        "visit_count": 3,
    },
}

# ۱. پنهان‌سازی فیلدهای مشخص‌شده با حفظ یکپارچگی ارجاعی در کل رکورد:
redacted = redact_fields(record, ["note", "summary", "metadata.contact_iban"])
print(redacted["note"])
# خروجی: "تماس با [IR_MOBILE_1] جهت هماهنگی"
print(redacted["summary"])
# خروجی: "بیمار [IR_MOBILE_1] مراجعه مجدد داشت." (جانگهدار یکسان در چند فیلد)
print(redacted["metadata"]["contact_iban"])
# خروجی: "شبا [IR_IBAN_1]"

# فیلدهای دیگر و شیء اولیه کاملاً دست‌نخورده باقی می‌مانند:
assert record["note"] == "تماس با ۰۹۱۲۳۴۵۶۷۸۹ جهت هماهنگی"
assert redacted["age"] == 42
assert redacted["active"] is True

# ۲. تشخیص شناسه‌ها در فیلدهای مشخص‌شده:
detections = detect_fields(record, ["patient_id", "note"])
for path, dets in detections.items():
    print(f"مسیر: {path} -> تعداد تشخیص: {len(dets)}")

# ۳. گزارش آماری امن به تفکیک هر فیلد:
reports = report_fields(record, ["note", "metadata.contact_iban"])
print(reports["note"].counts)
# خروجی: {'IR_MOBILE': 1}
```

> [!WARNING]
> - **هدف‌گیری صریح به عنوان مرز امنیتی**: توابع ساخت‌یافته فیلدهای ناشناس را به صورت خودکار اسکن نمی‌کنند؛ برنامهٔ فراخواننده باید صریحاً فیلدهای متنی مورد نظر را تعیین نماید.
> - **نام مسیرها به عنوان فراداده (Metadata)**: خروجی `report_fields()` بر اساس نام مسیر فیلدها کلیدگذاری می‌شود؛ اگرچه مقادیر `DetectionReport` کاملاً بدون مقدار حساس هستند، اما خود نام مسیرها فراداده محسوب می‌شوند و نباید شناسه یا دادهٔ محرمانه در نام فیلدها درج شود.
> - **اندیس لیست‌ها و وایلدکاردها**: پیمایش اندیس‌های لیست (مانند `items.0.note`) و الگوهای `*` در این فاز پشتیبانی نمی‌شوند.
> - **عدم تضمین انطباق یا حذف کامل اطلاعات هویتی**: استفاده از این توابع به منزلهٔ حذف قطعی و خودکار همهٔ داده‌های حساس یا انطباق قانونی با استانداردهایی چون HIPAA نیست.

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
> **این فرایند به معنی ناشناس‌سازی یا de-identification کامل متن بالینی نیست.** `fa-redact` به صورت پیش‌فرض صرفاً کد ملی، شماره موبایل و شماره شبا (به همراه تشخیص‌دهنده‌های فعال‌شدهٔ اختیاری) را پوشش می‌دهد و داده‌هایی نظیر نام اشخاص، آدرس‌ها، تاریخ‌ها یا سایر رده‌های سلامت حفاظت‌شده را به‌طور پیش‌فرض تشخیص نمی‌دهد.

---

### جدول پوشش و قابلیت‌ها

| نوع شناسه هویتی / قابلیت | v0.1.0 | v0.2.0 | توضیحات |
| :--- | :---: | :---: | :--- |
| **کد ملی ایران** | ✅ پشتیبانی می‌شود | ✅ پیش‌فرض | اعتبارسنجی دقیق ۱۰ رقمی با قاعدهٔ چکسام Modulo-11 |
| **شماره تلفن همراه ایران** | ✅ پشتیبانی می‌شود | ✅ پیش‌فرض | اعتبارسنجی پیش‌شماره‌های مصوب رگولاتوری ایران (CRA 2026) |
| **شماره شبا (IBAN)** | ❌ پشتیبانی نمی‌شود | ✅ پیش‌فرض | اعتبارسنجی دقیق ۲۶ کاراکتری با قاعدهٔ چکسام MOD-97 (`IR` + ۲۴ رقم) |
| **آدرس ایمیل** | ❌ پشتیبانی نمی‌شود | 🧪 اختیاری | اعتبارسنجی و تشخیص ایمیل‌های اسکی محافظه‌کارانه (`detectors=[EmailDetector()]`) |
| **شماره کارت بانکی (PAN)** | ❌ پشتیبانی نمی‌شود | 🧪 اختیاری | فرمت فشردهٔ ۱۶ رقمی + Luhn؛ بدون استعلام BIN/IIN یا صادرکننده (`detectors=[BankCardDetector()]`) |
| **شناسه‌های سازمانی / درمانی (MRN و بیمار)** | ❌ پشتیبانی نمی‌شود | 🧪 اختیاری | قابل پیکربندی اختصاصی توسط کاربر با `PatternRule` و `PatternDetector` |
| **حل صریح تعارض تشخیص‌ها** | ❌ پشتیبانی نمی‌شود | 🧪 سیاست اختیاری | حل همپوشانی‌ها و تکرارها با سیاست `"longest"` یا `"priority"` |
| **نام اشخاص** | ❌ پشتیبانی نمی‌شود | ❌ پشتیبانی نمی‌شود | نیازمند مدل‌های پردازش زبان طبیعی و بازشناسی موجودیت‌های نام‌دار (NER) |
| **آدرس پستی و موقعیت مکانی** | ❌ پشتیبانی نمی‌شود | ❌ پشتیبانی نمی‌شود | موجودیت‌های غیرساختاریافته |
| **تاریخ تولد و زمان‌ها** | ❌ پشتیبانی نمی‌شود | ❌ پشتیبانی نمی‌شود | برنامه‌ریزی‌شده برای نسخه‌های آتی |
| **شماره بیمه درمانی** | ❌ پشتیبانی نمی‌شود | ❌ پشتیبانی نمی‌شود | فرمت سازمانی |

---

### مدل حریم خصوصی و سلب مسئولیت‌های امنیتی

> [!WARNING]
> - **محدودیت دامنهٔ پوشش**: این بسته به صورت پیش‌فرض صرفاً کد ملی، شماره موبایل و شماره شبای ایران (به همراه تشخیص‌دهنده‌های فعال‌شدهٔ اختیاری) را پوشش می‌دهد و به هیچ وجه سیستم دی‌ایدنتیفیکیشن (De-identification) کامل پرونده‌های پزشکی بالینی نیست.
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

برای آگاهی از نحوهٔ مشارکت در پروژه، راهنماهای [CONTRIBUTING.md](CONTRIBUTING.md) و [SECURITY.md](SECURITY.md) را مطالعه فرمایید. برای مشاهدهٔ وضعیت جاری توسعه و فازهای برنامه‌ریزی‌شده، فایل‌های [PROJECT_STATUS.md](PROJECT_STATUS.md) و [ROADMAP.md](ROADMAP.md) را بررسی کنید.

---

### مجوز (License)

این پروژه تحت [مجوز MIT](LICENSE) منتشر شده است.
