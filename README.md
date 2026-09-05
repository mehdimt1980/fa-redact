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
  - [5. Redaction Semantics](#5-redaction-semantics)
  - [6. Stateful Pseudonymization Sessions](#6-stateful-pseudonymization-sessions)
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
2. **Strict Algorithmic Validation**: Implements checksum and prefix validation for Iranian identifiers (National IDs and mobile numbers) rather than relying on loose regular expressions.
3. **Safe Placeholder Redaction**: Deterministically substitutes detected spans with typed placeholders.
4. **Stateful Pseudonymization & Local Restoration**: Generates stable aliases across conversational turns and restores original values locally inside your trusted boundary.

---

### Why fa-redact?

- **Handling Persian Text Peculiarities**: Persian text frequently mixes Persian digits (`۰-۹`), Arabic-Indic digits (`٠-٩`), and ASCII digits (`0-9`), alongside letter variants like Arabic Yeh (`ي`) and Kaf (`ك`). Simple regex patterns fail on mixed-script variations, while naive string replacements drift character offsets.
- **Offset Integrity**: `fa-redact` ensures `len(normalized) == len(original)`, guaranteeing that slice offsets `text[start:end]` map directly back to the original source text.
- **Privacy-First AI Integrations**: Mask patient or customer identifiers before sending prompts to external LLMs, then restore LLM outputs locally without ever exposing raw PII outside your trusted perimeter.
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
    print(f"Type: {d.type} | Value: {d.value} | Normalized: {d.normalized_value} | Span: [{d.start}:{d.end}]")
    assert text[d.start:d.end] == d.value
```

#### 2. Redact PII (Stateless)

Sanitize sensitive text into deterministic, typed placeholders. Repeated identifiers within the same call receive the same placeholder:

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
safe_prompt = session.pseudonymize(prompt)
print(safe_prompt)
# Output: "کد ملی بیمار [IR_NATIONAL_ID_1] و شماره تماس [IR_MOBILE_1] است."

# 2. Send ONLY safe_prompt to external LLM. Simulated LLM response:
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

- `type`: Identifier category (e.g. `IR_NATIONAL_ID`, `IR_MOBILE`).
- `value`: Exact substring as written in the original input text.
- `normalized_value`: Canonical normalized form of the span.
- `start` / `end`: Zero-indexed Python string slice boundaries (`text[start:end] == value`).

The pipeline validates detector outputs, verifies that detections do not overlap, and fails loudly with `ValueError` if overlapping spans are encountered.

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

- **Modulo-11 Checksum**: Applies the official modulo-11 checksum formula.
- **Repeated-Digit Rejection**: Rejects pseudo-values like `0000000000` or `1111111111`.
- **Exact Length**: Requires exactly 10 digits; does not strip spaces or auto-pad.
- **Verification Notice**: Validation confirms mathematical structure only. It does not query government registries or confirm whether an ID has been officially issued.

#### 4. Iranian Mobile Number Validation & Detection

Validates and detects Iranian mobile numbers using the official Communications Regulatory Authority (CRA) numbering-plan snapshot:

```python
from fa_redact import IranianMobileNumberDetector, is_valid_mobile_number

# Supported domestic and international formats
is_valid_mobile_number("09123456789")     # True (domestic)
is_valid_mobile_number("۰۹۱۲۳۴۵۶۷۸۹")     # True (Persian digits)
is_valid_mobile_number("+989123456789")   # True (+98 format)
is_valid_mobile_number("00989351234567")  # True (0098 format)
is_valid_mobile_number("09412345678")     # False (fixed non-geographical)
```

- **Prefix-Aware Allocation**: Validates National Destination Codes (NDC) allocated to mobile operators (MCI, MTN Irancell, RighTel, Shatel Mobile, etc.).
- **Exclusion of Non-Mobile Prefixes**: Non-mobile prefixes such as `094` (fixed non-geographic) and `09950` (Public Trunk) are rejected.
- **Verification Notice**: Prefix validation confirms structural numbering-plan compliance only; it does not verify active SIM status, subscriber identity, or carrier ownership.

#### 5. Redaction Semantics

- **Exact Span Substitution**: Slices are replaced from right to left to avoid offset recalculation errors.
- **Typed Placeholders**: Placeholders follow the format `[<TYPE>_<INDEX>]` (e.g. `[IR_NATIONAL_ID_1]`, `[IR_MOBILE_1]`).
- **Deterministic Numbering**: Identifiers receive sequential numbering based on their order of first appearance.
- **Collision Avoidance**: If an input already contains a literal string matching the placeholder syntax, newly generated placeholders increment past the colliding index.

#### 6. Stateful Pseudonymization Sessions

`PseudonymizationSession` manages persistent mappings across multi-turn AI interactions:

- **Local Sensitive Mapping**: `session.mapping` contains `{placeholder: original_raw_value}`. Keep this mapping strictly inside your trusted boundary.
- **Cross-Call Identity**: Entities are tracked by `(type, normalized_value)`. For example, `۰۹۱۲۳۴۵۶۷۸۹` in turn 1 and `09123456789` in turn 2 both resolve to `[IR_MOBILE_1]`.
- **First-Observed Representative Restoration**: Placeholders are restored using the first-observed raw representation.
- **Non-Cascading Restoration**: `restore()` performs an escaped single-pass replacement, preventing recursive expansion if restored values contain placeholder syntax.
- **Atomic Updates**: If a call fails during processing, the session state, mappings, and counters remain unmodified.
- **Historical Literal Token Reservation**: Literal placeholder-like tokens observed in prior calls remain reserved so they are never assigned to real PII in later calls.
- **Unknown Placeholders**: Unmapped placeholders (e.g. `[IR_MOBILE_99]`) are left untouched without error.

---

### Custom Detectors

`fa-redact` uses Python's structural typing (protocols). Any class implementing a `detect(self, text: str) -> Sequence[Detection]` method can be passed to `detect()`, `redact()`, or `session.pseudonymize()`:

```python
import re
from typing import Sequence
from fa_redact import Detection, detect

class MedicalRecordNumberDetector:
    """Example custom detector for institutional Medical Record Numbers (MRN)."""
    
    def detect(self, text: str) -> Sequence[Detection]:
        detections = []
        for match in re.finditer(r"\bMRN-\d{6}\b", text):
            detections.append(
                Detection(
                    type="MRN",
                    start=match.start(),
                    end=match.end(),
                    value=match.group(0),
                    normalized_value=match.group(0),
                )
            )
        return detections

# Use standard detectors along with custom detectors:
text = "پرونده بیمار با MRN-123456 و شماره ۰۹۱۲۳۴۵۶۷۸۹ بررسی شد."
detections = detect(text, detectors=[MedicalRecordNumberDetector()])
```

---

### Healthcare & AI/LLM Usage Pattern

```text
Local Hospital / Trusted Boundary
  │
  ├── 1. Raw clinical text with sensitive PII
  │      ↓
  ├── 2. session.pseudonymize(raw_text)
  │      ↓
  ├── 3. [IR_NATIONAL_ID_1], [IR_MOBILE_1] (Safe Prompt)
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

---

### Current Coverage & Limitations

| Identifier Type | Status in v0.1.0 | Notes |
| :--- | :---: | :--- |
| **Iranian National ID (`کد ملی`)** | ✅ Supported | Strict 10-digit modulo-11 checksum validation |
| **Iranian Mobile Number** | ✅ Supported | Prefix-aware validation against 2026 CRA numbering plan |
| **Personal Names** | ❌ Not Supported | Planned for future versions (requires NER/contextual models) |
| **Postal Addresses** | ❌ Not Supported | Unstructured spatial entities |
| **Email Addresses** | ❌ Not Supported | Planned for future release |
| **Medical Record Numbers (MRN)** | ❌ Not Supported | Institution-specific (use custom detectors) |
| **Health Insurance Numbers** | ❌ Not Supported | Institution-specific |
| **Bank Card Numbers (PAN)** | ❌ Not Supported | Planned for future release |
| **IBAN / Sheba (`شبا`)** | ❌ Not Supported | Planned for future release |
| **Dates of Birth** | ❌ Not Supported | Planned for future release |

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
  - [۵. ویژگی‌های امنیتی و رفتاری نشست نام‌مستعارسازی](#۵-ویژگی‌های-امنیتی-و-رفتاری-نشست-نام‌مستعارسازی)
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

کتابخانهٔ `fa-redact` با ارائهٔ ابزارهای سبک و کارآمد، متن را پیش از خروج از محیط امن شما پردازش کرده و شناسه‌های حساس را با نشان‌گذارهای جایگزین (Placeholders) امن تعویض می‌کند. پس از دریافت پاسخ از هوش مصنوعی، می‌توان نشان‌گذارها را در محیط محلی و امن خود به مقادیر اصلی بازگرداند (Restoration).

---

### چرا fa-redact؟ (Motivation)

پردازش متون فارسی در زمینهٔ امنیت داده و پالایش متون، چالش‌های منحصربه‌فردی دارد:

1. **تنوع ارقام و حروف**: در متون فارسی، شماره‌ها ممکن است با ارقام فارسی (`۰-۹`)، ارقام عربی (`٠-٩`) یا ارقام لاتین (`0-9`) نوشته شده باشند. همچنین تفاوت حروف مانند «ي» و «ك» عربی با «ی» و «ک» فارسی مانع عملکرد صحیح الگوهای ساده می‌شود.
2. **حفظ موقعیت کاراکترها (Offsets)**: روش‌های مرسوم نرم‌سازی متن اغلب طول رشته را تغییر می‌دهند (مثلاً با حذف فاصله‌ها یا اعراب)؛ این کار باعث جابه‌جایی ایندکس‌های کاراکتری شده و جایگزینی دقیق در متن اصلی را غیرممکن می‌سازد. `fa-redact` تضمین می‌کند که طول رشته قبل و بعد از نرم‌سازی یکسان باشد (`len(normalized) == len(original)`).
3. **اعتبارسنجی دقیق الگوریتمی**: به‌جای استفاده از رجکس‌های حدسی و شکننده، شناسه‌های ملی و شماره‌های موبایل با الگوریتم‌های رسمی کنترلی (مانند چکسام Modulo-11 و پیش‌شماره‌های رگولاتوری ایران) بررسی می‌شوند.
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
    assert text[item.start:item.end] == item.value
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
safe_prompt = session.pseudonymize(prompt)
print(safe_prompt)
# خروجی: "کد ملی بیمار [IR_NATIONAL_ID_1] و شماره تماس [IR_MOBILE_1] است."

# ۲. ارسال فقط متن امن (safe_prompt) به مدل زبانی. پاسخ فرضی مدل:
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

تابع `detect()` وظیفهٔ اجرای تشخیص‌دهنده‌ها، تجمیع نتایج و بررسی عدم همپوشانی (Overlap) را بر عهده دارد. در صورتی که دو تشخیص‌دهنده برای یک بازهٔ متنی مشترک گزارش تداخل ثبت کنند، سیستم با خطای `ValueError` متوقف می‌شود (Fail-loud) تا از جایگزینی‌های اشتباه و مخدوش شدن داده‌های محرمانه جلوگیری شود.

#### ۳. اعتبارسنجی و تشخیص کد ملی ایران

تشخیص و اعتبارسنجی کد ملی ۱۰ رقمی با الگوریتم رسمی باقیماندهٔ تقسیم بر ۱۱ (Modulo-11):

```python
from fa_redact import IranianNationalIDDetector, is_valid_national_id

# مقادیر نمونهٔ الگوریتمی (غیرواقعی):
is_valid_national_id("1234567891")  # True (معتبر)
is_valid_national_id("۱۲۳۴۵۶۷۸۹۱")  # True (پشتیبانی از ارقام فارسی)
is_valid_national_id("1234567890")  # False (رقم کنترلی نامعتبر)
is_valid_national_id("1111111111")  # False (رد ارقام تکراری جعلی)
```

- **بررسی چکسام**: اعمال فرمول کنترلی استاندارد ثبت احوال.
- **رد کدهای تکراری جعلی**: کدهایی مانند `0000000000` یا `1111111111` که فرمول چکسام را پاس می‌کنند اما نامعتبرند، رد می‌شوند.
- **طول دقیق**: ورودی باید دقیقاً ۱۰ رقم باشد؛ صفرهای ابتدایی حذف یا به‌طور خودکار اضافه نمی‌شوند.
- **سلب مسئولیت استعلام**: این اعتبارسنجی صرفاً ساختار ریاضی را تایید می‌کند و استعلامی از سامانهٔ ثبت احوال انجام نمی‌دهد.

#### ۴. اعتبارسنجی و تشخیص شماره موبایل ایران

تشخیص شماره‌های همراه بر اساس سند رسمی شماره‌گذاری سازمان تنظیم مقررات و ارتباطات رادیویی ایران (CRA / ITU 2026):

```python
from fa_redact import IranianMobileNumberDetector, is_valid_mobile_number

is_valid_mobile_number("09123456789")     # True (قالب داخلی)
is_valid_mobile_number("۰۹۱۲۳۴۵۶۷۸۹")     # True (ارقام فارسی)
is_valid_mobile_number("+989123456789")   # True (قالب بین‌المللی با +98)
is_valid_mobile_number("00989351234567")  # True (قالب بین‌المللی با 0098)
is_valid_mobile_number("09412345678")     # False (شماره ثابت غیرجغرافیایی)
```

- **تفکیک پیش‌شماره‌های همراه**: تنها شماره‌های اپراتورهای سیار (همراه اول، ایرانسل، رایتل، شاتل موبایل و...) معتبر شناخته می‌شوند.
- **رد پیش‌شماره‌های غیرموبایل**: پیش‌شماره‌هایی نظیر `094` (ثابت غیرجغرافیایی) یا `09950` (ترانک عمومی) به عنوان موبایل پذیرفته نمی‌شوند.
- **سلب مسئولیت مالکیت**: اعتبارسنجی ساختاری است و فعال بودن سیم‌کارت یا هویت مالک آن را بررسی نمی‌کند.

#### ۵. ویژگی‌های امنیتی و رفتاری نشست نام‌مستعارسازی

کلاس `PseudonymizationSession` رفتارهای امنیتی زیر را تضمین می‌کند:

- **ایزوله‌سازی نشست‌ها (Mapping Isolation)**: هر نشست دارای حافظه و نگاشت مستقل است.
- **یکپارچگی هویت در چند مرحله (Cross-Call Identity)**: هویت یک موجودیت بر اساس `(type, normalized_value)` ردیابی می‌شود. بنابراین `۰۹۱۲۳۴۵۶۷۸۹` در نوبت اول و `09123456789` در نوبت دوم هر دو به `[IR_MOBILE_1]` متصل می‌شوند.
- **بازگردانی به اولین نمایش دیده‌شده (First-Observed Representative)**: در زمان `restore()`، نشان‌گذار به همان فرمت نویسه‌ای که در اولین مشاهده ثبت شده بود بازگردانده می‌شود.
- **بازگردانی غیرآبشاری (Non-Cascading Restore)**: بازگردانی در یک مرحله و با فرار کاراکترهای خاص انجام می‌شود تا اگر مقدار بازگردانده‌شده شبیه به نشان‌گذار باشد، بازگردانی بازگشتی و ناخواسته رخ ندهد.
- **به‌روزرسانی اتمیک (Atomic Updates)**: اگر در حین پردازش خطایی رخ دهد، وضعیت نشست و شمارنده‌ها دست‌نخورده باقی می‌مانند.
- **محافظت در برابر تداخل تاریخی با نشان‌گذارهای متنی**: اگر در متون قبلی عبارتی مانند `[IR_MOBILE_2]` به عنوان متن عادی وجود داشته باشد، سیستم آن شماره را رزرو کرده و برای شناسه‌های واقعی جدید اختصاص نمی‌دهد.
- **عدم دستکاری نشان‌گذارهای ناشناخته**: نشان‌گذارهایی که در نگاشت نشست ثبت نشده‌اند (مانند `[IR_MOBILE_99]`) بدون خطا و دست‌نخورده باقی می‌مانند.

---

### تشخیص‌دهنده‌های سفارشی (Custom Detectors)

معماری `fa-redact` مبتنی بر پروتکل‌های ساختاری پایتون (Duck Typing) است. شما می‌توانید بدون نیاز به ارث‌بری، کلاس‌هایی با متد `detect(self, text: str) -> Sequence[Detection]` بسازید و آن‌ها را به توابع کتابخانه منتقل کنید:

```python
import re
from typing import Sequence
from fa_redact import Detection, detect

class MedicalRecordNumberDetector:
    """نمونه تشخیص‌دهنده سفارشی برای شماره پرونده پزشکی بیمارستانی (MRN)."""
    
    def detect(self, text: str) -> Sequence[Detection]:
        detections = []
        for match in re.finditer(r"\bMRN-\d{6}\b", text):
            detections.append(
                Detection(
                    type="MRN",
                    start=match.start(),
                    end=match.end(),
                    value=match.group(0),
                    normalized_value=match.group(0),
                )
            )
        return detections

# استفاده همزمان از تشخیص‌دهنده سفارشی:
text = "پرونده بیمار با MRN-123456 و شماره ۰۹۱۲۳۴۵۶۷۸۹ بررسی شد."
detections = detect(text, detectors=[MedicalRecordNumberDetector()])
```

---

### کاربرد در حوزهٔ سلامت و هوش مصنوعی (Healthcare & AI/LLM)

```text
محیط محلی و امن بیمارستان / سازمان
  │
  ├── ۱. متن پرونده حاوی شناسه‌های حساس بیمار
  │      ↓
  ├── ۲. session.pseudonymize(raw_text)
  │      ↓
  ├── ۳. متن پالایش‌شده با نشان‌گذارهای [IR_NATIONAL_ID_1] و [IR_MOBILE_1]
  │
  ▼  (ارسال صرفاً متن امن به هوش مصنوعی خارج از سازمان)
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

> **یادآوری مهم**: این معماری از نشت شناسه‌های مستقیم پیش‌بینی‌شده جلوگیری می‌کند، اما به خودی خود به معنای ناشناس‌سازی کامل پرونده بالینی نیست؛ زیرا ممکن است داده‌های متنی دیگری (مانند نام، آدرس یا تاریخ‌ها) در متن وجود داشته باشند که هنوز توسط این نسخه پشتیبانی نمی‌شوند.

---

### جدول پوشش و محدودیت‌ها در نسخه v0.1.0

| نوع شناسه هویتی | وضعیت در v0.1.0 | توضیحات |
| :--- | :---: | :--- |
| **کد ملی ایران** | ✅ پشتیبانی می‌شود | اعتبارسنجی دقیق ۱۰ رقمی با الگوریتم Modulo-11 |
| **شماره تلفن همراه ایران** | ✅ پشتیبانی می‌شود | اعتبارسنجی پیش‌شماره‌های مصوب رگولاتوری ایران (CRA 2026) |
| **نام اشخاص** | ❌ هنوز پشتیبانی نمی‌شود | نیازمند مدل‌های پردازش زبان طبیعی و بازشناسی موجودیت‌های نام‌دار (NER) |
| **آدرس پستی و موقعیت مکانی** | ❌ هنوز پشتیبانی نمی‌شود | موجودیت‌های غیرساختاریافته |
| **آدرس ایمیل** | ❌ هنوز پشتیبانی نمی‌شود | برنامه‌ریزی‌شده برای نسخه‌های آتی |
| **شماره پرونده پزشکی (MRN)** | ❌ هنوز پشتیبانی نمی‌شود | فرمت سازمانی (قابل تعریف با Custom Detector) |
| **شماره بیمه درمانی** | ❌ هنوز پشتیبانی نمی‌شود | فرمت سازمانی |
| **شماره کارت بانکی (PAN)** | ❌ هنوز پشتیبانی نمی‌شود | برنامه‌ریزی‌شده برای نسخه‌های آتی |
| **شماره شبا (IBAN)** | ❌ هنوز پشتیبانی نمی‌شود | برنامه‌ریزی‌شده برای نسخه‌های آتی |
| **تاریخ تولد و زمان‌ها** | ❌ هنوز پشتیبانی نمی‌شود | برنامه‌ریزی‌شده برای نسخه‌های آتی |

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
