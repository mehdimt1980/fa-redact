# Release Guide

This document outlines the release process and PyPI Trusted Publishing setup for `fa-redact`.

---

## Architecture Overview

`fa-redact` uses **GitHub Actions OIDC Trusted Publishing** to securely publish releases to PyPI without storing long-lived API tokens or passwords in repository secrets.

The release process follows this flow:
```text
GitHub Release published (e.g. tag v0.1.0)
        ↓
Trigger .github/workflows/release.yml
        ↓
Build sdist and wheel on Python 3.13
        ↓
Verify tag matches fa_redact.__version__
        ↓
Validate package metadata via twine
        ↓
Execute isolated wheel smoke test
        ↓
Upload distribution artifacts
        ↓
Publish job requests PyPI OIDC token (environment: pypi)
        ↓
pypa/gh-action-pypi-publish uploads to PyPI
```

---

## 1. PyPI Pending Trusted Publisher Setup

Before publishing the first release (`v0.1.0`), set up a **Pending Publisher** on PyPI:

1. Log in to your account on [pypi.org](https://pypi.org).
2. Go to **Account Settings** → **Publishing**.
3. Under **Add a publisher**, configure:
   - **PyPI Project Name**: `fa-redact`
   - **Owner**: `mehdimt1980`
   - **Repository Name**: `fa-redact`
   - **Workflow name**: `release.yml`
   - **Environment name**: `pypi`
4. Click **Add publisher**.

> [!IMPORTANT]
> **Name Reservation Notice**: Adding a Pending Publisher on PyPI links publishing credentials for the repository, but it does **not** reserve or lock the package name on PyPI until the first package release is successfully published.

---

## 2. GitHub Environment Configuration

Create the deployment environment in GitHub:

1. In the repository on GitHub, navigate to **Settings** → **Environments**.
2. Click **New environment** and enter the name: `pypi`.
3. *(Optional / Plan-dependent)*: If supported by your GitHub plan, configure deployment protection rules such as required reviewers or restricting deployments to release tags.

> [!NOTE]
> Do **NOT** add any PyPI API tokens or passwords to the repository or environment secrets. The `release.yml` workflow uses OpenID Connect (OIDC) authentication (`id-token: write`).

---

## 3. Pre-Release Checklist (Before Publication)

- [ ] `main` branch CI is completely green (`.github/workflows/ci.yml`).
- [ ] `.github/workflows/release.yml` is merged into `main`.
- [ ] Package version is set to `0.1.0` in `pyproject.toml` and `src/fa_redact/__init__.py`.
- [ ] `CHANGELOG.md` has an entry for `[0.1.0] - 2026-09-05`.
- [ ] PyPI name availability preflight confirmed (`fa-redact` is available).
- [ ] GitHub `pypi` environment is created in repository settings.
- [ ] PyPI Pending Trusted Publisher is configured with exact repository and workflow details.
- [ ] No PyPI tokens or publishing credentials exist in repository secrets.
- [ ] Release notes and documentation are reviewed.
- [ ] Git tag `v0.1.0` does not already exist locally or remotely.
- [ ] PyPI `fa-redact` `0.1.0` does not already exist.

---

## 4. Publication Process (Phase 10B)

1. Draft a new GitHub Release targeting `main`:
   - Tag: `v0.1.0`
   - Release Title: `fa-redact v0.1.0`
   - Description: Copy release notes from `CHANGELOG.md`.
2. Click **Publish release**.
3. The `.github/workflows/release.yml` workflow will trigger automatically.

---

## 5. Post-Release Verification Checklist

- [ ] GitHub `Release` workflow completes successfully (`build` and `publish-pypi` jobs).
- [ ] Project page is live at `https://pypi.org/project/fa-redact/0.1.0/`.
- [ ] Both binary wheel (`.whl`) and source distribution (`.tar.gz`) are visible on PyPI.
- [ ] Clean installation from PyPI works in a fresh environment:
  ```bash
  pip install fa-redact
  ```
- [ ] Public API verification in clean environment:
  ```python
  import fa_redact

  assert fa_redact.__version__ == "0.1.0"
  assert callable(fa_redact.detect)
  assert callable(fa_redact.redact)
  ```
