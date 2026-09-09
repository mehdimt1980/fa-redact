<div align="center">

# fa-redact

**Local-first Persian PII detection and de-identification for Python**

Protect Persian and Iranian sensitive data before it reaches an external API, LLM, analytics pipeline, or third-party service.

[![PyPI version](https://img.shields.io/pypi/v/fa-redact.svg)](https://pypi.org/project/fa-redact/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/mehdimt1980/fa-redact/actions/workflows/ci.yml/badge.svg)](https://github.com/mehdimt1980/fa-redact/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Zero runtime dependencies](https://img.shields.io/badge/core%20runtime%20deps-0-39e6a6)](pyproject.toml)

[Website](https://fa-redact-site.vercel.app/) · [PyPI](https://pypi.org/project/fa-redact/) · [Full reference](docs/REFERENCE.md) · [Changelog](CHANGELOG.md) · [فارسی](#فارسی)

<img src="https://fa-redact-site.vercel.app/opengraph-image" alt="fa-redact — Persian PII detection and de-identification" width="820" />

</div>

---

## What is fa-redact?

`fa-redact` is a privacy-first Python toolkit for **detecting, redacting, and pseudonymizing Persian/Iranian personally identifiable information (PII)**.

It is designed for workflows where raw sensitive text should remain inside your trusted boundary — especially **healthcare, clinical NLP, enterprise data processing, and AI/LLM applications**.

The deterministic core is pure Python and has **zero mandatory runtime dependencies**.

> **Status: Alpha**  
> Package version in this source tree: `v0.4.0`

```bash
pip install fa-redact
```

## See it in 20 seconds

```python
from fa_redact import redact

text = "بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره ۰۹۱۲۳۴۵۶۷۸۹ مراجعه کرد."
print(redact(text))
```

Output:

```text
بیمار با کد ملی [IR_NATIONAL_ID_1] و شماره [IR_MOBILE_1] مراجعه کرد.
```

No API call. No service account. No raw PII leaves your process.

---

## Why this exists

Persian text creates practical problems that generic regex-only masking often handles poorly:

- Persian, Arabic-Indic, and ASCII digits may appear in the same document.
- Arabic/Persian letter variants can complicate matching.
- Naive normalization can shift character offsets.
- Iranian identifiers often have structural or checksum rules that are stronger than loose pattern matching.
- Clinical and AI workflows may need stable pseudonyms across multiple turns, not one-off replacement.

`fa-redact` is built around four principles:

**Local by default.** Detection and transformation run inside your environment.

**Exact offsets.** Position-preserving normalization keeps detected spans aligned with the original Persian source text.

**Deterministic where possible.** Structured identifiers use explicit validation rules rather than only permissive regexes.

**ML only when requested.** Persian PERSON NER is optional; the base package remains lightweight.

---

## Healthcare and LLM pattern

A common use case is protecting Persian clinical text before it crosses a system boundary:

```text
Raw clinical text
       │
       ▼
  fa-redact
(local detection + pseudonymization)
       │
       ▼
Protected text only
       │
       ▼
LLM / API / downstream system
       │
       ▼
Local restoration when needed
```

```python
from fa_redact import PseudonymizationSession

session = PseudonymizationSession()

prompt = "کد ملی بیمار ۱۲۳۴۵۶۷۸۹۱ و شماره تماس ۰۹۱۲۳۴۵۶۷۸۹ است."
protected_prompt = session.pseudonymize(prompt)

# Send only `protected_prompt` outside your trusted boundary.
llm_response = "جهت هماهنگی با بیمار با [IR_MOBILE_1] تماس حاصل فرمایید."
restored = session.restore(llm_response)
```

> [!IMPORTANT]
> `fa-redact` is a technical de-identification toolkit. It does **not** by itself establish GDPR, HIPAA, medical-device, or institutional compliance.

---

## Coverage

### Included by default

| Type | Entity | Validation |
|---|---|---|
| Iranian National ID | `IR_NATIONAL_ID` | structural + checksum |
| Iranian mobile number | `IR_MOBILE` | prefix / numbering-plan aware |
| Iranian IBAN / Sheba | `IR_IBAN` | MOD-97 |

### Explicit opt-ins

- Email addresses
- 16-digit bank card / PAN values
- Iranian Legal Entity National ID
- Institution-specific identifiers such as MRN, Patient ID, Admission ID, and Encounter ID
- Explicit overlap/conflict-resolution policies

### Optional Persian PERSON NER

PyTorch backend:

```bash
pip install "fa-redact[ner]"
```

ONNX backend:

```bash
pip install "fa-redact[onnx]"
```

NER remains opt-in. The base package does not force an ML stack on users who only need deterministic PII handling.

---

## Exact source offsets

```python
from fa_redact import detect

text = "تماس با ۰۹۱۲۳۴۵۶۷۸۹"

for d in detect(text):
    assert text[d.start:d.end] == d.value
    print(d.type, d.start, d.end, d.normalized_value)
```

Position-preserving normalization keeps detected spans aligned with the original source text.

---

## CLI

```bash
echo "کد ملی بیمار ۱۲۳۴۵۶۷۸۹۱ است." | fa-redact redact
```

```bash
fa-redact report clinical_note.txt
```

The report path is designed to expose aggregate detection metadata without returning raw detected PII values.

---

## Structured data

Explicitly target fields instead of recursively scanning an entire object:

```python
from fa_redact import redact_fields

record = {
    "note": "تماس با ۰۹۱۲۳۴۵۶۷۸۹ جهت هماهنگی",
    "age": 42,
}

safe_record = redact_fields(record, ["note"])
```

Unselected fields are not scanned or modified.

---

## Design choices

| Choice | Why |
|---|---|
| Zero-dependency deterministic core | Easier review, deployment, and on-premise use |
| Position-preserving normalization | Keeps source offsets trustworthy |
| Conservative defaults | Avoids silently expanding detection scope |
| Explicit opt-in detectors | Applications choose their own privacy boundary |
| Fail-loud conflict handling by default | Ambiguous overlaps are not silently guessed away |
| Optional PyTorch / ONNX NER | ML is available without forcing an ML stack on every user |
| Privacy-safe reporting | Operational metadata without echoing raw values |

---

## Documentation

The front README is intentionally concise. The previous comprehensive README has been preserved as the **full technical reference**, including detector semantics, validation rules, CLI behavior, conflict policies, structured helpers, NER, privacy/security notes, and release guidance.

**→ [Read the full technical reference](docs/REFERENCE.md)**

Also useful:

- [Changelog](CHANGELOG.md)
- [Roadmap](ROADMAP.md)
- [Project status](PROJECT_STATUS.md)
- [Release process](RELEASING.md)

---

## Contributing and feedback

Feedback is especially useful from people working with **Persian NLP, healthcare/clinical NLP, privacy engineering, local AI, LLM safety, and Iranian structured identifiers**.

If you find a bug, false positive, false negative, missing detector, integration opportunity, or documentation gap, please [open an issue](https://github.com/mehdimt1980/fa-redact/issues).

Pull requests are welcome. If the project is useful to you, a GitHub star helps other developers discover it.

---

# فارسی

**fa-redact** یک ابزار متن‌باز پایتون برای **شناسایی، حذف و ناشناس‌سازی اطلاعات شخصی و حساس در متن فارسی** است؛ با تمرکز ویژه بر داده‌های ایرانی، سلامت، متن‌های بالینی و جریان‌های کاری هوش مصنوعی.

هسته‌ی اصلی پروژه به‌صورت محلی اجرا می‌شود و **هیچ وابستگی اجباری در زمان اجرا ندارد**.

> **وضعیت: آلفا**  
> نسخه بسته در این درخت منبع: `v0.4.0`

```bash
pip install fa-redact
```

نمونه‌ی ساده:

```python
from fa_redact import redact

text = "بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره ۰۹۱۲۳۴۵۶۷۸۹ مراجعه کرد."
print(redact(text))
```

خروجی:

```text
بیمار با کد ملی [IR_NATIONAL_ID_1] و شماره [IR_MOBILE_1] مراجعه کرد.
```

### چرا fa-redact؟

- پردازش داده به‌صورت **محلی** و بدون نیاز به API خارجی
- پشتیبانی از ارقام فارسی، عربی و لاتین
- حفظ دقیق موقعیت کاراکترها در متن اصلی
- اعتبارسنجی ساختاری شناسه‌های ایرانی
- نام‌های مستعار پایدار برای جریان‌های چندمرحله‌ای LLM
- شناسایی اختیاری نام اشخاص فارسی با PyTorch یا ONNX
- مناسب برای محیط‌های حساس مانند **سلامت، پزشکی، داده‌های بالینی و سامانه‌های on-premise**

### پوشش پیش‌فرض

- کد ملی ایران
- شماره موبایل ایران
- شماره شبا / IBAN ایران

قابلیت‌هایی مانند ایمیل، شماره کارت بانکی، شناسه ملی اشخاص حقوقی، شناسه‌های اختصاصی بیمارستان و شناسایی نام اشخاص به‌صورت صریح و اختیاری قابل اضافه‌شدن هستند.

### الگوی استفاده در سلامت و هوش مصنوعی

```text
متن خام بیمار
     ↓
fa-redact در محیط محلی
     ↓
متن محافظت‌شده
     ↓
LLM / API / سامانه‌ی بیرونی
     ↓
بازیابی محلی در صورت نیاز
```

> [!IMPORTANT]
> `fa-redact` یک ابزار فنی برای de-identification است و به‌تنهایی به معنی تضمین انطباق با GDPR، HIPAA یا الزامات حقوقی و سازمانی حوزه سلامت نیست.

برای جزئیات کامل detectorها، اعتبارسنجی‌ها، CLI، NER، conflict resolution، structured data و مدل امنیت و حریم خصوصی:

**→ [مستندات فنی کامل](docs/REFERENCE.md)**

گزارش bug، پیشنهاد detector جدید، integration و Pull Request بسیار ارزشمند است.

---

<div align="center">

**Open source · Local-first · Built for Persian**

[Website](https://fa-redact-site.vercel.app/) · [PyPI](https://pypi.org/project/fa-redact/) · [Issues](https://github.com/mehdimt1980/fa-redact/issues) · [MIT License](LICENSE)

</div>
