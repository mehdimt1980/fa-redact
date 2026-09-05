"""Tests for Iranian Mobile Number validation and detection (Phase 5)."""

import pytest

from fa_redact import (
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
    is_valid_mobile_number,
    normalize_text,
)

# --- Validator Tests ---

# Representative test vectors across all 2026 CRA mobile NDC prefix families
_VALID_DOMESTIC_TEST_VECTORS = [
    # 900..905
    "09001234567",
    "09011234567",
    "09021234567",
    "09031234567",
    "09041234567",
    "09051234567",
    # 91
    "09101234567",
    "09121234567",
    "09191234567",
    # 920..923
    "09201234567",
    "09211234567",
    "09221234567",
    "09231234567",
    # 93
    "09301234567",
    "09351234567",
    "09391234567",
    # 990..994
    "09901234567",
    "09911234567",
    "09921234567",
    "09931234567",
    "09941234567",
    # 99510, 99550
    "09951012345",
    "09955012345",
    # 996
    "09961234567",
    # 998...
    "09981123456",
    "09982123456",
    "09983012345",
    "09983112345",
    "09983212345",
    "09988812345",
    # 999...
    "09990012345",
    "09990112345",
    "09990212345",
    "09990312345",
    "09991123456",
    "09992112345",
    "09993012345",
    "09993112345",
    "09993212345",
    "09993312345",
    "09993412345",
    "09995123456",
    "09996912345",
    "09997712345",
    "09998123456",
    "09999123456",
]


@pytest.mark.parametrize("phone", _VALID_DOMESTIC_TEST_VECTORS)
def test_validator_valid_domestic_prefixes(phone: str) -> None:
    """Verify all official 2026 CRA mobile NDC prefix families validate."""
    assert is_valid_mobile_number(phone) is True


def test_validator_international_plus_format() -> None:
    """Verify +98 international format validation."""
    assert is_valid_mobile_number("+989123456789") is True
    assert is_valid_mobile_number("+989351234567") is True
    assert is_valid_mobile_number("+989901234567") is True
    assert is_valid_mobile_number("+989951012345") is True


def test_validator_international_dial_prefix_format() -> None:
    """Verify 0098 international dial prefix format validation."""
    assert is_valid_mobile_number("00989123456789") is True
    assert is_valid_mobile_number("00989351234567") is True
    assert is_valid_mobile_number("00989901234567") is True


def test_validator_persian_and_arabic_indic_digits() -> None:
    """Verify Persian and Arabic-Indic digit encodings across all formats."""
    # Domestic Persian
    assert is_valid_mobile_number("۰۹۱۲۳۴۵۶۷۸۹") is True
    # International Plus Persian
    assert is_valid_mobile_number("+۹۸۹۱۲۳۴۵۶۷۸۹") is True
    # International 0098 Persian
    assert is_valid_mobile_number("۰۰۹۸۹۱۲۳۴۵۶۷۸۹") is True

    # Domestic Arabic-Indic
    assert is_valid_mobile_number("٠٩١٢٣٤٥٦٧٨٩") is True
    # International Plus Arabic-Indic
    assert is_valid_mobile_number("+٩٨٩١٢٣٤٥٦٧٨٩") is True
    # International 0098 Arabic-Indic
    assert is_valid_mobile_number("٠٠٩٨٩١٢٣٤٥٦٧٨٩") is True


def test_validator_mixed_digit_sets() -> None:
    """Verify mixed supported digit representations."""
    assert is_valid_mobile_number("۰91۲34۵678۹") is True
    assert is_valid_mobile_number("+98۹1۲3456789") is True


def test_validator_rejected_fixed_and_non_geographical_ranges() -> None:
    """Verify 094... fixed/non-geographical numbers are strictly rejected."""
    assert is_valid_mobile_number("09412345678") is False
    assert is_valid_mobile_number("09421234567") is False
    assert is_valid_mobile_number("+989412345678") is False
    assert is_valid_mobile_number("00989412345678") is False


def test_validator_rejected_public_trunk_ranges() -> None:
    """Verify 09950... public trunk ranges are rejected unless in 99510/99550."""
    assert is_valid_mobile_number("09950123456") is False
    assert is_valid_mobile_number("09952123456") is False
    assert is_valid_mobile_number("+989950123456") is False


def test_validator_rejected_unlisted_prefixes() -> None:
    """Verify unallocated or unlisted prefixes are rejected."""
    assert is_valid_mobile_number("09061234567") is False
    assert is_valid_mobile_number("09241234567") is False
    assert is_valid_mobile_number("09712345678") is False
    assert is_valid_mobile_number("09512345678") is False
    assert is_valid_mobile_number("09812345678") is False


def test_validator_strict_formatting_rejected() -> None:
    """Verify spaces, hyphens, parentheses, and slashes are rejected."""
    assert is_valid_mobile_number("0912 345 6789") is False
    assert is_valid_mobile_number("0912-345-6789") is False
    assert is_valid_mobile_number("(0912)3456789") is False
    assert is_valid_mobile_number("0912/345/6789") is False
    assert is_valid_mobile_number(" 09123456789 ") is False


def test_validator_invalid_lengths() -> None:
    """Verify invalid lengths are rejected."""
    assert is_valid_mobile_number("") is False
    assert is_valid_mobile_number("0912345678") is False  # 10 chars
    assert is_valid_mobile_number("091234567890") is False  # 12 chars
    assert is_valid_mobile_number("+98912345678") is False  # 12 chars
    assert is_valid_mobile_number("+9891234567890") is False  # 14 chars


def test_validator_bare_nsn_rejected() -> None:
    """Verify bare 10-digit NSN without national/international prefix is rejected."""
    assert is_valid_mobile_number("9123456789") is False


def test_validator_incorrect_trunk_in_international_rejected() -> None:
    """Verify international format with domestic trunk 0 is rejected."""
    assert is_valid_mobile_number("+9809123456789") is False
    assert is_valid_mobile_number("009809123456789") is False


def test_validator_non_string_and_unsupported_numerals() -> None:
    """Verify non-string types and unsupported numeral systems are rejected."""
    assert is_valid_mobile_number(9123456789) is False  # type: ignore[arg-type]
    assert is_valid_mobile_number("০৯১২৩৪۵۶۷۸۹") is False  # Bengali digits


# --- Detector Tests ---


def test_detector_domestic_ascii() -> None:
    """Verify detection of compact domestic mobile number."""
    detector = IranianMobileNumberDetector()
    text = "شماره همراه بیمار 09123456789 است."
    normalized = normalize_text(text)

    results = detector.detect(text, normalized)
    assert len(results) == 1
    assert results[0].type == "IR_MOBILE"
    assert results[0].value == "09123456789"
    assert results[0].normalized_value == "09123456789"
    assert results[0].start == text.index("09123456789")
    assert results[0].end == results[0].start + 11


def test_detector_persian_digits() -> None:
    """Verify detector preserves raw Persian digits in Detection.value."""
    detector = IranianMobileNumberDetector()
    text = "تماس با ۰۹۱۲۳۴۵۶۷۸۹ جهت هماهنگی."
    normalized = normalize_text(text)

    results = detector.detect(text, normalized)
    assert len(results) == 1
    assert results[0].type == "IR_MOBILE"
    assert results[0].value == "۰۹۱۲۳۴۵۶۷۸۹"
    assert results[0].normalized_value == "09123456789"
    assert text[results[0].start : results[0].end] == "۰۹۱۲۳۴۵۶۷۸۹"
    assert normalized[results[0].start : results[0].end] == "09123456789"


def test_detector_arabic_indic_and_mixed_digits() -> None:
    """Verify detector handles Arabic-Indic and mixed digits."""
    detector = IranianMobileNumberDetector()

    # Arabic-Indic
    text_ar = "شماره ٠٩١٢٣٤٥٦٧٨٩ ثبت شد."
    norm_ar = normalize_text(text_ar)
    res_ar = detector.detect(text_ar, norm_ar)
    assert len(res_ar) == 1
    assert res_ar[0].value == "٠٩١٢٣٤٥٦٧٨٩"
    assert res_ar[0].normalized_value == "09123456789"

    # Mixed
    text_mix = "تلفن ۰91۲34۵678۹ موجود است."
    norm_mix = normalize_text(text_mix)
    res_mix = detector.detect(text_mix, norm_mix)
    assert len(res_mix) == 1
    assert res_mix[0].value == "۰91۲34۵678۹"
    assert res_mix[0].normalized_value == "09123456789"


def test_detector_international_plus_and_0098() -> None:
    """Verify detection of international +98 and 0098 formats."""
    detector = IranianMobileNumberDetector()

    # +98 format
    text_plus = "تماس اضطراری: +989123456789"
    norm_plus = normalize_text(text_plus)
    res_plus = detector.detect(text_plus, norm_plus)
    assert len(res_plus) == 1
    assert res_plus[0].value == "+989123456789"
    assert res_plus[0].normalized_value == "+989123456789"

    # 0098 format
    text_00 = "کد بین‌الملل: 00989351234567"
    norm_00 = normalize_text(text_00)
    res_00 = detector.detect(text_00, norm_00)
    assert len(res_00) == 1
    assert res_00[0].value == "00989351234567"
    assert res_00[0].normalized_value == "00989351234567"


def test_detector_multiple_numbers_in_order() -> None:
    """Verify multiple numbers are detected in textual order."""
    detector = IranianMobileNumberDetector()
    text = "همراه اول: 09123456789 و ایرانسل: 09351234567"
    normalized = normalize_text(text)

    results = detector.detect(text, normalized)
    assert len(results) == 2
    assert results[0].value == "09123456789"
    assert results[1].value == "09351234567"
    assert results[0].start < results[1].start


def test_detector_unlisted_and_fixed_ranges_ignored() -> None:
    """Verify unlisted prefixes (0906...) and fixed ranges (094...) are skipped."""
    detector = IranianMobileNumberDetector()
    text = "غیرمجاز: 09061234567، ثابت: 09412345678، عمومی: 09950123456"
    normalized = normalize_text(text)

    results = detector.detect(text, normalized)
    assert len(results) == 0


def test_detector_longer_numeric_sequence_isolation() -> None:
    """Verify numbers embedded inside longer digit runs are NOT detected."""
    detector = IranianMobileNumberDetector()
    text = "شماره اشتباه: 9909123456789 و حساب 0912345678900 و +9891234567890"
    normalized = normalize_text(text)

    results = detector.detect(text, normalized)
    assert len(results) == 0


def test_detector_adjacent_punctuation() -> None:
    """Verify numbers adjacent to punctuation marks are properly extracted."""
    detector = IranianMobileNumberDetector()
    text = "(09123456789) [+989351234567] :00989901234567، ۰۹۲۱۲۳۴۵۶۷۸."
    normalized = normalize_text(text)

    results = detector.detect(text, normalized)
    assert len(results) == 4
    assert [r.normalized_value for r in results] == [
        "09123456789",
        "+989351234567",
        "00989901234567",
        "09212345678",
    ]


def test_detector_empty_text() -> None:
    """Verify empty text returns empty list."""
    detector = IranianMobileNumberDetector()
    assert detector.detect("", "") == []


def test_detector_source_length_mismatch() -> None:
    """Verify ValueError on mismatched source text lengths."""
    detector = IranianMobileNumberDetector()
    with pytest.raises(ValueError, match="must equal normalized_text length"):
        detector.detect("0912", "09123")


def test_detector_healthcare_synthetic_example() -> None:
    """Verify detection on synthetic clinical text using mobile test vector."""
    detector = IranianMobileNumberDetector()
    text = (
        "پرونده بیمار: بستری در بخش داخلی.\n"
        "شماره تماس همراه: ۰۹۱۲۳۴۵۶۷۸۹ جهت پیگیری نتایج آزمایش."
    )
    normalized = normalize_text(text)

    results = detector.detect(text, normalized)
    assert len(results) == 1

    d = results[0]
    assert d.type == "IR_MOBILE"
    assert d.value == "۰۹۱۲۳۴۵۶۷۸۹"
    assert d.normalized_value == "09123456789"

    # Exact offset integrity
    assert text[d.start : d.end] == "۰۹۱۲۳۴۵۶۷۸۹"
    assert normalized[d.start : d.end] == "09123456789"
    assert "بستری در بخش داخلی" in text


def test_interaction_with_national_id_detector() -> None:
    """Verify 11-digit mobile is not detected by National ID detector and vice versa."""
    nid_detector = IranianNationalIDDetector()
    mobile_detector = IranianMobileNumberDetector()

    # 1. Eleven-digit mobile number in text
    mobile_text = "همراه: 09123456789"
    mobile_norm = normalize_text(mobile_text)

    # National ID detector must NOT match any part of the 11-digit mobile
    nid_results = nid_detector.detect(mobile_text, mobile_norm)
    assert len(nid_results) == 0

    # Mobile detector MUST match the mobile number
    mob_results = mobile_detector.detect(mobile_text, mobile_norm)
    assert len(mob_results) == 1
    assert mob_results[0].type == "IR_MOBILE"

    # 2. Ten-digit National ID in text
    nid_text = "کد ملی: 1234567891"
    nid_norm = normalize_text(nid_text)

    # Mobile detector must NOT match 10-digit National ID
    mob_results2 = mobile_detector.detect(nid_text, nid_norm)
    assert len(mob_results2) == 0

    # National ID detector MUST match National ID
    nid_results2 = nid_detector.detect(nid_text, nid_norm)
    assert len(nid_results2) == 1
    assert nid_results2[0].type == "IR_NATIONAL_ID"
