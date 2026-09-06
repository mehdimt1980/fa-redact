"""Unit and integration tests for BankCardDetector."""

from __future__ import annotations

import pytest

from fa_redact import (
    BankCardDetector,
    Detector,
    normalize_text,
)

_VALID_ASCII = "1234567890123452"
_VALID_PERSIAN = "۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۲"
_VALID_ARABIC_INDIC = "١٢٣٤٥٦٧٨٩٠١٢٣٤٥٢"
_VALID_SECOND = "5022291234567897"


class TestBankCardDetectorUnit:
    """Direct unit tests for BankCardDetector."""

    def test_protocol_conformance(self) -> None:
        """Verify BankCardDetector satisfies the Detector protocol."""
        detector: Detector = BankCardDetector()
        assert callable(detector.detect)

    def test_basic_ascii_detection(self) -> None:
        """Verify detection of a valid ASCII card number in Persian prose."""
        detector = BankCardDetector()
        text = f"شماره کارت جهت واریز: {_VALID_ASCII} است."
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 1
        d = detections[0]
        assert d.type == "BANK_CARD"
        assert d.value == _VALID_ASCII
        assert d.normalized_value == _VALID_ASCII
        assert d.start == text.index(_VALID_ASCII)
        assert d.end == d.start + len(_VALID_ASCII)
        assert text[d.start : d.end] == _VALID_ASCII

    def test_persian_digit_detection_and_representation(self) -> None:
        """Verify Persian card preserves raw Persian value and ASCII normalized."""
        detector = BankCardDetector()
        text = f"کارت: {_VALID_PERSIAN} ثبت شد."
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 1
        d = detections[0]
        assert d.type == "BANK_CARD"
        assert d.value == _VALID_PERSIAN
        assert d.normalized_value == _VALID_ASCII
        assert text[d.start : d.end] == _VALID_PERSIAN

    def test_arabic_indic_digit_detection(self) -> None:
        """Verify Arabic-Indic digit card detection."""
        detector = BankCardDetector()
        text = f"کارت بانکی: {_VALID_ARABIC_INDIC}"
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 1
        d = detections[0]
        assert d.type == "BANK_CARD"
        assert d.value == _VALID_ARABIC_INDIC
        assert d.normalized_value == _VALID_ASCII
        assert text[d.start : d.end] == _VALID_ARABIC_INDIC

    def test_multiple_cards_source_order(self) -> None:
        """Verify multiple cards are detected in source text order."""
        detector = BankCardDetector()
        text = f"کارت ۱: {_VALID_ASCII} و کارت ۲: {_VALID_SECOND}"
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 2
        assert detections[0].value == _VALID_ASCII
        assert detections[1].value == _VALID_SECOND
        assert detections[0].start < detections[1].start

    def test_surrounding_punctuation_boundaries(self) -> None:
        """Verify punctuation boundaries around card candidates."""
        detector = BankCardDetector()
        cases = [
            (f"({_VALID_ASCII})", _VALID_ASCII),
            (f"[{_VALID_ASCII}]", _VALID_ASCII),
            (f"کارت: {_VALID_ASCII}.", _VALID_ASCII),
            (f"کارت: {_VALID_ASCII},", _VALID_ASCII),
            (f"کارت: {_VALID_ASCII};", _VALID_ASCII),
            (f"کارت={_VALID_ASCII}", _VALID_ASCII),
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
        """Verify candidates embedded in larger numeric tokens are ignored."""
        detector = BankCardDetector()
        cases = [
            f"0{_VALID_ASCII}",  # 17 digits, preceded by digit
            f"{_VALID_ASCII}0",  # 17 digits, followed by digit
            f"9{_VALID_ASCII}9",  # 18 digits, surrounded by digits
            f"1{_VALID_ASCII}1",  # 18 digits, surrounded by digits
        ]

        for text in cases:
            norm = normalize_text(text)
            detections = detector.detect(text, norm)
            assert len(detections) == 0, f"Expected 0 detections for '{text}'"

    def test_checksum_invalid_candidate_ignored(self) -> None:
        """Verify candidate with invalid Luhn checksum is ignored."""
        detector = BankCardDetector()
        # Mutated last digit: 3 instead of 2
        text = "شماره کارت: 1234567890123453"
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 0

    def test_all_identical_candidate_ignored(self) -> None:
        """Verify all-identical candidate is ignored."""
        detector = BankCardDetector()
        text = "شماره کارت: 0000000000000000 و 1111111111111111"
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 0

    def test_multiline_synthetic_clinical_billing_prose(self) -> None:
        """Verify extraction in multiline synthetic hospital billing notes."""
        detector = BankCardDetector()
        text = (
            "رسید تراکنش بیمارستانی\n"
            f"کارت مبدا: {_VALID_ASCII}\n"
            f"کارت مقصد: {_VALID_SECOND}\n"
            "پرداخت تایید شد."
        )
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 2
        assert detections[0].value == _VALID_ASCII
        assert detections[1].value == _VALID_SECOND

    def test_length_mismatch_raises_value_error(self) -> None:
        """Verify ValueError is raised when text lengths differ."""
        detector = BankCardDetector()
        with pytest.raises(ValueError, match="length"):
            detector.detect("short", "longer_normalized_string")
