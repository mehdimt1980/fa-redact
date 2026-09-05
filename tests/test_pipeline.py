"""Tests for the high-level detection pipeline (Phase 6)."""

from collections.abc import Sequence

import pytest

from fa_redact import (
    Detection,
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
    detect,
    normalize_text,
)


def test_detect_empty_text() -> None:
    """Verify empty text returns empty list."""
    assert detect("") == []


def test_detect_national_id_only() -> None:
    """Verify default pipeline detects a single Iranian National ID."""
    text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱ است."
    results = detect(text)
    assert len(results) == 1
    assert results[0].type == "IR_NATIONAL_ID"
    assert results[0].value == "۱۲۳۴۵۶۷۸۹۱"
    assert results[0].normalized_value == "1234567891"


def test_detect_mobile_only() -> None:
    """Verify default pipeline detects a single Iranian Mobile Number."""
    text = "همراه: ۰۹۱۲۳۴۵۶۷۸۹ ثبت شد."
    results = detect(text)
    assert len(results) == 1
    assert results[0].type == "IR_MOBILE"
    assert results[0].value == "۰۹۱۲۳۴۵۶۷۸۹"
    assert results[0].normalized_value == "09123456789"


def test_detect_mixed_national_id_and_mobile() -> None:
    """Verify default pipeline detects both National ID and Mobile Number."""
    text = "کد ملی 1234567891 و همراه 09123456789"
    results = detect(text)
    assert len(results) == 2
    types = {r.type for r in results}
    assert types == {"IR_NATIONAL_ID", "IR_MOBILE"}


def test_detect_source_ordering() -> None:
    """Verify detections are ordered by source offset regardless of detector order."""
    # 1. Mobile before National ID
    text_mobile_first = "شماره 09123456789 و کد 1234567891"
    results1 = detect(text_mobile_first)
    assert len(results1) == 2
    assert results1[0].type == "IR_MOBILE"
    assert results1[1].type == "IR_NATIONAL_ID"
    assert results1[0].start < results1[1].start

    # 2. National ID before Mobile
    text_nid_first = "کد 1234567891 و شماره 09123456789"
    results2 = detect(text_nid_first)
    assert len(results2) == 2
    assert results2[0].type == "IR_NATIONAL_ID"
    assert results2[1].type == "IR_MOBILE"
    assert results2[0].start < results2[1].start


def test_detect_persian_digit_preservation() -> None:
    """Verify Persian digit strings preserve raw values in Detection.value."""
    text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱، همراه: ۰۹۱۲۳۴۵۶۷۸۹"
    results = detect(text)
    assert len(results) == 2
    assert results[0].value == "۱۲۳۴۵۶۷۸۹۱"
    assert results[0].normalized_value == "1234567891"
    assert results[1].value == "۰۹۱۲۳۴۵۶۷۸۹"
    assert results[1].normalized_value == "09123456789"


def test_detect_arabic_indic_digit_preservation() -> None:
    """Verify Arabic-Indic digit strings preserve raw values in Detection.value."""
    text = "کد ملی: ١٢٣٤٥٦٧٨٩١، همراه: ٠٩١٢٣٤٥٦٧٨٩"
    results = detect(text)
    assert len(results) == 2
    assert results[0].value == "١٢٣٤٥٦٧٨٩١"
    assert results[0].normalized_value == "1234567891"
    assert results[1].value == "٠٩١٢٣٤٥٦٧٨٩"
    assert results[1].normalized_value == "09123456789"


def test_detect_multiline_healthcare_text() -> None:
    """Verify detection on synthetic multiline clinical text with exact offsets."""
    text = (
        "گزارش پذیرش درمانگاه:\n"
        "نام بیمار: بیمار الف\n"
        "کد ملی: ۱۲۳۴۵۶۷۸۹۱\n"
        "تلفن تماس: +989123456789\n"
        "علت مراجعه: معاینه دوره‌ای."
    )
    normalized = normalize_text(text)
    results = detect(text)

    assert len(results) == 2
    assert results[0].type == "IR_NATIONAL_ID"
    assert results[0].value == "۱۲۳۴۵۶۷۸۹۱"
    assert results[1].type == "IR_MOBILE"
    assert results[1].value == "+989123456789"

    for d in results:
        assert text[d.start : d.end] == d.value
        assert normalized[d.start : d.end] == d.normalized_value


def test_detect_explicit_empty_detectors() -> None:
    """Verify detectors=[] returns [] even if entities exist in text."""
    text = "کد 1234567891 و شماره 09123456789"
    assert detect(text, detectors=[]) == []


def test_detect_single_explicit_detector() -> None:
    """Verify passing a single explicit detector runs only that detector."""
    text = "کد 1234567891 و همراه 09123456789"
    results = detect(text, detectors=[IranianMobileNumberDetector()])
    assert len(results) == 1
    assert results[0].type == "IR_MOBILE"
    assert results[0].value == "09123456789"


def test_detect_custom_detector() -> None:
    """Verify custom detector satisfying Detector protocol executes via detect()."""

    class WordDetector:
        """Custom detector identifying specific keywords."""

        def detect(
            self,
            original_text: str,
            normalized_text: str,
        ) -> Sequence[Detection]:
            keyword = "بیمار"
            detections: list[Detection] = []
            idx = original_text.find(keyword)
            while idx != -1:
                detections.append(
                    Detection.from_texts(
                        type="CUSTOM_KEYWORD",
                        original_text=original_text,
                        normalized_text=normalized_text,
                        start=idx,
                        end=idx + len(keyword),
                    )
                )
                idx = original_text.find(keyword, idx + len(keyword))
            return detections

    text = "بیمار اول و بیمار دوم"
    results = detect(text, detectors=[WordDetector()])
    assert len(results) == 2
    assert all(r.type == "CUSTOM_KEYWORD" for r in results)


def test_detect_custom_detector_receives_normalized_text() -> None:
    """Verify custom detectors receive the position-preserving normalized text."""

    class NormalizedInspectorDetector:
        """Detector asserting that normalized_text contains ASCII digits."""

        def detect(
            self,
            original_text: str,
            normalized_text: str,
        ) -> Sequence[Detection]:
            assert "123" in normalized_text
            assert "۱۲۳" in original_text
            start = original_text.index("۱۲۳")
            return [
                Detection.from_texts(
                    type="CUSTOM_DIGIT",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=start,
                    end=start + 3,
                )
            ]

    text = "شناسه: ۱۲۳"
    results = detect(text, detectors=[NormalizedInspectorDetector()])
    assert len(results) == 1
    assert results[0].value == "۱۲۳"
    assert results[0].normalized_value == "123"


def test_detect_custom_detector_result_ordering() -> None:
    """Verify out-of-order spans from multiple detectors are globally sorted."""

    class LateDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="LATE",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=10,
                    end=15,
                )
            ]

    class EarlyDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="EARLY",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=2,
                    end=6,
                )
            ]

    text = "01234567890123456789"
    # Execute LateDetector first in sequence
    results = detect(text, detectors=[LateDetector(), EarlyDetector()])
    assert len(results) == 2
    assert results[0].type == "EARLY"
    assert results[0].start == 2
    assert results[1].type == "LATE"
    assert results[1].start == 10


def test_detect_overlapping_custom_detections_retained() -> None:
    """Verify overlapping spans from different detectors are retained in Phase 6."""

    class SpanADetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="SPAN_A",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=0,
                    end=5,
                )
            ]

    class SpanBDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="SPAN_B",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=2,
                    end=7,
                )
            ]

    text = "0123456789"
    results = detect(text, detectors=[SpanADetector(), SpanBDetector()])
    assert len(results) == 2
    assert results[0].type == "SPAN_A"
    assert results[1].type == "SPAN_B"


def test_detect_duplicate_detector_retains_duplicates() -> None:
    """Verify passing the same detector twice retains duplicates as documented."""
    text = "کد ملی: 1234567891"
    nid_detector = IranianNationalIDDetector()
    results = detect(text, detectors=[nid_detector, nid_detector])
    assert len(results) == 2
    assert results[0] == results[1]


def test_detect_detector_failure_propagation() -> None:
    """Verify detector exceptions are propagated without being swallowed."""

    class FailingDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            raise RuntimeError("detector failed")

    with pytest.raises(RuntimeError, match="detector failed"):
        detect("تست", detectors=[FailingDetector()])


def test_detect_non_string_input_raises_type_error() -> None:
    """Verify non-string text inputs raise TypeError."""
    with pytest.raises(TypeError, match="text must be a str"):
        detect(None)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="text must be a str"):
        detect(123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="text must be a str"):
        detect(["invalid"])  # type: ignore[arg-type]


def test_detect_iranian_iban_default() -> None:
    """Verify default pipeline detects Iranian IBAN in ASCII and Persian digits."""
    text_ascii = "شماره شبا: IR641234567890123456789012"
    results_ascii = detect(text_ascii)
    assert len(results_ascii) == 1
    assert results_ascii[0].type == "IR_IBAN"
    assert results_ascii[0].value == "IR641234567890123456789012"
    assert results_ascii[0].normalized_value == "IR641234567890123456789012"

    text_persian = "شماره شبا: IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲"
    results_persian = detect(text_persian)
    assert len(results_persian) == 1
    assert results_persian[0].type == "IR_IBAN"
    assert results_persian[0].value == "IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲"
    assert results_persian[0].normalized_value == "IR641234567890123456789012"


def test_detect_all_three_default_entities() -> None:
    """Verify default pipeline detects National ID, Mobile, and IBAN together."""
    text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱، موبایل: ۰۹۱۲۳۴۵۶۷۸۹، شبا: IR641234567890123456789012"
    results = detect(text)
    assert len(results) == 3
    assert results[0].type == "IR_NATIONAL_ID"
    assert results[1].type == "IR_MOBILE"
    assert results[2].type == "IR_IBAN"


def test_detect_no_accidental_overlap_inside_iban() -> None:
    """Verify 24-digit IBAN does not trigger National ID or Mobile detections."""
    text = "IR641234567890123456789012"
    results = detect(text)
    assert len(results) == 1
    assert results[0].type == "IR_IBAN"
    assert results[0].value == text


def test_email_remains_absent_from_defaults() -> None:
    """Verify EmailDetector remains opt-in and is not run by default in detect()."""
    text = "ایمیل: user@example.com و شبا: IR641234567890123456789012"
    results = detect(text)
    # Only IBAN should be detected by default
    assert len(results) == 1
    assert results[0].type == "IR_IBAN"
