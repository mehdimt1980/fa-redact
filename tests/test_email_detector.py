"""Tests for EmailDetector and email detection pipeline integration."""

import pytest

from fa_redact import (
    Detector,
    EmailDetector,
    IranianMobileNumberDetector,
    PseudonymizationSession,
    detect,
    redact,
)
from fa_redact.normalization import normalize_text


class TestEmailDetectorUnit:
    """Direct unit tests for EmailDetector."""

    def test_basic_sentence_detection(self) -> None:
        detector = EmailDetector()
        text = "جهت پیگیری با ایمیل alice@example.com تماس بگیرید."
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 1
        d = detections[0]
        assert d.type == "EMAIL"
        assert d.value == "alice@example.com"
        assert d.normalized_value == "alice@example.com"
        assert text[d.start : d.end] == "alice@example.com"

    def test_multiple_emails_source_order(self) -> None:
        detector = EmailDetector()
        text = "تماس ۱: alice@example.com و تماس ۲: bob.smith@example.co.uk"
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 2
        assert detections[0].value == "alice@example.com"
        assert detections[1].value == "bob.smith@example.co.uk"
        assert detections[0].start < detections[1].start

    def test_trailing_punctuation_boundaries(self) -> None:
        detector = EmailDetector()
        cases = [
            ("ایمیل: alice@example.com.", "alice@example.com"),
            ("ایمیل: alice@example.com,", "alice@example.com"),
            ("ایمیل: alice@example.com;", "alice@example.com"),
            ("ایمیل: alice@example.com:", "alice@example.com"),
            ("تماس (alice@example.com)", "alice@example.com"),
            ("آدرس <alice@example.com>", "alice@example.com"),
            ('پست الکترونیک: "alice@example.com"', "alice@example.com"),
            ("ارسال به [alice@example.com]", "alice@example.com"),
        ]

        for text, expected in cases:
            norm = normalize_text(text)
            detections = detector.detect(text, norm)
            assert len(detections) == 1
            assert detections[0].value == expected
            assert text[detections[0].start : detections[0].end] == expected

    def test_multi_line_synthetic_prose(self) -> None:
        detector = EmailDetector()
        text = (
            "Patient Clinical Referral\n"
            "Primary Contact: referral@hospital-system.org\n"
            "Billing Inquiry: billing.dept+urgent@health-center.co.uk\n"
            "End of record."
        )
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 2
        assert detections[0].value == "referral@hospital-system.org"
        assert detections[1].value == "billing.dept+urgent@health-center.co.uk"
        for d in detections:
            assert text[d.start : d.end] == d.value

    def test_ascii_only_protection_persian_digits_not_detected(self) -> None:
        """Prove scanner scans original text so Persian digits in emails
        are rejected.
        """
        detector = EmailDetector()
        # Even though normalization would convert ۱۲ to 12,
        # the detector operates on original_text and rejects user۱۲@example.com.
        text = "ایمیل نامعتبر: user۱۲@example.com و دیگری: ۱۲۳@example.com"
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 0

    def test_length_mismatch_raises_value_error(self) -> None:
        detector = EmailDetector()
        with pytest.raises(ValueError, match="must equal normalized_text length"):
            detector.detect("test@example.com", "short")

    def test_detector_does_not_mutate_or_transform_input(self) -> None:
        detector = EmailDetector()
        text = "ایمیل UPPER.CASE@EXAMPLE.COM است."
        norm = normalize_text(text)

        detections = detector.detect(text, norm)
        assert len(detections) == 1
        assert detections[0].value == "UPPER.CASE@EXAMPLE.COM"
        assert detections[0].normalized_value == "UPPER.CASE@EXAMPLE.COM"


class TestEmailPipelineIntegration:
    """Test detect() pipeline integration with EmailDetector."""

    def test_default_detect_does_not_detect_email(self) -> None:
        """Verify EmailDetector is strictly opt-in in Phase 12."""
        text = "تماس: alice@example.com"
        detections = detect(text)
        assert detections == []

    def test_explicit_detect_with_email_detector(self) -> None:
        text = "تماس: alice@example.com"
        detections = detect(text, detectors=[EmailDetector()])
        assert len(detections) == 1
        assert detections[0].type == "EMAIL"
        assert detections[0].value == "alice@example.com"

    def test_custom_detector_list_replaces_defaults(self) -> None:
        # text contains both National ID and Email
        text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱ و ایمیل: alice@example.com"

        # Defaults detect only National ID
        default_dets = detect(text)
        assert len(default_dets) == 1
        assert default_dets[0].type == "IR_NATIONAL_ID"

        # Explicit EmailDetector detects ONLY Email
        email_dets = detect(text, detectors=[EmailDetector()])
        assert len(email_dets) == 1
        assert email_dets[0].type == "EMAIL"


class TestEmailRedactionIntegration:
    """Test redact() with EmailDetector."""

    def test_single_email_redaction(self) -> None:
        text = "ایمیل بیمار alice@example.com است."
        result = redact(text, detectors=[EmailDetector()])
        assert result == "ایمیل بیمار [EMAIL_1] است."

    def test_repeated_exact_email_shares_placeholder(self) -> None:
        text = "تماس ۱: alice@example.com، تماس ۲: alice@example.com"
        result = redact(text, detectors=[EmailDetector()])
        assert result == "تماس ۱: [EMAIL_1]، تماس ۲: [EMAIL_1]"

    def test_distinct_emails_receive_distinct_placeholders(self) -> None:
        text = "اصلی: alice@example.com، جایگزین: bob@example.com"
        result = redact(text, detectors=[EmailDetector()])
        assert result == "اصلی: [EMAIL_1]، جایگزین: [EMAIL_2]"

    def test_case_difference_remains_distinct(self) -> None:
        text = "ایمیل ۱: alice@example.com، ایمیل ۲: Alice@example.com"
        result = redact(text, detectors=[EmailDetector()])
        assert result == "ایمیل ۱: [EMAIL_1]، ایمیل ۲: [EMAIL_2]"

    def test_plus_tag_difference_remains_distinct(self) -> None:
        text = "عمومی: alice@example.com، برچسب‌دار: alice+urgent@example.com"
        result = redact(text, detectors=[EmailDetector()])
        assert result == "عمومی: [EMAIL_1]، برچسب‌دار: [EMAIL_2]"


class TestEmailPseudonymizationSessionIntegration:
    """Test PseudonymizationSession stateful workflow with EmailDetector."""

    def test_pseudonymize_and_restore_workflow(self) -> None:
        session = PseudonymizationSession()

        prompt = "تماس با بیمار alice@example.com ثبت گردید."
        pseudonymized_prompt = session.pseudonymize(prompt, detectors=[EmailDetector()])
        assert pseudonymized_prompt == "تماس با بیمار [EMAIL_1] ثبت گردید."
        assert session.mapping == {"[EMAIL_1]": "alice@example.com"}

        llm_response = "جهت پیگیری به [EMAIL_1] پیام ارسال شود."
        restored = session.restore(llm_response)
        assert restored == "جهت پیگیری به alice@example.com پیام ارسال شود."

    def test_cross_call_stability(self) -> None:
        session = PseudonymizationSession()

        turn1 = session.pseudonymize(
            "ورودی ۱: alice@example.com", detectors=[EmailDetector()]
        )
        assert turn1 == "ورودی ۱: [EMAIL_1]"

        turn2 = session.pseudonymize(
            "ورودی ۲: alice@example.com", detectors=[EmailDetector()]
        )
        assert turn2 == "ورودی ۲: [EMAIL_1]"

        turn3 = session.pseudonymize(
            "ورودی ۳: bob@example.org", detectors=[EmailDetector()]
        )
        assert turn3 == "ورودی ۳: [EMAIL_2]"


class TestEmailOverlapRegression:
    """Test explicit overlap behavior between Email and Mobile detectors."""

    def test_overlapping_email_and_mobile_in_detect(self) -> None:
        # 09123456789 is a valid Iranian mobile number
        # 09123456789@example.com is a valid email whose local part is a mobile number
        text = "آدرس تماس: 09123456789@example.com"
        detectors: list[Detector] = [
            IranianMobileNumberDetector(),
            EmailDetector(),
        ]

        detections = detect(text, detectors=detectors)
        # detect() allows overlapping detections
        assert len(detections) == 2
        types = {d.type for d in detections}
        assert types == {"IR_MOBILE", "EMAIL"}

    def test_overlapping_email_and_mobile_fails_in_redact(self) -> None:
        text = "آدرس تماس: 09123456789@example.com"
        detectors: list[Detector] = [
            IranianMobileNumberDetector(),
            EmailDetector(),
        ]

        with pytest.raises(ValueError, match="(?i)overlapping"):
            redact(text, detectors=detectors)

    def test_overlapping_email_and_mobile_fails_in_pseudonymize(self) -> None:
        text = "آدرس تماس: 09123456789@example.com"
        detectors: list[Detector] = [
            IranianMobileNumberDetector(),
            EmailDetector(),
        ]
        session = PseudonymizationSession()

        with pytest.raises(ValueError, match="(?i)overlapping"):
            session.pseudonymize(text, detectors=detectors)
