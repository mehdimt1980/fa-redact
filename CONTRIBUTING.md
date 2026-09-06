# Contributing to fa-redact

Thank you for your interest in contributing to `fa-redact`! We welcome contributions that improve PII detection, redaction safety, and Persian language processing.

---

## Development Setup

`fa-redact` requires **Python >= 3.10**.

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/mehdimt1980/fa-redact.git
   cd fa-redact
   ```

2. Install the package in editable mode with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

---

## Quality Standards and Verification

Before submitting changes, ensure all quality checks pass:

1. **Unit Tests**:
   ```bash
   python -m pytest
   ```

2. **Code Linting and Formatting**:
   ```bash
   ruff check .
   ruff format --check .
   ```

3. **Static Type Checking**:
   ```bash
   mypy src
   mypy tests
   ```

4. **Package Build & Distribution Validation**:
   ```bash
   python -m build
   python -m twine check dist/*
   ```

---

## Privacy-Safe Test-Data Policy

> [!IMPORTANT]
> **Never commit real Personally Identifiable Information (PII) or patient records to the repository.**

All test cases, examples, and documentation must adhere to the following rules:
- **No Real Personal Data**: Tests and examples must never contain real patient medical records, genuine clinical documents, credentials, API keys, or deliberately sourced personal identifiers.
- **Synthetic Test Vectors**: Use algorithmically generated test vectors, synthetic clinical prose, and non-personal sample data.
- **Source Clarification**: Test values are not sourced from personal datasets. While checksum-valid or prefix-valid test values are mathematically structured, they are constructed solely for automated testing and do not represent actual individuals.

---

## Core Architectural Principles

When contributing to `fa-redact`, please keep these foundational rules in mind:

1. **Zero Runtime Dependencies**: The core package relies strictly on the Python Standard Library. Any proposed runtime dependency must be thoroughly justified.
2. **Position-Preserving Normalization**: Text normalization must map exactly one Unicode code point to one Unicode code point (`len(normalized) == len(original)`). Never add, delete, or collapse whitespace or ZWNJs during normalization, ensuring character offsets (`start`, `end`) remain identical across raw and normalized text.
3. **Safe Redaction and Pseudonymization**: Redaction must never leak original PII in error messages or logs. Pseudonymization mappings (`session.mapping`) must remain local and confidential.

---

## Pull Request Guidelines

1. Before starting larger feature work, review [PROJECT_STATUS.md](PROJECT_STATUS.md) and [ROADMAP.md](ROADMAP.md) for current state, core invariants, and planned phase sequencing.
2. Create a feature or bugfix branch (e.g. `feat/new-detector` or `fix/span-offset`).
3. Write tests covering all new features, bug fixes, or edge cases.
4. Ensure automated tests, Ruff, mypy, and twine checks pass without warnings.
5. Keep pull requests focused and concise.
