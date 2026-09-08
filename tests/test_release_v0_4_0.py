"""Tests for fa-redact v0.4.0 Release Preparation (Phase 34).

Verifies:
1. Runtime and pyproject.toml package version alignment (0.4.0).
2. Base package dependencies remain strictly empty (`dependencies = []`).
3. README.md source-tree version reflects v0.4.0 in English and Persian headers.
4. CHANGELOG.md contains finalized `[0.4.0] - 2026-09-08` and `[Unreleased]`.
5. Release workflow (`release.yml`) distribution audits include ONNX detector.
6. Isolated import safety of `ONNXPersianNERDetector` without ML runtimes.
7. ROADMAP.md records Phase 32 and 33 COMPLETED, Phase 34 ACTIVE, no Phase 35.
8. PROJECT_STATUS.md lists published release as v0.3.0 and source as 0.4.0.
9. RELEASING.md reflects target release v0.4.0.
"""

from __future__ import annotations

import sys
from pathlib import Path

import fa_redact

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_package_version_and_pyproject_version() -> None:
    """Verify runtime package version and pyproject.toml version match 0.4.0."""
    assert fa_redact.__version__ == "0.4.0"

    pyproject_path = REPO_ROOT / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")
    assert 'version = "0.4.0"' in content
    assert "dependencies = []" in content


def test_readme_source_tree_version() -> None:
    """Verify README.md reflects v0.4.0 in both English and Persian sections."""
    readme_path = REPO_ROOT / "README.md"
    content = readme_path.read_text(encoding="utf-8")

    assert "Package version in this source tree: `v0.4.0`" in content
    assert "نسخه بسته در این درخت منبع: `v0.4.0`" in content


def test_changelog_v0_4_0_and_unreleased() -> None:
    """Verify CHANGELOG.md contains fresh [Unreleased] and [0.4.0] section."""
    changelog_path = REPO_ROOT / "CHANGELOG.md"
    content = changelog_path.read_text(encoding="utf-8")

    assert "## [Unreleased]" in content
    assert "## [0.4.0] - 2026-09-08" in content
    assert "## [0.3.0] - 2026-09-07" in content

    unreleased_idx = content.find("## [Unreleased]")
    v040_idx = content.find("## [0.4.0] - 2026-09-08")
    assert unreleased_idx != -1
    assert v040_idx != -1
    assert unreleased_idx < v040_idx


def test_release_workflow_packaging_audits() -> None:
    """Verify release.yml audits include onnx_persian_ner.py and _ner_utils.py."""
    release_yml_path = REPO_ROOT / ".github" / "workflows" / "release.yml"
    content = release_yml_path.read_text(encoding="utf-8")

    assert "'fa_redact/detectors/_ner_utils.py'" in content
    assert "'fa_redact/detectors/onnx_persian_ner.py'" in content
    assert "'src/fa_redact/detectors/_ner_utils.py'" in content
    assert "'src/fa_redact/detectors/onnx_persian_ner.py'" in content

    # Check smoke test assertions
    assert "assert fa_redact.ONNXPersianNERDetector is not None" in content
    assert 'assert "onnxruntime" not in sys.modules' in content


def test_top_level_import_safety_without_ml_runtimes() -> None:
    """Verify importing top-level package symbols does not pull in ML runtimes."""
    assert fa_redact.ONNXPersianNERDetector is not None
    assert fa_redact.PersianNERDetector is not None
    assert fa_redact.IranianLegalEntityIDDetector is not None
    assert callable(fa_redact.is_valid_iranian_legal_entity_id)
    assert callable(fa_redact.detect)
    assert callable(fa_redact.redact)
    assert callable(fa_redact.detect_many)
    assert callable(fa_redact.redact_many)
    assert callable(fa_redact.report_many)
    assert callable(fa_redact.detection_to_dict)
    assert callable(fa_redact.dumps_detections)
    assert callable(fa_redact.clinical_profile)

    # Verify no heavy ML runtimes were imported
    assert "onnxruntime" not in sys.modules
    assert "torch" not in sys.modules
    assert "transformers" not in sys.modules


def test_roadmap_phase_statuses_and_no_phase_35() -> None:
    """Verify ROADMAP.md has Phase 32 & 33 COMPLETED, Phase 34 ACTIVE."""
    roadmap_path = REPO_ROOT / "ROADMAP.md"
    content = roadmap_path.read_text(encoding="utf-8")

    p32 = (
        "### Phase 32 — Persian NER Backend Validation & Production Readiness Gate\n"
        "*Status: `COMPLETED`*"
    )
    p33 = (
        "### Phase 33 — Performance Profiling & Evidence-Based Optimization\n"
        "*Status: `COMPLETED`*"
    )
    p34 = (
        "### Phase 34 — v0.4.0 Release Preparation\n"
        "*Status: `ACTIVE / RELEASE PREPARATION`*"
    )
    assert p32 in content
    assert p33 in content
    assert p34 in content
    assert "Feature Freeze & Feedback Period" in content
    assert "Phase 35" not in content


def test_project_status_invariants() -> None:
    """Verify PROJECT_STATUS.md lists v0.3.0 as published and 0.4.0 as source."""
    status_path = REPO_ROOT / "PROJECT_STATUS.md"
    content = status_path.read_text(encoding="utf-8")

    closed_phase = (
        "- **Last closed phase:** Phase 33 — "
        "Performance Profiling & Evidence-Based Optimization"
    )
    active_phase = "- **Current active phase:** Phase 34 — v0.4.0 Release Preparation"

    assert "- **Latest published release:** `v0.3.0`" in content
    assert "- **Current source version:** `0.4.0`" in content
    assert closed_phase in content
    assert active_phase in content


def test_releasing_guide_v0_4_0() -> None:
    """Verify RELEASING.md reflects target version 0.4.0 and tag v0.4.0."""
    releasing_path = REPO_ROOT / "RELEASING.md"
    content = releasing_path.read_text(encoding="utf-8")

    assert "tag vX.Y.Z, e.g. v0.4.0" in content
    assert "Target version `0.4.0`" in content
    assert "Git tag `v0.4.0`" in content
    assert "https://pypi.org/project/fa-redact/0.4.0/" in content
