# fa-redact

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`fa-redact` is an early-stage Python toolkit for privacy-preserving processing of Persian/Iranian text. The project is being designed to detect, pseudonymize, and redact personal identifiers, with healthcare and AI/LLM workflows as a primary use case.

> **Status: Early Development (Phase 6 - Detection Pipeline & Public detect() API)**  
> This package is currently in pre-alpha development. It provides position-preserving Persian text normalization, immutable `Detection` models, Iranian National ID and Mobile Number validation/detection, and a unified `detect()` orchestration pipeline.

---

## Current Functionality

### 1. High-Level Detection Pipeline
The top-level `detect()` function automatically normalizes input text and runs entity detectors, returning `Detection` objects in deterministic source-text order:

```python
from fa_redact import detect

text = "بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره تماس ۰۹۱۲۳۴۵۶۷۸۹ مراجعه نمود."
detections = detect(text)

for d in detections:
    print(f"{d.type}: {d.value} -> {d.normalized_value}")

    # Offsets map identically to the source text:
    assert text[d.start:d.end] == d.value
```

You can also pass a custom sequence of detectors (or custom implementations adhering to the `Detector` protocol):

```python
from fa_redact import detect, IranianNationalIDDetector

# Run only specific detectors:
detections = detect(text, detectors=[IranianNationalIDDetector()])
```

### 2. Position-Preserving Text Normalization
`fa-redact` provides pure, deterministic normalization functions that map individual Unicode code points 1-to-1 (`len(normalized) == len(original)`), guaranteeing that character offsets remain identical to the original input text:

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

### 3. Detection Data Model
The immutable `Detection` dataclass represents identified spans while preserving both the original text and its normalized form:

```python
from fa_redact import Detection, normalize_text

text = "کد ملی بیمار ۰۰۱۲۳۴۵۶۷۹ است."
normalized = normalize_text(text)

raw_id = "۰۰۱۲۳۴۵۶۷۹"
start = text.index(raw_id)
end = start + len(raw_id)

detection = Detection.from_texts(
    type="IR_NATIONAL_ID",
    original_text=text,
    normalized_text=normalized,
    start=start,
    end=end,
)

print(detection.value)  # "۰۰۱۲۳۴۵۶۷۹" (raw from original)
print(detection.normalized_value)  # "0012345679" (normalized representation)
```

### 4. Iranian National ID Validation
Validate the modulo-11 checksum of Iranian National IDs (Code Melli / `کد ملی`) across ASCII, Persian, and Arabic-Indic digits:

```python
from fa_redact import is_valid_national_id

# Checksum-valid test vectors not sourced from personal data
is_valid_national_id("1234567891")  # True
is_valid_national_id("۱۲۳۴۵۶۷۸۹۱")  # True (Persian digits)
is_valid_national_id("1234567890")  # False (invalid check digit)
is_valid_national_id("1111111111")  # False (repeated digits rejected)
```

> **Note on Verification Scope**: Checksum validation verifies mathematical structure only without querying official registries. These example values are algorithmic test vectors not sourced from personal or patient records. Checksum validity does not establish whether an identifier has actually been issued or belongs to a real individual.

### 5. Iranian National ID Detection
Find checksum-valid Iranian National IDs in Persian and mixed-language text:

```python
from fa_redact import IranianNationalIDDetector, normalize_text

text = "بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱ جهت بستری مراجعه کرد."
normalized = normalize_text(text)

detector = IranianNationalIDDetector()
detections = detector.detect(text, normalized)

for d in detections:
    print(d.type)              # "IR_NATIONAL_ID"
    print(d.value)             # "۱۲۳۴۵۶۷۸۹۱"
    print(d.normalized_value)  # "1234567891"

    # Offsets map identically to original and normalized text:
    assert text[d.start:d.end] == d.value
    assert normalized[d.start:d.end] == d.normalized_value
```

### 6. Iranian Mobile Number Validation
Validate Iranian mobile numbers against official 2026 Communications Regulatory Authority (CRA) mobile NDC prefixes:

```python
from fa_redact import is_valid_mobile_number

# Domestic, +98 international, and 0098 international formats
is_valid_mobile_number("09123456789")     # True (domestic)
is_valid_mobile_number("۰۹۱۲۳۴۵۶۷۸۹")     # True (Persian digits)
is_valid_mobile_number("+989123456789")   # True (+98 format)
is_valid_mobile_number("00989351234567")  # True (0098 format)
is_valid_mobile_number("09412345678")     # False (fixed non-geographical)
is_valid_mobile_number("09061234567")     # False (unlisted prefix)
```

> **Note on Numbering Plan**: Prefix classification is derived from the Communications Regulatory Authority (CRA) of Iran National Numbering Plan (communication dated 22 April 2026, published via ITU Operational Bulletin No. 1340). Numbering plans may evolve over time. Prefix validation confirms structural allocation only and does not verify subscriber ownership, active SIM status, or carrier identity.

### 7. Iranian Mobile Number Detection
Find prefix-valid Iranian mobile numbers across domestic and international representations:

```python
from fa_redact import IranianMobileNumberDetector, normalize_text

text = "شماره همراه بیمار: ۰۹۱۲۳۴۵۶۷۸۹ و شماره پشتیبان: +989351234567"
normalized = normalize_text(text)

detector = IranianMobileNumberDetector()
detections = detector.detect(text, normalized)

for d in detections:
    print(d.type)              # "IR_MOBILE"
    print(d.value)             # "۰۹۱۲۳۴۵۶۷۸۹" or "+989351234567"
    print(d.normalized_value)  # "09123456789" or "+989351234567"

    # Offsets map identically to original and normalized text:
    assert text[d.start:d.end] == d.value
    assert normalized[d.start:d.end] == d.normalized_value
```

*(Note: Redaction, pseudonymization, and additional entity detectors such as medical record numbers, postal codes, and names are under active development.)*

---

## Vision & Future Roadmap

The primary mission of `fa-redact` is to enable privacy-first processing of Persian text before it is consumed by AI/LLM systems, data pipelines, or third-party services, while retaining essential analytical and clinical utility.

### Future Use Cases
Future releases aim to support redaction and pseudonymization across scenarios such as:
- **Clinical Notes & Medical Records**: De-identifying patient notes, discharge summaries, and referral letters.
- **Patient Communications**: Sanitizing patient messages and support interactions.
- **Operational & Hospital Text**: Processing administrative logs, intake forms, and operational records.
- **Healthcare Datasets**: Preparing de-identified datasets for research and analytics while preserving medical context (diagnoses, medications, procedures, symptoms).
- **AI/LLM Prompts**: Sanitizing user prompts and context documents before sending them to large language models.

### Target Identifiers (Planned)
- **General Persian/Iranian PII**: Phone numbers, Iranian National IDs (کد ملی), bank card numbers, IBANs (شماره شبا), postal codes, addresses, personal names, and IP addresses.
- **Healthcare Identifiers**: Medical record numbers (MRNs), admission/case IDs, insurance numbers, and provider identifiers.

---

## Important Disclaimers

- **Not Production Clinical Software**: `fa-redact` is an experimental, early-stage open-source library and is **not** certified as a medical device or approved for production clinical decision-making.
- **No Inherent Regulatory Compliance**: Use of this library does not automatically ensure compliance with HIPAA, GDPR, or local privacy laws. Organizations remain responsible for validating that their data pipelines meet applicable legal and privacy standards.

---

## Installation & Development Setup

### Requirements
- Python >= 3.10

### Installation (Editable / Development)

Clone the repository and install development dependencies:

```bash
git clone https://github.com/mehdimt1980/fa-redact.git
cd fa-redact
pip install -e ".[dev]"
```

### Development & Quality Checks

Run the test suite:
```bash
python -m pytest
```

Check code quality and linting:
```bash
ruff check .
```

Check code formatting:
```bash
ruff format --check .
```

Run static type checking:
```bash
mypy src
```

---

## License

This project is licensed under the [MIT License](LICENSE).
