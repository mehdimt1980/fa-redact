"""Minimal package tests for fa-redact foundation."""

import fa_redact


def test_package_import_and_version() -> None:
    """Verify that the package imports successfully and exposes version 0.2.0."""
    assert hasattr(fa_redact, "__version__")
    assert fa_redact.__version__ == "0.2.0"
    assert isinstance(fa_redact.__version__, str)


def test_version_consistency() -> None:
    """Verify consistency between pyproject.toml, metadata, and __version__."""
    import re
    from pathlib import Path

    assert fa_redact.__version__ == "0.2.0"

    # 1. Check pyproject.toml version
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', content)
        assert match is not None, "Version not found in pyproject.toml"
        assert match.group(1) == fa_redact.__version__

    # 2. Check importlib.metadata if package is installed in environment
    try:
        import importlib.metadata

        installed_ver = importlib.metadata.version("fa-redact")
        assert installed_ver == fa_redact.__version__
    except importlib.metadata.PackageNotFoundError:
        pass


def test_package_all_export() -> None:
    """Verify that __all__ exports all expected public symbols."""
    expected_exports = {
        "__version__",
        "BankCardDetector",
        "ConflictPolicy",
        "Detection",
        "DetectionReport",
        "Detector",
        "EmailDetector",
        "IranianIBANDetector",
        "IranianMobileNumberDetector",
        "IranianNationalIDDetector",
        "PatternDetector",
        "PatternRule",
        "PersianNERDetector",
        "PseudonymizationSession",
        "detect",
        "detect_fields",
        "detection_report",
        "is_valid_bank_card_number",
        "is_valid_email",
        "is_valid_iranian_iban",
        "is_valid_mobile_number",
        "is_valid_national_id",
        "normalize_digits",
        "normalize_letters",
        "normalize_text",
        "redact",
        "redact_fields",
        "report_detections",
        "report_fields",
        "resolve_detection_conflicts",
    }
    assert expected_exports.issubset(set(fa_redact.__all__))
    for name in expected_exports:
        assert hasattr(fa_redact, name)


def test_pipeline_and_protocols_imports() -> None:
    """Verify direct imports from core submodules."""
    from fa_redact.conflicts import (
        ConflictPolicy as SubConflictPolicy,
    )
    from fa_redact.conflicts import (
        resolve_detection_conflicts as sub_resolve,
    )
    from fa_redact.pipeline import detect as sub_detect
    from fa_redact.protocols import Detector as SubDetector
    from fa_redact.pseudonymization import (
        PseudonymizationSession as SubSession,
    )
    from fa_redact.redaction import redact as sub_redact
    from fa_redact.reporting import (
        DetectionReport as SubReport,
    )
    from fa_redact.reporting import (
        detection_report as sub_detection_report,
    )
    from fa_redact.reporting import (
        report_detections as sub_report_detections,
    )
    from fa_redact.structured import (
        detect_fields as sub_detect_fields,
    )
    from fa_redact.structured import (
        redact_fields as sub_redact_fields,
    )
    from fa_redact.structured import (
        report_fields as sub_report_fields,
    )

    assert callable(sub_detect)
    assert callable(sub_redact)
    assert callable(sub_resolve)
    assert callable(sub_detection_report)
    assert callable(sub_report_detections)
    assert callable(sub_detect_fields)
    assert callable(sub_redact_fields)
    assert callable(sub_report_fields)
    assert SubReport is not None
    assert SubSession is not None
    assert SubDetector is not None
    assert SubConflictPolicy is not None


def test_subpackage_imports() -> None:
    """Verify direct imports from validators and detectors subpackages."""
    from fa_redact.detectors import (
        BankCardDetector as SubBankCardDetector,
    )
    from fa_redact.detectors import (
        EmailDetector as SubEmailDetector,
    )
    from fa_redact.detectors import (
        IranianIBANDetector as SubIbanDetector,
    )
    from fa_redact.detectors import (
        IranianMobileNumberDetector as SubMobileDetector,
    )
    from fa_redact.detectors import (
        IranianNationalIDDetector as SubNidDetector,
    )
    from fa_redact.detectors import (
        PatternDetector as SubPatternDetector,
    )
    from fa_redact.detectors import (
        PatternRule as SubPatternRule,
    )
    from fa_redact.detectors import (
        PersianNERDetector as SubPersianNERDetector,
    )
    from fa_redact.validators import (
        is_valid_bank_card_number as sub_card_val,
    )
    from fa_redact.validators import (
        is_valid_email as sub_email_val,
    )
    from fa_redact.validators import (
        is_valid_iranian_iban as sub_iban_val,
    )
    from fa_redact.validators import (
        is_valid_mobile_number as sub_mobile_val,
    )
    from fa_redact.validators import (
        is_valid_national_id as sub_nid_val,
    )

    assert callable(sub_card_val)
    assert callable(sub_email_val)
    assert callable(sub_iban_val)
    assert callable(sub_mobile_val)
    assert callable(sub_nid_val)
    assert SubBankCardDetector is not None
    assert SubEmailDetector is not None
    assert SubIbanDetector is not None
    assert SubMobileDetector is not None
    assert SubNidDetector is not None
    assert SubPatternDetector is not None
    assert SubPatternRule is not None
    assert SubPersianNERDetector is not None


def test_cli_import_and_scripts() -> None:
    """Verify CLI module import and entry point script configuration."""
    import re
    from pathlib import Path

    from fa_redact.cli import main as cli_main

    assert callable(cli_main)

    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text(encoding="utf-8")
        assert "[project.scripts]" in content
        match = re.search(r'(?m)^fa-redact\s*=\s*"([^"]+)"', content)
        assert match is not None, "fa-redact script not found in pyproject.toml"
        assert match.group(1) == "fa_redact.cli:main"


def test_pyproject_dependencies_and_extras() -> None:
    """Verify base package has zero mandatory dependencies and optional ner extra."""
    import re
    from pathlib import Path

    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text(encoding="utf-8")
        # Check dependencies = []
        dep_match = re.search(r"(?m)^dependencies\s*=\s*\[\s*\]", content)
        assert dep_match is not None, "Core dependencies must be empty list []"

        # Check optional-dependencies contain ner
        assert "[project.optional-dependencies]" in content
        assert "ner = [" in content
        assert "torch" in content
        assert "transformers" in content
