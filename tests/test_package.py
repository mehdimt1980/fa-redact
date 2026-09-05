"""Minimal package tests for fa-redact foundation (Phase 1)."""

import fa_redact


def test_package_import_and_version() -> None:
    """Verify that the package imports successfully and exposes version 0.1.0."""
    assert hasattr(fa_redact, "__version__")
    assert fa_redact.__version__ == "0.1.0"
    assert isinstance(fa_redact.__version__, str)


def test_package_all_export() -> None:
    """Verify that __all__ exports __version__ and normalization functions."""
    expected_exports = {
        "__version__",
        "normalize_digits",
        "normalize_letters",
        "normalize_text",
    }
    assert expected_exports.issubset(set(fa_redact.__all__))
    for name in expected_exports:
        assert hasattr(fa_redact, name)
