# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-05

### Added
- Immutable `Detection` data model preserving raw and normalized value representations, with span validation and `from_texts()` safe factory (Phase 3).
- `Detector` structural typing protocol defining standard contract for entity detectors (Phase 3).
- Position-preserving Persian and Arabic-Indic text normalization (`normalize_digits`, `normalize_letters`, `normalize_text`) preserving exact Unicode string lengths and offsets (Phase 2).
- Initial project foundation and repository scaffolding (Phase 1).
- Package metadata and build configuration in `pyproject.toml` with `src/` layout.
- Version export `fa_redact.__version__`.
- Type marker (`py.typed`) and static typing configuration (`mypy`).
- Linting and code formatting configuration (`ruff`).
- Initial unit tests and test framework setup (`pytest`).
- Initial documentation and MIT license.
