# fa-redact

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`fa-redact` is a lightweight, privacy-first Python toolkit for Persian/Iranian Personally Identifiable Information (PII) detection, redaction, and pseudonymization, designed especially for healthcare and AI/LLM applications.

> **Status: v0.1.0 Release Candidate (Alpha)**  
> This package provides position-preserving Persian text normalization, immutable `Detection` data models, strict Iranian National ID (Code Melli) and Mobile Number validators and detectors, high-level `detect()` orchestration, stateless placeholder-based `redact()`, and stateful `PseudonymizationSession` with safe restoration for AI/LLM workflows.

---

## Quick Start

### 1. Detect PII
Identify sensitive spans with exact source offsets and normalized representations:

```python
from fa_redact import detect

text = "بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره ۰۹۱۲۳۴۵۶۷۸۹ مراجعه کرد."
detections = detect(text)

for d in detections:
    print(f"Type: {d.type} | Value: {d.value} | Span: [{d.start}:{d.end}]")
```

### 2. Redact PII (Stateless)
Sanitize text into safe, typed placeholders with fresh counter numbering:

```python
from fa_redact import redact

text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱، تماس: ۰۹۱۲۳۴۵۶۷۸۹، تماس دوم: 09123456789"
safe_text = redact(text)
print(safe_text)
# Output: "کد ملی: [IR_NATIONAL_ID_1]، تماس: [IR_MOBILE_1]، تماس دوم: [IR_MOBILE_1]"
```

### 3. Stateful Pseudonymization & AI/LLM Restoration
Maintain consistent entity mappings across conversation turns and restore placeholders locally:

```python
from fa_redact import PseudonymizationSession

session = PseudonymizationSession()

# 1. Pseudonymize prompt locally before sending to external LLM:
prompt = "کد ملی بیمار ۱۲۳۴۵۶۷۸۹۱ و شماره تماس ۰۹۱۲۳۴۵۶۷۸۹ است."
safe_prompt = session.pseudonymize(prompt)
print(safe_prompt)
# Output: "کد ملی بیمار [IR_NATIONAL_ID_1] و شماره تماس [IR_MOBILE_1] است."

# 2. Send ONLY safe_prompt to external LLM. Simulated LLM response:
llm_response = "جهت پیگیری بیمار با [IR_MOBILE_1] هماهنگ شد."

# 3. Restore placeholders locally within your trusted boundary:
restored = session.restore(llm_response)
print(restored)
# Output: "جهت پیگیری بیمار با ۰۹۱۲۳۴۵۶۷۸۹ هماهنگ شد."
```

---

## Installation

### Future PyPI Release
Once v0.1.0 is published to PyPI:

```bash
pip install fa-redact
```

### Development Installation
For development or installing from source:

```bash
git clone https://github.com/mehdimt1980/fa-redact.git
cd fa-redact
pip install -e ".[dev]"
```

---

## Detailed Capabilities

### 1. Stateful Pseudonymization Sessions
The `PseudonymizationSession` class manages state across multi-turn workflows:
- **Local Sensitive Mapping**: `session.mapping` holds `{placeholder: original_pii}`. Keep this mapping strictly inside your local trusted environment; never transmit it to external AI services.
- **First-Observed Representative Restoration**: For each unique identity `(type, normalized_value)`, the session records the first-observed raw string as its semantic restoration target.
- **Non-Cascading Single-Pass Restoration**: `restore()` performs an escaped single-pass substitution, preventing recursive evaluation if restored values contain placeholder-like text.
- **Cross-Call Collision Safety**: Generated placeholders automatically avoid colliding with literal placeholder-shaped tokens seen in current or previous inputs within the session.
- **Unknown Placeholders**: Unmapped placeholders (e.g., `[IR_MOBILE_999]`) are left untouched without error.

> [!WARNING]
> **Sensitive Data Notice**: `session.mapping` contains original PII. Treat it as sensitive data and protect it accordingly.
>
> **Scope Limitation**: `fa-redact` detects and redacts only the PII types supported by its enabled detectors (Iranian National IDs and Iranian Mobile Numbers in v0.1.0). It does not provide complete automated clinical de-identification.

### 2. Position-Preserving Normalization
`fa-redact` provides pure, deterministic normalization where each Unicode character maps 1-to-1 to a normalized code point (`len(normalized) == len(original)`), guaranteeing that character offsets remain identical to the original input text:

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

### 3. Detection Data Model & Pipeline
The immutable `Detection` dataclass represents identified spans:

```python
from fa_redact import Detection, IranianNationalIDDetector, detect, normalize_text

# Using custom detector list:
detections = detect("کد ملی: ۱۲۳۴۵۶۷۸۹۱", detectors=[IranianNationalIDDetector()])
for d in detections:
    assert d.type == "IR_NATIONAL_ID"
    assert d.value == "۱۲۳۴۵۶۷۸۹۱"
    assert d.normalized_value == "1234567891"
```

### 4. Iranian National ID Validation & Detection
Validate and detect Iranian National IDs (Code Melli / `کد ملی`) with strict modulo-11 checksum verification:

```python
from fa_redact import IranianNationalIDDetector, is_valid_national_id

# Algorithmic test vectors not sourced from personal data
is_valid_national_id("1234567891")  # True
is_valid_national_id("۱۲۳۴۵۶۷۸۹۱")  # True (Persian digits)
is_valid_national_id("1234567890")  # False (invalid check digit)
is_valid_national_id("1111111111")  # False (repeated digits rejected)
```

> **Verification Notice**: Checksum validation verifies mathematical structure only without querying official registries. These values are algorithmic test vectors not sourced from personal or patient records. Checksum validity does not establish whether an identifier has been officially issued to an individual.

### 5. Iranian Mobile Number Validation & Detection
Validate and detect Iranian mobile numbers against official Communications Regulatory Authority (CRA) mobile NDC prefixes:

```python
from fa_redact import IranianMobileNumberDetector, is_valid_mobile_number

# Domestic, +98 international, and 0098 international formats
is_valid_mobile_number("09123456789")  # True (domestic)
is_valid_mobile_number("۰۹۱۲۳۴۵۶۷۸۹")  # True (Persian digits)
is_valid_mobile_number("+989123456789")  # True (+98 format)
is_valid_mobile_number("00989351234567")  # True (0098 format)
is_valid_mobile_number("09412345678")  # False (fixed non-geographical)
```

> **Numbering Plan Notice**: Prefix classification is based on the official Communications Regulatory Authority (CRA) National Numbering Plan (published via ITU Operational Bulletin No. 1340). Prefix validation confirms structural allocation only and does not verify subscriber ownership, active SIM status, or carrier identity.

---

## Privacy-Safe Test-Data Policy

All test fixtures, examples, and documentation in `fa-redact` are constructed from **synthetic test vectors, algorithmic patterns, and non-personal sample data**. No real patient records, clinical charts, credentials, or personal datasets are used or included in the repository.

---

## Important Disclaimers

- **Not Production Clinical Software**: `fa-redact` is an experimental, early-stage open-source library and is **not** certified as a medical device or approved for production clinical decision-making.
- **No Inherent Regulatory Compliance**: Use of this library does not automatically ensure compliance with HIPAA, GDPR, or local privacy regulations. Organizations remain responsible for verifying that their data pipelines meet applicable legal and privacy standards.
- **No Identity Verification**: Validation functions verify format and mathematical structure only; they do not query government registries or authenticate individuals.

---

## Development & Quality Checks

Run the automated test suite:
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

---

## License

This project is licensed under the [MIT License](LICENSE).
