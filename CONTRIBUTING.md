# Contributing to fa-redact

Thank you for your interest in contributing to `fa-redact`.

`fa-redact` is a privacy-first Persian PII detection and de-identification toolkit, especially for healthcare, clinical NLP, and sensitive-data workflows.

Contributions are welcome, including bug fixes, new detectors, Persian-language improvements, tests, documentation, and performance improvements.

## Getting Started

### 1. Fork the repository

Fork the repository on GitHub:

https://github.com/mehdimt1980/fa-redact

Then clone your fork:

```bash
git clone https://github.com/<your-username>/fa-redact.git
cd fa-redact
```

Add the original repository as `upstream`:

```bash
git remote add upstream https://github.com/mehdimt1980/fa-redact.git
```

### 2. Create a branch

Keep your local `main` branch up to date:

```bash
git checkout main
git fetch upstream
git merge upstream/main
```

Create a new branch for your contribution:

```bash
git checkout -b feat/my-feature
```

Examples:

```text
feat/new-detector
fix/span-offset
docs/update-readme
test/add-edge-cases
```

Do not work directly on `main`.

## Development Setup

`fa-redact` requires Python 3.10 or newer.

Install the project with development dependencies:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Before Submitting a Pull Request

Run the test and quality checks:

```bash
python -m pytest
ruff check .
ruff format --check .
mypy src
mypy tests
python -m build
python -m twine check dist/*
```

GitHub Actions will run the required checks again when you open a pull request.

## Privacy and Test Data

Never commit real personally identifiable information or confidential data.

Do not include:

- real patient records
- real clinical documents containing PII
- passwords, API keys, or tokens
- private datasets
- confidential institutional data

Use synthetic or non-personal test data only.

If you are unsure whether data is safe to publish, do not commit it.

## Core Project Rules

Contributions should preserve the following principles.

### Position-preserving normalization

Normalization used for detection must preserve character offsets.

In particular:

```python
len(normalized) == len(original)
```

Changes must not unexpectedly alter span positions through character insertion, deletion, whitespace collapsing, or ZWNJ removal.

### Privacy-safe behavior

Detected PII should not be exposed through logs, exceptions, debugging output, or other unintended channels.

### Local-first design

The core library should remain suitable for local and privacy-sensitive environments.

### Lightweight core

Avoid adding mandatory runtime dependencies unless there is a strong technical reason.

## Tests

Bug fixes should include regression tests where possible.

New features should include tests for:

- expected behavior
- relevant edge cases
- Persian text variations where applicable
- span and offset correctness
- privacy-sensitive behavior where relevant

## Pull Requests

Push your branch to your fork:

```bash
git push -u origin feat/my-feature
```

Then open a pull request into:

```text
mehdimt1980/fa-redact:main
```

Please keep pull requests focused and explain:

- what changed
- why the change is needed
- how it was tested
- whether it affects public API behavior
- whether it affects privacy, normalization, or span offsets

Before larger changes, please review:

- `README.md`
- `PROJECT_STATUS.md`
- `ROADMAP.md`

Opening an issue first is recommended for substantial architectural changes.

## Commit Messages

Clear commit messages are preferred.

Examples:

```text
feat: add Persian passport detector
fix: preserve offsets around ZWNJ
test: add synthetic national ID edge cases
docs: improve contribution guide
```

## Security

For security or privacy vulnerabilities, please follow the process described in `SECURITY.md`.

Do not disclose sensitive vulnerabilities publicly before they can be reviewed.

## License

By contributing to `fa-redact`, you agree that your contribution may be distributed under the project's MIT License.

Thank you for helping improve Persian-language privacy tooling.
