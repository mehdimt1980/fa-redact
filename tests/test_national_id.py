"""Tests for Iranian National ID validation and detection (Phase 4)."""

import pytest

from fa_redact import (
    IranianNationalIDDetector,
    is_valid_national_id,
    normalize_text,
)

# --- Validator Tests ---


def test_validator_valid_synthetic_ascii() -> None:
    """Verify checksum-valid test vectors pass validation."""
    valid_test_vectors = [
        "1234567891",  # 210 % 11 = 1 -> check digit 1
        "0012345679",  # 112 % 11 = 2 -> 11 - 2 = 9
        "0490784526",  # 225 % 11 = 5 -> 11 - 5 = 6
        "7731689956",  # 313 % 11 = 5 -> 11 - 5 = 6
        "0080000002",  # 64 % 11 = 9 -> 11 - 9 = 2
    ]
    for nid in valid_test_vectors:
        assert is_valid_national_id(nid) is True, f"Failed for valid ID: {nid}"


def test_validator_persian_digits() -> None:
    """Verify Persian digit representation of valid IDs."""
    assert is_valid_national_id("۱۲۳۴۵۶۷۸۹۱") is True
    assert is_valid_national_id("۰۰۱۲۳۴۵۶۷۹") is True


def test_validator_arabic_indic_digits() -> None:
    """Verify Arabic-Indic digit representation of valid IDs."""
    assert is_valid_national_id("١٢٣٤٥٦٧٨٩١") is True
    assert is_valid_national_id("٠٠١٢٣٤٥٦٧٩") is True


def test_validator_mixed_digit_sets() -> None:
    """Verify mixed Persian, Arabic-Indic, and ASCII representations."""
    assert is_valid_national_id("۱۲3٤۵6۷8۹1") is True


def test_validator_incorrect_check_digit() -> None:
    """Verify corrupted check digits fail validation."""
    assert is_valid_national_id("1234567890") is False
    assert is_valid_national_id("1234567892") is False
    assert is_valid_national_id("0012345678") is False


def test_validator_repeated_digits_rejected() -> None:
    """Verify all 10 repeated-digit pseudo-values are rejected."""
    for d in range(10):
        nid_ascii = str(d) * 10
        assert is_valid_national_id(nid_ascii) is False, f"Accepted: {nid_ascii}"

    # Also in Persian digits
    assert is_valid_national_id("۰۰۰۰۰۰۰۰۰۰") is False
    assert is_valid_national_id("۱۱۱۱۱۱۱۱۱۱") is False


def test_validator_invalid_lengths() -> None:
    """Verify invalid lengths are strictly rejected without zero-padding."""
    assert is_valid_national_id("") is False
    assert is_valid_national_id("1") is False
    assert is_valid_national_id("12345678") is False  # 8 digits
    assert is_valid_national_id("123456789") is False  # 9 digits
    assert is_valid_national_id("01234567891") is False  # 11 digits
    assert is_valid_national_id("123456789012") is False  # 12 digits


def test_validator_separators_and_whitespace_rejected() -> None:
    """Verify strings with separators or whitespace are strictly rejected."""
    assert is_valid_national_id(" 1234567891 ") is False
    assert is_valid_national_id("123-456789-1") is False
    assert is_valid_national_id("123/456789/1") is False
    assert is_valid_national_id("123.456789.1") is False
    assert is_valid_national_id("123 456789 1") is False


def test_validator_non_digit_characters_rejected() -> None:
    """Verify strings with letters or non-digits are rejected."""
    assert is_valid_national_id("123456789a") is False
    assert is_valid_national_id("۱۲۳۴۵۶۷۸۹الف") is False
    assert is_valid_national_id(1234567891) is False  # type: ignore[arg-type]


def test_validator_unsupported_unicode_numerals_rejected() -> None:
    """Verify unsupported numeral systems (e.g. Bengali, Devanagari) are rejected."""
    bengali_digits = "১২৩৪৫۶۷۸۹১"
    assert is_valid_national_id(bengali_digits) is False


# --- Detector Tests ---


def test_detector_ascii_national_id() -> None:
    """Verify detector finds ASCII national ID in a sentence."""
    detector = IranianNationalIDDetector()
    original = "کد ملی متقاضی 1234567891 است."
    normalized = normalize_text(original)

    results = detector.detect(original, normalized)
    assert len(results) == 1
    assert results[0].type == "IR_NATIONAL_ID"
    assert results[0].value == "1234567891"
    assert results[0].normalized_value == "1234567891"
    assert results[0].start == original.index("1234567891")
    assert results[0].end == results[0].start + 10


def test_detector_persian_digits_national_id() -> None:
    """Verify detector preserves original Persian digits in Detection.value."""
    detector = IranianNationalIDDetector()
    original = "شماره ملی: ۱۲۳۴۵۶۷۸۹۱ جهت ثبت نام."
    normalized = normalize_text(original)

    results = detector.detect(original, normalized)
    assert len(results) == 1
    assert results[0].type == "IR_NATIONAL_ID"
    assert results[0].value == "۱۲۳۴۵۶۷۸۹۱"
    assert results[0].normalized_value == "1234567891"
    assert original[results[0].start : results[0].end] == "۱۲۳۴۵۶۷۸۹۱"
    assert normalized[results[0].start : results[0].end] == "1234567891"


def test_detector_arabic_indic_and_mixed_digits() -> None:
    """Verify detector handles Arabic-Indic and mixed digit representations."""
    detector = IranianNationalIDDetector()

    # Arabic-Indic
    orig_arabic = "کد ملی ١٢٣٤٥٦٧٨٩١"
    norm_arabic = normalize_text(orig_arabic)
    res_arabic = detector.detect(orig_arabic, norm_arabic)
    assert len(res_arabic) == 1
    assert res_arabic[0].value == "١٢٣٤٥٦٧٨٩١"
    assert res_arabic[0].normalized_value == "1234567891"

    # Mixed
    orig_mixed = "کد ملی ۱۲3٤۵6۷8۹1"
    norm_mixed = normalize_text(orig_mixed)
    res_mixed = detector.detect(orig_mixed, norm_mixed)
    assert len(res_mixed) == 1
    assert res_mixed[0].value == "۱۲3٤۵6۷8۹1"
    assert res_mixed[0].normalized_value == "1234567891"


def test_detector_invalid_checksum_ignored() -> None:
    """Verify invalid checksum candidates are skipped."""
    detector = IranianNationalIDDetector()
    original = "کد ملی نامعتبر 1234567890 است."
    normalized = normalize_text(original)

    results = detector.detect(original, normalized)
    assert len(results) == 0


def test_detector_repeated_digits_ignored() -> None:
    """Verify repeated-digit sequences are skipped."""
    detector = IranianNationalIDDetector()
    original = "شماره ۱۱۱۱۱۱۱۱۱۱ و ۲۲۲۲۲۲۲۲۲۲ نباید شناسایی شوند."
    normalized = normalize_text(original)

    results = detector.detect(original, normalized)
    assert len(results) == 0


def test_detector_multiple_candidates_in_order() -> None:
    """Verify multiple valid candidates are detected in textual order."""
    detector = IranianNationalIDDetector()
    original = "نفر اول ۱۲۳۴۵۶۷۸۹۱ و نفر دوم 0012345679 هستند."
    normalized = normalize_text(original)

    results = detector.detect(original, normalized)
    assert len(results) == 2
    assert results[0].value == "۱۲۳۴۵۶۷۸۹۱"
    assert results[0].normalized_value == "1234567891"
    assert results[1].value == "0012345679"
    assert results[1].normalized_value == "0012345679"
    assert results[0].start < results[1].start


def test_detector_longer_numeric_sequences_isolated() -> None:
    """Verify 10-digit patterns inside 11-digit or longer runs are NOT extracted."""
    detector = IranianNationalIDDetector()
    # 1234567891 prefixed or suffixed with extra digits
    original = "موبایل: 01234567891، حساب: 12345678910، طولانی: 99123456789199"
    normalized = normalize_text(original)

    results = detector.detect(original, normalized)
    assert len(results) == 0


def test_detector_punctuation_boundaries() -> None:
    """Verify valid IDs adjacent to various punctuation marks are detected."""
    detector = IranianNationalIDDetector()
    original = "(1234567891) [۱۲۳۴۵۶۷۸۹۱] :0012345679، 0490784526."
    normalized = normalize_text(original)

    results = detector.detect(original, normalized)
    assert len(results) == 4
    assert [r.normalized_value for r in results] == [
        "1234567891",
        "1234567891",
        "0012345679",
        "0490784526",
    ]


def test_detector_empty_text() -> None:
    """Verify empty text returns empty list."""
    detector = IranianNationalIDDetector()
    assert detector.detect("", "") == []


def test_detector_source_length_mismatch() -> None:
    """Verify ValueError is raised if original and normalized texts differ in length."""
    detector = IranianNationalIDDetector()
    with pytest.raises(ValueError, match="must equal normalized_text length"):
        detector.detect("abc", "abcd")


def test_detector_healthcare_synthetic_example() -> None:
    """Verify detection on synthetic clinical note using test vector."""
    detector = IranianNationalIDDetector()
    original = (
        "بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱ جهت تشکیل پرونده مراجعه کرد.\n"
        "تشخیص: سردرد میگرنی. فشار خون: 120/80."
    )
    normalized = normalize_text(original)

    results = detector.detect(original, normalized)
    assert len(results) == 1

    d = results[0]
    assert d.type == "IR_NATIONAL_ID"
    assert d.value == "۱۲۳۴۵۶۷۸۹۱"
    assert d.normalized_value == "1234567891"

    # Verify offset integrity
    assert original[d.start : d.end] == "۱۲۳۴۵۶۷۸۹۱"
    assert normalized[d.start : d.end] == "1234567891"

    # Verify clinical terms remain in text around the detection
    assert "تشخیص: سردرد میگرنی" in original
