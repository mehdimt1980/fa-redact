"""Tests for safe placeholder-based redaction (Phase 7)."""

from collections.abc import Sequence

import pytest

from fa_redact import (
    Detection,
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
    redact,
)


def test_redact_empty_string() -> None:
    """Verify empty string returns empty string."""
    assert redact("") == ""


def test_redact_no_pii() -> None:
    """Verify text with no PII is returned completely unchanged."""
    text = "این یک متن ساده بدون هیچ‌گونه اطلاعات هویتی است."
    assert redact(text) == text


def test_redact_single_national_id() -> None:
    """Verify single Iranian National ID is redacted with [IR_NATIONAL_ID_1]."""
    text = "کد ملی بیمار ۱۲۳۴۵۶۷۸۹۱ است."
    expected = "کد ملی بیمار [IR_NATIONAL_ID_1] است."
    assert redact(text) == expected


def test_redact_single_mobile() -> None:
    """Verify single Iranian mobile number is redacted with [IR_MOBILE_1]."""
    text = "شماره همراه: ۰۹۱۲۳۴۵۶۷۸۹ ثبت شد."
    expected = "شماره همراه: [IR_MOBILE_1] ثبت شد."
    assert redact(text) == expected


def test_redact_both_builtin_types() -> None:
    """Verify National ID and mobile number are redacted with typed placeholders."""
    text = "بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره تماس ۰۹۱۲۳۴۵۶۷۸۹ مراجعه نمود."
    expected = (
        "بیمار با کد ملی [IR_NATIONAL_ID_1] و شماره تماس [IR_MOBILE_1] مراجعه نمود."
    )
    assert redact(text) == expected


def test_redact_multiple_distinct_mobiles() -> None:
    """Verify multiple distinct mobile numbers receive sequential indexes."""
    text = "همراه اول: 09123456789، همراه دوم: 09351234567"
    expected = "همراه اول: [IR_MOBILE_1]، همراه دوم: [IR_MOBILE_2]"
    assert redact(text) == expected


def test_redact_repeated_same_mobile_referential_consistency() -> None:
    """Verify repeated occurrences of the same mobile number share a placeholder."""
    # First is Persian digits (۰۹۱۲۳۴۵۶۷۸۹), second is ASCII digits (09123456789)
    # Both normalize to "09123456789" -> same placeholder [IR_MOBILE_1]
    text = "تماس اولیه: ۰۹۱۲۳۴۵۶۷۸۹، تماس تکراری: 09123456789"
    expected = "تماس اولیه: [IR_MOBILE_1]، تماس تکراری: [IR_MOBILE_1]"
    assert redact(text) == expected


def test_redact_repeated_same_national_id_referential_consistency() -> None:
    """Verify repeated occurrences of the same National ID share a placeholder."""
    # First is Persian digits (۱۲۳۴۵۶۷۸۹۱), second is ASCII (1234567891)
    text = "کد ملی اول: ۱۲۳۴۵۶۷۸۹۱، کد ملی دوم: 1234567891"
    expected = "کد ملی اول: [IR_NATIONAL_ID_1]، کد ملی دوم: [IR_NATIONAL_ID_1]"
    assert redact(text) == expected


def test_redact_different_values_same_type() -> None:
    """Verify different values of the same type receive separate sequential indexes."""
    text = "کد ۱: 1234567891، کد ۲: 0012345679"
    expected = "کد ۱: [IR_NATIONAL_ID_1]، کد ۲: [IR_NATIONAL_ID_2]"
    assert redact(text) == expected


def test_redact_source_ordering_numbering() -> None:
    """Verify placeholder numbering follows first occurrence in source text."""
    text = "شماره: 09123456789، کد ملی: 1234567891، شماره دیگر: 09351234567"
    expected = (
        "شماره: [IR_MOBILE_1]، کد ملی: [IR_NATIONAL_ID_1]، شماره دیگر: [IR_MOBILE_2]"
    )
    assert redact(text) == expected


def test_redact_multiline_healthcare_text() -> None:
    """Verify redaction in realistic clinical text with repeated identifiers."""
    text = (
        "گزارش پذیرش بخش اورژانس:\n"
        "بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره همراه ۰۹۱۲۳۴۵۶۷۸۹ بستری شد.\n"
        "تشخیص اولیه: دیابت نوع ۲ و فشار خون بالا.\n"
        "داروهای تجویزی: متفورمین ۵۰۰ میلی‌گرم و لوزارتان ۲۵ میلی‌گرم.\n"
        "شماره تماس همراه بیمار جهت پیگیری: 09123456789 (همان شماره ثبت‌شده).\n"
        "کد ملی بیمار جهت ترخیص: 1234567891.\n"
    )
    expected = (
        "گزارش پذیرش بخش اورژانس:\n"
        "بیمار با کد ملی [IR_NATIONAL_ID_1] و شماره همراه [IR_MOBILE_1] بستری شد.\n"
        "تشخیص اولیه: دیابت نوع ۲ و فشار خون بالا.\n"
        "داروهای تجویزی: متفورمین ۵۰۰ میلی‌گرم و لوزارتان ۲۵ میلی‌گرم.\n"
        "شماره تماس همراه بیمار جهت پیگیری: [IR_MOBILE_1] (همان شماره ثبت‌شده).\n"
        "کد ملی بیمار جهت ترخیص: [IR_NATIONAL_ID_1].\n"
    )
    assert redact(text) == expected


def test_redact_international_mobile_formats() -> None:
    """Verify +98 and 0098 international formats are completely redacted."""
    text = "تماس ۱: +989123456789 و تماس ۲: 00989351234567"
    expected = "تماس ۱: [IR_MOBILE_1] و تماس ۲: [IR_MOBILE_2]"
    assert redact(text) == expected


def test_redact_arabic_indic_digit_representations() -> None:
    """Verify Arabic-Indic digit formats are properly recognized and redacted."""
    text = "کد ملی: ١٢٣٤٥٦٧٨٩١ و تلفن: ٠٩١٢٣٤٥٦٧٨٩"
    expected = "کد ملی: [IR_NATIONAL_ID_1] و تلفن: [IR_MOBILE_1]"
    assert redact(text) == expected


def test_redact_explicit_empty_detectors() -> None:
    """Verify detectors=[] leaves text completely unchanged."""
    text = "کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره ۰۹۱۲۳۴۵۶۷۸۹"
    assert redact(text, detectors=[]) == text


def test_redact_single_explicit_detector() -> None:
    """Verify passing a single detector redacts only that entity type."""
    text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱، شماره: ۰۹۱۲۳۴۵۶۷۸۹"
    # Redact mobile only:
    result = redact(text, detectors=[IranianMobileNumberDetector()])
    assert result == "کد ملی: ۱۲۳۴۵۶۷۸۹۱، شماره: [IR_MOBILE_1]"


def test_redact_custom_detector() -> None:
    """Verify custom structural detector is executed and typed placeholder applied."""

    class CustomMRNDetector:
        """Detector for custom synthetic Medical Record Number format MRN-XXXX."""

        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            keyword = "MRN-1234"
            idx = original_text.find(keyword)
            if idx != -1:
                return [
                    Detection.from_texts(
                        type="MRN",
                        original_text=original_text,
                        normalized_text=normalized_text,
                        start=idx,
                        end=idx + len(keyword),
                    )
                ]
            return []

    text = "پرونده بیمار با شناسه MRN-1234 ثبت گردید."
    result = redact(text, detectors=[CustomMRNDetector()])
    assert result == "پرونده بیمار با شناسه [MRN_1] ثبت گردید."


def test_redact_same_normalized_value_different_custom_types() -> None:
    """Verify same normalized value under different types gets distinct placeholders."""

    class TypeADetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="TYPE_A",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=0,
                    end=3,
                )
            ]

    class TypeBDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="TYPE_B",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=4,
                    end=7,
                )
            ]

    text = "123 123"
    result = redact(text, detectors=[TypeADetector(), TypeBDetector()])
    assert result == "[TYPE_A_1] [TYPE_B_1]"


def test_redact_overlapping_custom_detections_raises_value_error() -> None:
    """Verify overlapping spans raise ValueError without leaking PII values."""

    class Span1Detector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="SPAN_1",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=0,
                    end=5,
                )
            ]

    class Span2Detector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="SPAN_2",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=3,
                    end=8,
                )
            ]

    text = "0123456789"
    with pytest.raises(ValueError) as excinfo:
        redact(text, detectors=[Span1Detector(), Span2Detector()])

    msg = str(excinfo.value)
    assert "Overlapping detections at spans [0:5] (SPAN_1) and [3:8] (SPAN_2)" in msg
    # Verify no source text or PII is leaked in exception message:
    assert "0123456789" not in msg
    assert "01234" not in msg


def test_redact_nested_custom_detections_raises_value_error() -> None:
    """Verify nested spans raise ValueError."""

    class OuterDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="OUTER",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=0,
                    end=10,
                )
            ]

    class InnerDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="INNER",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=2,
                    end=6,
                )
            ]

    text = "0123456789"
    with pytest.raises(ValueError, match=r"Overlapping detections at spans"):
        redact(text, detectors=[OuterDetector(), InnerDetector()])


def test_redact_exact_duplicate_detections_raises_value_error() -> None:
    """Verify exact duplicate spans from different detectors raise ValueError."""

    class DuplicateDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="DUP_1",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=0,
                    end=5,
                ),
                Detection.from_texts(
                    type="DUP_2",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=0,
                    end=5,
                ),
            ]

    text = "0123456789"
    with pytest.raises(ValueError, match=r"Overlapping detections at spans"):
        redact(text, detectors=[DuplicateDetector()])


def test_redact_adjacent_custom_detections() -> None:
    """Verify adjacent spans (prev.end == curr.start) redact cleanly without error."""

    class Adj1Detector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="ADJ_1",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=0,
                    end=4,
                )
            ]

    class Adj2Detector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="ADJ_2",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=4,
                    end=8,
                )
            ]

    text = "AAAABBBB"
    result = redact(text, detectors=[Adj1Detector(), Adj2Detector()])
    assert result == "[ADJ_1_1][ADJ_2_1]"


def test_redact_duplicate_detector_instance_raises_value_error() -> None:
    """Verify passing the same detector twice raises overlap ValueError."""
    text = "کد ملی: 1234567891"
    nid_detector = IranianNationalIDDetector()
    with pytest.raises(ValueError, match=r"Overlapping detections at spans"):
        redact(text, detectors=[nid_detector, nid_detector])


def test_redact_custom_detector_exception_propagates() -> None:
    """Verify custom detector exceptions propagate unchanged."""

    class FailingDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            raise RuntimeError("custom detector crashed")

    with pytest.raises(RuntimeError, match="custom detector crashed"):
        redact("متن تست", detectors=[FailingDetector()])


def test_redact_non_string_input_raises_type_error() -> None:
    """Verify non-string inputs raise TypeError without leaking input content."""
    with pytest.raises(TypeError, match="text must be a str"):
        redact(None)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="text must be a str"):
        redact(12345)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="text must be a str"):
        redact(["invalid"])  # type: ignore[arg-type]


def test_redact_placeholder_collision_single() -> None:
    """Verify existing literal placeholder in source text is skipped."""
    # Text already contains "[IR_MOBILE_1]" literally
    text = "یادداشت: [IR_MOBILE_1]، شماره واقعی: 09123456789"
    expected = "یادداشت: [IR_MOBILE_1]، شماره واقعی: [IR_MOBILE_2]"
    assert redact(text) == expected


def test_redact_placeholder_collision_multiple() -> None:
    """Verify multiple existing literal placeholders are all skipped."""
    text = "ثبت شده: [IR_MOBILE_1] و [IR_MOBILE_2]، شماره جدید: 09123456789"
    expected = "ثبت شده: [IR_MOBILE_1] و [IR_MOBILE_2]، شماره جدید: [IR_MOBILE_3]"
    assert redact(text) == expected


def test_redact_exact_span_replacement_correctness() -> None:
    """Verify redaction replaces only exact detected spans, not identical texts."""

    class SelectiveDetector:
        """Detector that detects only the second occurrence of 'بیمار'."""

        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            target = "بیمار"
            first = original_text.find(target)
            second = original_text.find(target, first + len(target))
            return [
                Detection.from_texts(
                    type="SELECTIVE",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=second,
                    end=second + len(target),
                )
            ]

    text = "بیمار اول و بیمار دوم"
    result = redact(text, detectors=[SelectiveDetector()])
    assert result == "بیمار اول و [SELECTIVE_1] دوم"


def test_redact_referential_consistency_limitation() -> None:
    """Verify referential consistency operates on normalized_value strings.

    In Phase 7, representations that normalize to different strings (e.g. domestic
    '09123456789' vs international '+989123456789') receive separate placeholders.
    """
    text = "شماره داخلی: 09123456789، شماره بین‌الملل: +989123456789"
    result = redact(text)
    # Domestic normalizes to "09123456789", international normalizes to "+989123456789"
    assert result == "شماره داخلی: [IR_MOBILE_1]، شماره بین‌الملل: [IR_MOBILE_2]"


def test_redact_single_iban() -> None:
    """Verify default redact() replaces Iranian IBAN with [IR_IBAN_1]."""
    text = "شماره شبا: IR641234567890123456789012"
    assert redact(text) == "شماره شبا: [IR_IBAN_1]"


def test_redact_multiple_distinct_ibans() -> None:
    """Verify multiple distinct IBANs receive sequential placeholder indices."""
    text = "شبا اصلی: IR641234567890123456789012، شبا فرعی: IR220000000000000000000001"
    expected = "شبا اصلی: [IR_IBAN_1]، شبا فرعی: [IR_IBAN_2]"
    assert redact(text) == expected


def test_redact_repeated_same_iban_referential_consistency() -> None:
    """Verify repeated ASCII and Persian digit representations share [IR_IBAN_1]."""
    text = (
        "شبا لاتین: IR641234567890123456789012، شبا فارسی: IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲"
    )
    expected = "شبا لاتین: [IR_IBAN_1]، شبا فارسی: [IR_IBAN_1]"
    assert redact(text) == expected


def test_redact_single_bank_card_opt_in() -> None:
    """Verify explicit redact() replaces 16-digit card with [BANK_CARD_1]."""
    from fa_redact import BankCardDetector

    text = "شماره کارت: 1234567890123452"
    assert redact(text, detectors=[BankCardDetector()]) == "شماره کارت: [BANK_CARD_1]"


def test_redact_multiple_distinct_bank_cards() -> None:
    """Verify multiple distinct bank cards receive sequential placeholders."""
    from fa_redact import BankCardDetector

    text = "کارت اول: 1234567890123452، کارت دوم: 5022291234567897"
    expected = "کارت اول: [BANK_CARD_1]، کارت دوم: [BANK_CARD_2]"
    assert redact(text, detectors=[BankCardDetector()]) == expected


def test_redact_repeated_same_bank_card_referential_consistency() -> None:
    """Verify repeated ASCII and Persian representations share [BANK_CARD_1]."""
    from fa_redact import BankCardDetector

    text = "کارت لاتین: 1234567890123452، کارت فارسی: ۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۲"
    expected = "کارت لاتین: [BANK_CARD_1]، کارت فارسی: [BANK_CARD_1]"
    assert redact(text, detectors=[BankCardDetector()]) == expected


def test_redact_with_pattern_detector_opt_in() -> None:
    """Verify redact() with custom PatternDetector produces typed placeholders."""
    from fa_redact import PatternDetector, PatternRule

    detector = PatternDetector(
        [
            PatternRule(type="MRN", pattern=r"(?<!\w)MRN-[0-9]{6}(?!\w)"),
            PatternRule(type="PATIENT_ID", pattern=r"(?<!\w)PAT-[0-9]{8}(?!\w)"),
        ]
    )
    text = "پرونده: MRN-123456 و بیمار: PAT-12345678"
    expected = "پرونده: [MRN_1] و بیمار: [PATIENT_ID_1]"
    assert redact(text, detectors=[detector]) == expected
