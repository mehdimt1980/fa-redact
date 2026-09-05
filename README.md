# fa-redact

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`fa-redact` is an early-stage Python toolkit for privacy-preserving processing of Persian/Iranian text. The project is being designed to detect, pseudonymize, and redact personal identifiers, with healthcare and AI/LLM workflows as a primary use case.

> **Status: Early Development (Phase 3 - Data Models & Protocol Foundation)**  
> This package is currently in pre-alpha development. It does not yet include active PII detection, redaction, or pseudonymization capabilities. The current release provides position-preserving Persian text normalization and the core `Detection` data model and `Detector` protocol.

---

## Current Functionality

### 1. Position-Preserving Text Normalization
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

### 2. Detection Data Model & Protocols
The immutable `Detection` dataclass represents identified spans while preserving both the original text and its normalized form:

```python
from fa_redact import Detection, normalize_text

text = "کد ملی بیمار ۰۰۱۲۳۴۵۶۷۸ است."
normalized = normalize_text(text)

# Example illustrative Detection instance
raw_id = "۰۰۱۲۳۴۵۶۷۸"
start = text.index(raw_id)
end = start + len(raw_id)

detection = Detection.from_texts(
    type="IR_NATIONAL_ID",
    original_text=text,
    normalized_text=normalized,
    start=start,
    end=end,
)

print(detection.value)  # "۰۰۱۲۳۴۵۶۷۸" (raw from original)
print(detection.normalized_value)  # "0012345678" (normalized representation)
```

*(Note: Built-in PII and healthcare detector implementations will be introduced in subsequent phases.)*

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
