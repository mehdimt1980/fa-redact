"""Tests for Iranian Legal Entity National ID detector."""

from __future__ import annotations

import pytest
from research.legal_entity_id_reference import (
    compute_legal_entity_checksum_variant_a,
)

from fa_redact.detectors.legal_entity_id import IranianLegalEntityIDDetector
from fa_redact.normalization import normalize_text


def _make_synthetic_legal_id(prefix_10: str) -> str:
    """Deterministic test-only fixture generator."""
    check = compute_legal_entity_checksum_variant_a(prefix_10)
    return f"{prefix_10}{check}"


def _to_persian_digits(ascii_str: str) -> str:
    return "".join(chr(0x06F0 + int(c)) if c.isdigit() else c for c in ascii_str)


def _to_arabic_indic_digits(ascii_str: str) -> str:
    return "".join(chr(0x0660 + int(c)) if c.isdigit() else c for c in ascii_str)


_SYNTH_PREFIX_1 = "1400000001"
_SYNTH_PREFIX_2 = "1026000001"


class TestIranianLegalEntityIDDetector:
    """Comprehensive test suite for IranianLegalEntityIDDetector."""

    def test_detects_valid_ascii_candidate(self) -> None:
        """1. Detects valid ASCII candidate in text."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        text = f"شناسه ملی شرکت {synth_id} می‌باشد."
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 1
        d = detections[0]
        assert d.type == "IR_LEGAL_ENTITY_ID"
        assert d.value == synth_id
        assert d.normalized_value == synth_id

    def test_detects_persian_digits(self) -> None:
        """2. Detects Persian digits candidate in text."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        persian_val = _to_persian_digits(synth_id)
        text = f"شماره شناسه: {persian_val}"
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 1
        d = detections[0]
        assert d.type == "IR_LEGAL_ENTITY_ID"
        assert d.value == persian_val
        assert d.normalized_value == synth_id

    def test_detects_arabic_indic_digits(self) -> None:
        """3. Detects Arabic-Indic digits candidate in text."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        arabic_val = _to_arabic_indic_digits(synth_id)
        text = f"شناسه: {arabic_val}"
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 1
        d = detections[0]
        assert d.type == "IR_LEGAL_ENTITY_ID"
        assert d.value == arabic_val
        assert d.normalized_value == synth_id

    def test_detects_mixed_digit_scripts(self) -> None:
        """4. Detects mixed Persian/Arabic/ASCII digit strings."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        mixed_val = (
            synth_id[:4]
            + _to_persian_digits(synth_id[4:7])
            + _to_arabic_indic_digits(synth_id[7:])
        )
        text = f"کد: {mixed_val}"
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 1
        d = detections[0]
        assert d.type == "IR_LEGAL_ENTITY_ID"
        assert d.value == mixed_val
        assert d.normalized_value == synth_id

    def test_raw_and_normalized_values_preserved(self) -> None:
        """5-6. Raw value preserves exact source form; normalized is ASCII."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        raw_val = _to_persian_digits(synth_id)
        text = f"صورت‌حساب به نام شرکت با شناسه {raw_val} صادر شد."
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 1
        d = detections[0]
        assert d.value == raw_val
        assert d.normalized_value == synth_id
        assert d.normalized_value.isascii()

    def test_exact_character_offsets(self) -> None:
        """7-8. Start and end offsets index exactly into original text."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        text = f"پیشوند {synth_id} پسوند"
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 1
        d = detections[0]
        assert d.start == 7
        assert d.end == 7 + 11
        assert text[d.start : d.end] == synth_id

    def test_multiple_candidates_preserve_order(self) -> None:
        """9. Multiple distinct candidates are emitted in textual order."""
        detector = IranianLegalEntityIDDetector()
        id1 = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        id2 = _make_synthetic_legal_id(_SYNTH_PREFIX_2)
        text = f"شرکت الف {id1} و شرکت ب {id2} ثبت شده‌اند."
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 2
        assert detections[0].value == id1
        assert detections[1].value == id2
        assert detections[0].start < detections[1].start

    def test_repeated_candidate_emits_repeated_evidence(self) -> None:
        """10. Repeated occurrences of the same identifier emit distinct detections."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        text = f"شناسه {synth_id} مجدداً {synth_id}"
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 2
        assert detections[0].start < detections[1].start
        assert detections[0].value == detections[1].value == synth_id

    def test_invalid_checksum_ignored(self) -> None:
        """11. 11-digit numbers with invalid checksums are silently ignored."""
        detector = IranianLegalEntityIDDetector()
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        correct_check = int(base_id[-1])
        wrong_check = (correct_check + 1) % 10
        invalid_candidate = f"{base_id[:-1]}{wrong_check}"
        text = f"شماره پیگیری نامعتبر {invalid_candidate}"
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 0

    def test_all_identical_digits_ignored(self) -> None:
        """12. 11-digit all-identical numbers are ignored."""
        detector = IranianLegalEntityIDDetector()
        for d in range(10):
            repeated = str(d) * 11
            text = f"کد فرضی {repeated}"
            normalized = normalize_text(text)
            assert len(detector.detect(text, normalized)) == 0

    def test_embedded_inside_longer_numeric_sequence_ignored(self) -> None:
        """13. 11-digit sequences embedded in longer numbers are ignored."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        text = f"شماره طولانی 9{synth_id}5"
        normalized = normalize_text(text)
        assert len(detector.detect(text, normalized)) == 0

    def test_left_and_right_numeric_boundaries(self) -> None:
        """14-15. Strict numeric lookbehind and lookahead boundaries enforced."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        left_touch = f"0{synth_id}"
        right_touch = f"{synth_id}0"
        assert len(detector.detect(left_touch, normalize_text(left_touch))) == 0
        assert len(detector.detect(right_touch, normalize_text(right_touch))) == 0

    def test_punctuation_boundaries_accepted(self) -> None:
        """16. Punctuation adjacent to candidate is accepted."""
        detector = IranianLegalEntityIDDetector()
        id1 = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        id2 = _make_synthetic_legal_id(_SYNTH_PREFIX_2)
        text = f"({id1}), [{id2}]!"
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 2
        assert detections[0].value == id1
        assert detections[1].value == id2

    def test_persian_prose_boundaries_accepted(self) -> None:
        """17. Persian letters adjacent to whitespace are accepted."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        text = f"شناسه:{synth_id}است."
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 1
        assert detections[0].value == synth_id

    def test_adjacent_non_digit_characters_accepted(self) -> None:
        """18. Non-digit delimiters like quotes and brackets are accepted."""
        detector = IranianLegalEntityIDDetector()
        id1 = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        id2 = _make_synthetic_legal_id(_SYNTH_PREFIX_2)
        text = f'"{id1}" / <{id2}>'
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 2

    def test_length_mismatch_raises_value_error(self) -> None:
        """19. Length mismatch between original and normalized raises ValueError."""
        detector = IranianLegalEntityIDDetector()
        with pytest.raises(ValueError, match=r"original_text length \(10\) must equal"):
            detector.detect("1234567890", "12345678901")

    def test_mismatch_error_reveals_lengths_only(self) -> None:
        """20. Mismatch error message contains lengths only, no source text."""
        detector = IranianLegalEntityIDDetector()
        secret_text = "SECRET_DATA_123"
        try:
            detector.detect(secret_text, "SHORT")
        except ValueError as exc:
            msg = str(exc)
            assert "SECRET" not in msg
            assert "DATA" not in msg
            assert "15" in msg
            assert "5" in msg

    def test_entity_type_exact_ir_legal_entity_id(self) -> None:
        """21. Emits exact canonical entity type IR_LEGAL_ENTITY_ID."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        text = synth_id
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)
        assert len(detections) == 1
        assert detections[0].type == "IR_LEGAL_ENTITY_ID"

    def test_empty_input(self) -> None:
        """22. Empty input returns empty list."""
        detector = IranianLegalEntityIDDetector()
        assert detector.detect("", "") == []

    def test_no_false_match_for_10_digit_code_melli(self) -> None:
        """23. 10-digit National IDs are not matched as 11-digit Legal Entity IDs."""
        detector = IranianLegalEntityIDDetector()
        text = "کد ملی شخص حقیقی 0012345679 می‌باشد."
        normalized = normalize_text(text)
        assert len(detector.detect(text, normalized)) == 0

    def test_no_false_match_for_16_digit_bank_card(self) -> None:
        """24. 16-digit Bank Cards are not matched."""
        detector = IranianLegalEntityIDDetector()
        text = "شماره کارت 6037991122334455 است."
        normalized = normalize_text(text)
        assert len(detector.detect(text, normalized)) == 0

    def test_no_false_match_for_iban(self) -> None:
        """25. Iranian IBANs are not matched."""
        detector = IranianLegalEntityIDDetector()
        text = "شماره شبا IR641234567890123456789012 است."
        normalized = normalize_text(text)
        assert len(detector.detect(text, normalized)) == 0

    def test_detector_uses_validator_behavior(self) -> None:
        """26. Detector output strictly aligns with validator output."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        correct_check = int(synth_id[-1])
        wrong_check = (correct_check + 1) % 10
        invalid_id = f"{synth_id[:-1]}{wrong_check}"
        text = f"{synth_id} {invalid_id}"
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)
        assert len(detections) == 1
        assert detections[0].value == synth_id

    def test_deterministic_results(self) -> None:
        """27. Multiple detection calls produce identical results."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        text = f"متن با شناسه {synth_id}"
        normalized = normalize_text(text)
        d1 = detector.detect(text, normalized)
        d2 = detector.detect(text, normalized)
        assert d1 == d2

    def test_source_offsets_preserved_after_persian_digit_normalization(self) -> None:
        """28. Offsets accurately slice original Persian text."""
        detector = IranianLegalEntityIDDetector()
        synth_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        persian_id = _to_persian_digits(synth_id)
        prefix = "شرکت ثبت شده: "
        suffix = " پایان متن"
        text = f"{prefix}{persian_id}{suffix}"
        normalized = normalize_text(text)
        detections = detector.detect(text, normalized)

        assert len(detections) == 1
        d = detections[0]
        assert d.start == len(prefix)
        assert d.end == len(prefix) + len(persian_id)
        assert text[d.start : d.end] == persian_id
