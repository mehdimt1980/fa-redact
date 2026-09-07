# Release Guide

This document outlines the release process and PyPI Trusted Publishing setup for `fa-redact`.

---

## Architecture Overview

`fa-redact` uses **GitHub Actions OIDC Trusted Publishing** to securely publish releases to PyPI without storing long-lived API tokens or passwords in repository secrets.

The release process follows this flow:
```text
GitHub Release published (tag vX.Y.Z, e.g. v0.3.0)
        ↓
Trigger .github/workflows/release.yml (on: release: types: [published])
        ↓
Build sdist and wheel on Python 3.13
        ↓
Verify release tag matches pyproject.toml and fa_redact.__version__
        ↓
Validate package metadata via twine
        ↓
Execute isolated wheel smoke test
        ↓
Upload distribution artifacts
        ↓
Publish job requests PyPI OIDC token (environment: pypi, id-token: write)
        ↓
pypa/gh-action-pypi-publish uploads to PyPI
```

---

## 1. PyPI Trusted Publisher Configuration

`fa-redact` uses PyPI OIDC Trusted Publishing configured under the project on PyPI:

- **PyPI Project**: `fa-redact`
- **Owner**: `mehdimt1980`
- **Repository**: `fa-redact`
- **Workflow name**: `release.yml`
- **Environment name**: `pypi`

> [!NOTE]
> Do **NOT** add any PyPI API tokens or passwords to repository secrets or environment variables. The `release.yml` workflow uses OpenID Connect (OIDC) authentication (`id-token: write`).

---

## 2. GitHub Environment Configuration

The GitHub deployment environment is configured as follows:

1. In the repository on GitHub, navigate to **Settings** → **Environments**.
2. Environment name: `pypi`.
3. Required deployment permissions: `id-token: write`, `contents: read`.

---

## 3. Pre-Release Checklist (Release Preparation Gate)

Before creating and publishing any release tag (`vX.Y.Z`, e.g. `v0.3.0`):

- [ ] `main` branch CI is completely green (`.github/workflows/ci.yml`).
- [ ] Release preparation PR (e.g. `release/v0.3.0`) is reviewed and merged to `main`.
- [ ] Post-merge CI on `main` for the release preparation merge commit is verified green.
- [ ] Package version is aligned across `pyproject.toml` and `src/fa_redact/__init__.py` (`0.3.0`).
- [ ] `CHANGELOG.md` has a finalized section `[0.3.0] - 2026-09-07` and a fresh `[Unreleased]` section.
- [ ] Release notes in `CHANGELOG.md` accurately document Added capabilities, Important behaviors, and Limitations.
- [ ] Documentation (`README.md`, `PROJECT_STATUS.md`, `ROADMAP.md`) reflects the target release version.
- [ ] No PyPI tokens, passwords, or publishing credentials exist in repository secrets.
- [ ] Git tag `v0.3.0` does NOT already exist locally or remotely (`git tag -l`, `git ls-remote --tags origin`).
- [ ] Target version `0.3.0` is NOT already published on PyPI.
- [ ] Local quality suite passes cleanly (`pytest`, `ruff`, `mypy`, `build`, `twine`).

---

## 4. Publication Process (Release Gate)

> [!IMPORTANT]
> **Separate Review Gate**: Release publication occurs **only after** the release preparation PR has been merged into `main` and post-merge `main` CI is verified. Never tag or publish from unmerged branches.

1. Navigate to repository **Releases** on GitHub.
2. Click **Draft a new release**.
3. Configure the release:
   - **Target**: `main` (authoritative merge commit)
   - **Tag**: `v0.3.0` (must match exact lowercase `v<version>` syntax)
   - **Title**: `fa-redact v0.3.0`
   - **Description**: Copy release notes directly from `CHANGELOG.md` `[0.3.0]` section.
4. Click **Publish release**.
5. The `.github/workflows/release.yml` workflow will trigger automatically.

---

## 5. Post-Release Verification Checklist

- [ ] GitHub `Release` workflow completes successfully (`build` and `publish-pypi` jobs).
- [ ] Target release is live on PyPI at `https://pypi.org/project/fa-redact/0.3.0/`.
- [ ] Both binary wheel (`.whl`) and source distribution (`.tar.gz`) are visible on PyPI.
- [ ] Clean installation from PyPI works in a fresh isolated environment:
  ```bash
  pip install fa-redact
  ```
- [ ] Public API verification in clean environment:
  ```python
  import fa_redact

  assert fa_redact.__version__ == "0.3.0"
  assert callable(fa_redact.detect)
  assert callable(fa_redact.redact)
  assert callable(fa_redact.detection_report)
  assert callable(fa_redact.detect_fields)
  assert callable(fa_redact.redact_fields)
  assert callable(fa_redact.report_fields)
  assert callable(fa_redact.clinical_profile)
  ```
- [ ] Update `PROJECT_STATUS.md` to reflect `v0.3.0` as the latest published release.
