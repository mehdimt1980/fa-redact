"""Unit and integration tests for IranianIBANDetector."""

from __future__ import annotations

import pytest

from fa_redact import (
    Detector,
    IranianIBANDetector,
    normalize_text,
)

_VALID_ASCII = "IR641234567890123456789012"
_VALID_PERSIAN = "IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲"
_VALID_ARABIC_INDIC = "IR٦٤١٢٣٤٥٦٧٨٩٠١٢٣٤٥٦٧٨٩٠١٢"
_VALID_SECOND = "IR220000000000000000000001"


class TestIranianIBANDetectorUnit:
    """Direct unit tests for IranianIBANDetector."""

    def test_protocol_conformance(self) -> None:
        """Verify IranianIBANDetector satisfies the Detector protocol."""
        detector: Detector = IranianIBANDetector()
        assert callable(detector.detect)

    def test_basic_ascii_detection(self) -> None:
        """Verify detection of a valid ASCII IBAN in Persian prose."""
        detector = IranianIBANDetector()
        text = f"شماره شبا جهت واریز وجه: {_VALID_ASCII} می‌باشد."
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 1
        d = detections[0]
        assert d.type == "IR_IBAN"
        assert d.value == _VALID_ASCII
        assert d.normalized_value == _VALID_ASCII
        assert d.start == text.index(_VALID_ASCII)
        assert d.end == d.start + len(_VALID_ASCII)
        assert text[d.start : d.end] == _VALID_ASCII

    def test_persian_digit_detection_and_representation(self) -> None:
        """Verify Persian IBAN preserves raw value and ASCII normalized_value."""
        detector = IranianIBANDetector()
        text = f"شبا: {_VALID_PERSIAN} ثبت شد."
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 1
        d = detections[0]
        assert d.type == "IR_IBAN"
        assert d.value == _VALID_PERSIAN
        assert d.normalized_value == _VALID_ASCII
        assert text[d.start : d.end] == _VALID_PERSIAN

    def test_arabic_indic_digit_detection(self) -> None:
        """Verify Arabic-Indic digit IBAN detection."""
        detector = IranianIBANDetector()
        text = f"حساب: {_VALID_ARABIC_INDIC}"
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 1
        d = detections[0]
        assert d.type == "IR_IBAN"
        assert d.value == _VALID_ARABIC_INDIC
        assert d.normalized_value == _VALID_ASCII
        assert text[d.start : d.end] == _VALID_ARABIC_INDIC

    def test_multiple_ibans_source_order(self) -> None:
        """Verify multiple IBANs are detected in source text order."""
        detector = IranianIBANDetector()
        text = f"شبا ۱: {_VALID_ASCII} و شبا ۲: {_VALID_SECOND}"
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 2
        assert detections[0].value == _VALID_ASCII
        assert detections[1].value == _VALID_SECOND
        assert detections[0].start < detections[1].start

    def test_surrounding_punctuation_boundaries(self) -> None:
        """Verify punctuation boundaries around IBAN candidates."""
        detector = IranianIBANDetector()
        cases = [
            (f"({_VALID_ASCII})", _VALID_ASCII),
            (f"[{_VALID_ASCII}]", _VALID_ASCII),
            (f"شبا: {_VALID_ASCII}.", _VALID_ASCII),
            (f"شبا: {_VALID_ASCII},", _VALID_ASCII),
            (f"شبا: {_VALID_ASCII};", _VALID_ASCII),
            (f"شبا={_VALID_ASCII}", _VALID_ASCII),
            (f'"{_VALID_ASCII}"', _VALID_ASCII),
            (f"'{_VALID_ASCII}'", _VALID_ASCII),
            (f"«{_VALID_PERSIAN}»", _VALID_PERSIAN),
        ]

        for text, expected in cases:
            norm = normalize_text(text)
            detections = detector.detect(text, norm)
            assert len(detections) == 1
            assert detections[0].value == expected
            assert text[detections[0].start : detections[0].end] == expected

    def test_embedded_tokens_rejected(self) -> None:
        """Verify candidates embedded inside larger alphanumeric tokens are ignored."""
        detector = IranianIBANDetector()
        cases = [
            f"X{_VALID_ASCII}",  # Preceded by letter
            f"{_VALID_ASCII}X",  # Followed by letter
            f"_{_VALID_ASCII}",  # Preceded by underscore
            f"{_VALID_ASCII}_",  # Followed by underscore
            f"1{_VALID_ASCII}",  # Preceded by digit
            f"{_VALID_ASCII}1",  # Followed by digit
            f"شبا{_VALID_ASCII}",  # Preceded by Persian letter without boundary
            f"{_VALID_ASCII}ریال",  # Followed by Persian letter without boundary
        ]

        for text in cases:
            norm = normalize_text(text)
            detections = detector.detect(text, norm)
            assert len(detections) == 0, f"Expected 0 detections for '{text}'"

    def test_lowercase_ir_ignored(self) -> None:
        """Verify lowercase 'ir' prefix is ignored."""
        detector = IranianIBANDetector()
        text = "شماره شبا: ir641234567890123456789012"
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 0

    def test_checksum_invalid_candidate_ignored(self) -> None:
        """Verify candidate with invalid checksum is ignored."""
        detector = IranianIBANDetector()
        # Mutated last digit: 3 instead of 2
        text = "شماره شبا: IR641234567890123456789013"
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 0

    def test_multiline_synthetic_clinical_billing_prose(self) -> None:
        """Verify extraction in multiline synthetic hospital billing notes."""
        detector = IranianIBANDetector()
        text = (
            "صورتحساب خدمات بالینی\n"
            f"شماره شبا بیمارستان: {_VALID_ASCII}\n"
            f"شبا پشتیبان: {_VALID_SECOND}\n"
            "پایان صورتحساب."
        )
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 2
        assert detections[0].value == _VALID_ASCII
        assert detections[1].value == _VALID_SECOND

    def test_length_mismatch_raises_value_error(self) -> None:
        """Verify ValueError is raised when text lengths differ."""
        detector = IranianIBANDetector()
        with pytest.raises(ValueError, match="length"):
            detector.detect("short", "longer_normalized_string")
