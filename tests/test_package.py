"""Minimal package tests for fa-redact foundation."""

import fa_redact


def test_package_import_and_version() -> None:
    """Verify that the package imports successfully and exposes version 0.1.0."""
    assert hasattr(fa_redact, "__version__")
    assert fa_redact.__version__ == "0.1.0"
    assert isinstance(fa_redact.__version__, str)


def test_package_all_export() -> None:
    """Verify that __all__ exports all expected public symbols."""
    expected_exports = {
        "__version__",
        "BankCardDetector",
        "Detection",
        "Detector",
        "EmailDetector",
        "IranianIBANDetector",
        "IranianMobileNumberDetector",
        "IranianNationalIDDetector",
        "PseudonymizationSession",
        "detect",
        "is_valid_bank_card_number",
        "is_valid_email",
        "is_valid_iranian_iban",
        "is_valid_mobile_number",
        "is_valid_national_id",
        "normalize_digits",
        "normalize_letters",
        "normalize_text",
        "redact",
    }
    assert expected_exports.issubset(set(fa_redact.__all__))
    for name in expected_exports:
        assert hasattr(fa_redact, name)


def test_pipeline_and_protocols_imports() -> None:
    """Verify direct imports from core submodules."""
    from fa_redact.pipeline import detect as sub_detect
    from fa_redact.protocols import Detector as SubDetector
    from fa_redact.pseudonymization import (
        PseudonymizationSession as SubSession,
    )
    from fa_redact.redaction import redact as sub_redact

    assert callable(sub_detect)
    assert callable(sub_redact)
    assert SubSession is not None
    assert SubDetector is not None


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
