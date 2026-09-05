"""Tests for stateful pseudonymization sessions (Phase 8)."""

from collections.abc import Sequence

import pytest

from fa_redact import (
    Detection,
    IranianNationalIDDetector,
    PseudonymizationSession,
    redact,
)


def test_fresh_session_empty_mapping() -> None:
    """Verify a new session has an empty mapping."""
    session = PseudonymizationSession()
    assert session.mapping == {}


def test_pseudonymize_single_mobile() -> None:
    """Verify pseudonymizing a single mobile creates mapping."""
    session = PseudonymizationSession()
    text = "شماره: ۰۹۱۲۳۴۵۶۷۸۹"
    result = session.pseudonymize(text)
    assert result == "شماره: [IR_MOBILE_1]"
    assert session.mapping == {"[IR_MOBILE_1]": "۰۹۱۲۳۴۵۶۷۸۹"}


def test_pseudonymize_single_national_id() -> None:
    """Verify pseudonymizing a single National ID creates mapping."""
    session = PseudonymizationSession()
    text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱"
    result = session.pseudonymize(text)
    assert result == "کد ملی: [IR_NATIONAL_ID_1]"
    assert session.mapping == {"[IR_NATIONAL_ID_1]": "۱۲۳۴۵۶۷۸۹۱"}


def test_pseudonymize_multiple_entity_types() -> None:
    """Verify independent per-type counters across multiple entity types."""
    session = PseudonymizationSession()
    text = "کد: ۱۲۳۴۵۶۷۸۹۱ و همراه: ۰۹۱۲۳۴۵۶۷۸۹"
    result = session.pseudonymize(text)
    assert result == "کد: [IR_NATIONAL_ID_1] و همراه: [IR_MOBILE_1]"
    assert session.mapping == {
        "[IR_NATIONAL_ID_1]": "۱۲۳۴۵۶۷۸۹۱",
        "[IR_MOBILE_1]": "۰۹۱۲۳۴۵۶۷۸۹",
    }


def test_multiple_calls_preserve_stable_mapping() -> None:
    """Verify same normalized identity across calls reuses stable placeholder."""
    session = PseudonymizationSession()
    res1 = session.pseudonymize("بیمار اول: ۰۹۱۲۳۴۵۶۷۸۹")
    assert res1 == "بیمار اول: [IR_MOBILE_1]"

    # Second call with ASCII digits for same number
    res2 = session.pseudonymize("پیگیری مجدد: 09123456789")
    assert res2 == "پیگیری مجدد: [IR_MOBILE_1]"

    # Mapping retained first observed representation
    assert session.mapping == {"[IR_MOBILE_1]": "۰۹۱۲۳۴۵۶۷۸۹"}


def test_counters_continue_across_calls() -> None:
    """Verify new identities receive subsequent indexes across multiple calls."""
    session = PseudonymizationSession()
    session.pseudonymize("تماس ۱: 09123456789")
    res2 = session.pseudonymize("تماس ۲: 09351234567")
    assert res2 == "تماس ۲: [IR_MOBILE_2]"

    res3 = session.pseudonymize("تماس ۳: 09901234567")
    assert res3 == "تماس ۳: [IR_MOBILE_3]"

    assert len(session.mapping) == 3


def test_first_observed_raw_value_retained_persian_first() -> None:
    """Verify first observed Persian representation is preserved when ASCII follows."""
    session = PseudonymizationSession()
    session.pseudonymize("نوبت اول: ۰۹۱۲۳۴۵۶۷۸۹")
    session.pseudonymize("نوبت دوم: 09123456789")
    assert session.mapping["[IR_MOBILE_1]"] == "۰۹۱۲۳۴۵۶۷۸۹"


def test_first_observed_raw_value_retained_ascii_first() -> None:
    """Verify first observed ASCII representation is preserved when Persian follows."""
    session = PseudonymizationSession()
    session.pseudonymize("نوبت اول: 09123456789")
    session.pseudonymize("نوبت دوم: ۰۹۱۲۳۴۵۶۷۸۹")
    assert session.mapping["[IR_MOBILE_1]"] == "09123456789"


def test_restore_basic_behavior() -> None:
    """Verify restore replaces placeholder inside modified response prose."""
    session = PseudonymizationSession()
    session.pseudonymize("شماره تماس: ۰۹۱۲۳۴۵۶۷۸۹")

    response = "پاسخ هوش مصنوعی: با [IR_MOBILE_1] تماس بگیرید."
    restored = session.restore(response)
    assert restored == "پاسخ هوش مصنوعی: با ۰۹۱۲۳۴۵۶۷۸۹ تماس بگیرید."


def test_restore_placeholder_repeated() -> None:
    """Verify restore replaces all occurrences of a placeholder in response."""
    session = PseudonymizationSession()
    session.pseudonymize("کد ملی: ۱۲۳۴۵۶۷۸۹۱")

    response = "بیمار [IR_NATIONAL_ID_1] با شناسه [IR_NATIONAL_ID_1] ترخیص شد."
    restored = session.restore(response)
    assert restored == "بیمار ۱۲۳۴۵۶۷۸۹۱ با شناسه ۱۲۳۴۵۶۷۸۹۱ ترخیص شد."


def test_restore_placeholder_removed() -> None:
    """Verify restore handles responses where some placeholders are omitted."""
    session = PseudonymizationSession()
    session.pseudonymize("کد ملی: ۱۲۳۴۵۶۷۸۹۱، تلفن: ۰۹۱۲۳۴۵۶۷۸۹")

    # LLM response mentions only mobile
    response = "پیام به [IR_MOBILE_1] ارسال شد."
    restored = session.restore(response)
    assert restored == "پیام به ۰۹۱۲۳۴۵۶۷۸۹ ارسال شد."


def test_restore_unknown_placeholder_unchanged() -> None:
    """Verify unmapped or unknown placeholders remain untouched."""
    session = PseudonymizationSession()
    session.pseudonymize("شماره: ۰۹۱۲۳۴۵۶۷۸۹")

    response = "شماره اول [IR_MOBILE_1] و شماره ناشناس [IR_MOBILE_999]."
    restored = session.restore(response)
    assert restored == "شماره اول ۰۹۱۲۳۴۵۶۷۸۹ و شماره ناشناس [IR_MOBILE_999]."


def test_restore_exact_matching_no_prefix_corruption() -> None:
    """Verify similarly named placeholders are not partially matched."""
    session = PseudonymizationSession()
    session.pseudonymize("شماره: ۰۹۱۲۳۴۵۶۷۸۹")  # assigns [IR_MOBILE_1]

    # Response contains [IR_MOBILE_1_EXTRA] which is not mapped
    response = "مقدار [IR_MOBILE_1_EXTRA] نباید تغییر کند ولی [IR_MOBILE_1] باید."
    restored = session.restore(response)
    assert restored == "مقدار [IR_MOBILE_1_EXTRA] نباید تغییر کند ولی ۰۹۱۲۳۴۵۶۷۸۹ باید."


def test_restore_non_cascading_protection() -> None:
    """Verify restored text containing placeholders is not recursively restored."""

    class TrickyDetector:
        """Custom detector returning raw value that looks like another placeholder."""

        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            # Detects "SECRET_A" as TYPE_A
            if "SECRET_A" in original_text:
                start = original_text.index("SECRET_A")
                return [
                    Detection.from_texts(
                        type="TYPE_A",
                        original_text=original_text,
                        normalized_text=normalized_text,
                        start=start,
                        end=start + len("SECRET_A"),
                    )
                ]
            return []

    class SecondDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            # Raw value is literally "[TYPE_A_1]" with matching span length (10)
            target = "0123456789"
            if target in original_text:
                start = original_text.index(target)
                return [
                    Detection(
                        type="TYPE_B",
                        start=start,
                        end=start + len(target),
                        value="[TYPE_A_1]",
                        normalized_value="0123456789",
                    )
                ]
            return []

    session = PseudonymizationSession()
    session.pseudonymize("مقدار: SECRET_A", detectors=[TrickyDetector()])
    session.pseudonymize("مقدار دوم: 0123456789", detectors=[SecondDetector()])

    # Mapping: [TYPE_A_1] -> SECRET_A, [TYPE_B_1] -> [TYPE_A_1]
    # Restoring "[TYPE_B_1]" should become "[TYPE_A_1]", NOT cascading into "SECRET_A"
    restored = session.restore("نتیجه: [TYPE_B_1]")
    assert restored == "نتیجه: [TYPE_A_1]"


def test_restore_empty_mapping() -> None:
    """Verify restore on fresh session returns text unchanged."""
    session = PseudonymizationSession()
    text = "متن بدون تغییر [IR_MOBILE_1]"
    assert session.restore(text) == text


def test_mapping_property_returns_isolated_copy() -> None:
    """Verify mutating returned mapping does not affect session internal state."""
    session = PseudonymizationSession()
    session.pseudonymize("شماره: ۰۹۱۲۳۴۵۶۷۸۹")

    snapshot = session.mapping
    assert "[IR_MOBILE_1]" in snapshot
    snapshot.clear()

    # Internal session mapping must still have the item
    assert "[IR_MOBILE_1]" in session.mapping
    assert session.restore("[IR_MOBILE_1]") == "۰۹۱۲۳۴۵۶۷۸۹"


def test_pseudonymize_explicit_empty_detectors() -> None:
    """Verify detectors=[] leaves text and mapping unchanged."""
    session = PseudonymizationSession()
    text = "کد ۱۲۳۴۵۶۷۸۹۱ و همراه ۰۹۱۲۳۴۵۶۷۸۹"
    res = session.pseudonymize(text, detectors=[])
    assert res == text
    assert session.mapping == {}


def test_pseudonymize_custom_detector() -> None:
    """Verify custom detector works in pseudonymize and restore."""

    class PatientCodeDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            key = "PAT-99"
            if key in original_text:
                idx = original_text.index(key)
                return [
                    Detection.from_texts(
                        type="PATIENT_CODE",
                        original_text=original_text,
                        normalized_text=normalized_text,
                        start=idx,
                        end=idx + len(key),
                    )
                ]
            return []

    session = PseudonymizationSession()
    res = session.pseudonymize(
        "بیمار با شناسه PAT-99 مراجعه کرد.",
        detectors=[PatientCodeDetector()],
    )
    assert res == "بیمار با شناسه [PATIENT_CODE_1] مراجعه کرد."
    assert session.mapping == {"[PATIENT_CODE_1]": "PAT-99"}

    restored = session.restore("گزارش ترخیص [PATIENT_CODE_1]")
    assert restored == "گزارش ترخیص PAT-99"


def test_pseudonymize_overlap_error_leaves_session_state_untouched() -> None:
    """Verify overlap error causes no partial state changes."""

    class OverlapDetector:
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
                ),
                Detection.from_texts(
                    type="SPAN_B",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=3,
                    end=8,
                ),
            ]

    session = PseudonymizationSession()
    session.pseudonymize("شماره قبلی: 09123456789")
    assert len(session.mapping) == 1

    with pytest.raises(ValueError, match=r"Overlapping detections at spans"):
        session.pseudonymize("0123456789", detectors=[OverlapDetector()])

    # Session mapping must remain exactly 1 entry
    assert len(session.mapping) == 1
    assert list(session.mapping.keys()) == ["[IR_MOBILE_1]"]


def test_pseudonymize_duplicate_detector_error_leaves_state_untouched() -> None:
    """Verify duplicate detector error causes no state changes."""
    session = PseudonymizationSession()
    nid = IranianNationalIDDetector()
    with pytest.raises(ValueError, match=r"Overlapping detections at spans"):
        session.pseudonymize("کد: 1234567891", detectors=[nid, nid])

    assert session.mapping == {}


def test_pseudonymize_detector_exception_propagates_and_state_untouched() -> None:
    """Verify detector exception propagates and leaves state untouched."""

    class FailingDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            raise RuntimeError("detector crashed")

    session = PseudonymizationSession()
    with pytest.raises(RuntimeError, match="detector crashed"):
        session.pseudonymize("متن تست", detectors=[FailingDetector()])

    assert session.mapping == {}


def test_pseudonymize_literal_new_placeholder_collision() -> None:
    """Verify existing literal placeholder in source text is skipped."""
    session = PseudonymizationSession()
    text = "یادداشت: [IR_MOBILE_1]، شماره: 09123456789"
    res = session.pseudonymize(text)
    assert res == "یادداشت: [IR_MOBILE_1]، شماره: [IR_MOBILE_2]"
    assert session.mapping == {"[IR_MOBILE_2]": "09123456789"}


def test_pseudonymize_existing_mapped_placeholder_collision_raises() -> None:
    """Verify input containing an already mapped placeholder raises ValueError."""
    session = PseudonymizationSession()
    session.pseudonymize("شماره: 09123456789")  # maps [IR_MOBILE_1]

    # Subsequent raw text literally contains "[IR_MOBILE_1]"
    text = "پیام دریافتی شامل [IR_MOBILE_1] است."
    with pytest.raises(ValueError) as excinfo:
        session.pseudonymize(text)

    msg = str(excinfo.value)
    expected_msg = (
        "Input contains a placeholder already assigned by this session: [IR_MOBILE_1]"
    )
    assert expected_msg in msg
    # Verify no surrounding text is leaked:
    assert "پیام دریافتی" not in msg


def test_multiple_sessions_isolated() -> None:
    """Verify independent sessions maintain separate states and mappings."""
    session_a = PseudonymizationSession()
    session_b = PseudonymizationSession()

    res_a = session_a.pseudonymize("همراه: 09123456789")
    res_b = session_b.pseudonymize("همراه: 09351234567")

    assert res_a == "همراه: [IR_MOBILE_1]"
    assert res_b == "همراه: [IR_MOBILE_1]"

    assert session_a.mapping == {"[IR_MOBILE_1]": "09123456789"}
    assert session_b.mapping == {"[IR_MOBILE_1]": "09351234567"}

    # Restoring with session_a vs session_b produces different results
    assert session_a.restore("[IR_MOBILE_1]") == "09123456789"
    assert session_b.restore("[IR_MOBILE_1]") == "09351234567"


def test_non_string_inputs_raise_type_error() -> None:
    """Verify non-string inputs raise TypeError for pseudonymize and restore."""
    session = PseudonymizationSession()

    with pytest.raises(TypeError, match="text must be a str"):
        session.pseudonymize(None)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="text must be a str"):
        session.pseudonymize(123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="text must be a str"):
        session.restore(None)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="text must be a str"):
        session.restore(456)  # type: ignore[arg-type]


def test_stateless_redact_regression_restarts_numbering() -> None:
    """Verify calling redact() independently still restarts numbering each call."""
    res1 = redact("تماس: 09123456789")
    res2 = redact("تماس دیگر: 09351234567")

    assert res1 == "تماس: [IR_MOBILE_1]"
    assert res2 == "تماس دیگر: [IR_MOBILE_1]"


def test_healthcare_llm_flow_synthetic() -> None:
    """Verify end-to-end synthetic healthcare/LLM workflow."""
    session = PseudonymizationSession()

    # Step 1: Clinical prompt with identifiers
    clinical_note = (
        "پرونده پذیرش بیمار:\n"
        "بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره همراه ۰۹۱۲۳۴۵۶۷۸۹ مراجعه کرد.\n"
        "علائم: سردرد و تب ۳۸ درجه.\n"
        "تشخیص احتمالی: سینوزیت حاد.\n"
        "شماره تماس همراه بیمار جهت پیگیری: 09123456789.\n"
    )

    safe_prompt = session.pseudonymize(clinical_note)

    # Verify clinical terms are intact and identifiers replaced
    assert "سینوزیت حاد" in safe_prompt
    assert "سردرد و تب ۳۸ درجه" in safe_prompt
    assert "۱۲۳۴۵۶۷۸۹۱" not in safe_prompt
    assert "۰۹۱۲۳۴۵۶۷۸۹" not in safe_prompt
    assert "[IR_NATIONAL_ID_1]" in safe_prompt
    assert "[IR_MOBILE_1]" in safe_prompt

    # Step 2: Simulated LLM response containing placeholders in altered structure
    simulated_llm_response = (
        "خلاصه بالینی:\n"
        "برای بیمار با کد ملی [IR_NATIONAL_ID_1]، داروی استامینوفن تجویز شد.\n"
        "لطفاً دستور دارویی به شماره [IR_MOBILE_1] پیامک شود."
    )

    # Step 3: Local restoration
    restored_output = session.restore(simulated_llm_response)

    expected_part = "برای بیمار با کد ملی ۱۲۳۴۵۶۷۸۹۱، داروی استامینوفن تجویز شد."
    assert expected_part in restored_output
    assert "لطفاً دستور دارویی به شماره ۰۹۱۲۳۴۵۶۷۸۹ پیامک شود." in restored_output
    assert "[IR_NATIONAL_ID_1]" not in restored_output
    assert "[IR_MOBILE_1]" not in restored_output


def test_cross_call_reserved_placeholder_collision_and_restore() -> None:
    """Verify literal placeholder from earlier call is not reused in later call."""
    session = PseudonymizationSession()
    old_output = session.pseudonymize("یادداشت: [IR_MOBILE_2]، تماس: 09123456789")
    assert old_output == "یادداشت: [IR_MOBILE_2]، تماس: [IR_MOBILE_1]"

    new_output = session.pseudonymize("تماس جدید: 09351234567")
    assert new_output == "تماس جدید: [IR_MOBILE_3]"

    restored = session.restore(old_output)
    assert restored == "یادداشت: [IR_MOBILE_2]، تماس: 09123456789"


def test_no_pii_call_reserves_literal_placeholder() -> None:
    """Verify call without PII reserves literal placeholder for subsequent calls."""
    session = PseudonymizationSession()
    res1 = session.pseudonymize("این متن شامل [IR_MOBILE_1] است.")
    assert res1 == "این متن شامل [IR_MOBILE_1] است."
    assert session.mapping == {}

    res2 = session.pseudonymize("تماس: 09123456789")
    assert res2 == "تماس: [IR_MOBILE_2]"
    assert session.mapping == {"[IR_MOBILE_2]": "09123456789"}


def test_empty_detectors_call_reserves_literal_placeholder() -> None:
    """Verify detectors=[] reserves literal placeholders."""
    session = PseudonymizationSession()
    res1 = session.pseudonymize("متن [IR_MOBILE_1]", detectors=[])
    assert res1 == "متن [IR_MOBILE_1]"
    assert session.mapping == {}

    res2 = session.pseudonymize("تماس: 09123456789")
    assert res2 == "تماس: [IR_MOBILE_2]"


def test_multiple_historical_reserved_placeholders() -> None:
    """Verify multiple historical reserved placeholders are skipped."""
    session = PseudonymizationSession()
    session.pseudonymize("متن با [IR_MOBILE_1] و [IR_MOBILE_2] و [IR_MOBILE_4]")
    # New mobile 1 -> [IR_MOBILE_3]
    res1 = session.pseudonymize("شماره ۱: 09123456789")
    assert res1 == "شماره ۱: [IR_MOBILE_3]"
    # New mobile 2 -> [IR_MOBILE_5]
    res2 = session.pseudonymize("شماره ۲: 09351234567")
    assert res2 == "شماره ۲: [IR_MOBILE_5]"


def test_reserved_placeholders_are_session_local() -> None:
    """Verify reserved placeholders are isolated per session."""
    session_a = PseudonymizationSession()
    session_b = PseudonymizationSession()

    session_a.pseudonymize("متن با [IR_MOBILE_1]")
    res_a = session_a.pseudonymize("تماس: 09123456789")
    assert res_a == "تماس: [IR_MOBILE_2]"

    # session_b did not see [IR_MOBILE_1], so it assigns [IR_MOBILE_1]
    res_b = session_b.pseudonymize("تماس: 09123456789")
    assert res_b == "تماس: [IR_MOBILE_1]"


def test_reserved_placeholders_not_in_public_mapping() -> None:
    """Verify session.mapping contains only assigned placeholders."""
    session = PseudonymizationSession()
    session.pseudonymize("یادداشت: [IR_MOBILE_2]، تماس: 09123456789")
    assert session.mapping == {"[IR_MOBILE_1]": "09123456789"}
    assert "[IR_MOBILE_2]" not in session.mapping


def test_failed_detector_call_does_not_reserve_literal() -> None:
    """Verify failing call does not commit newly observed reserved literals."""

    class FailingDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            raise RuntimeError("boom")

    session = PseudonymizationSession()
    with pytest.raises(RuntimeError):
        session.pseudonymize("متن با [IR_MOBILE_1]", detectors=[FailingDetector()])

    # Later call can still use [IR_MOBILE_1]
    res = session.pseudonymize("تماس: 09123456789")
    assert res == "تماس: [IR_MOBILE_1]"


def test_overlap_failure_does_not_reserve_literal() -> None:
    """Verify overlap failure does not commit reserved literals."""

    class OverlapDetector:
        def detect(
            self, original_text: str, normalized_text: str
        ) -> Sequence[Detection]:
            return [
                Detection.from_texts(
                    type="SPAN_A",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=0,
                    end=4,
                ),
                Detection.from_texts(
                    type="SPAN_B",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=2,
                    end=6,
                ),
            ]

    session = PseudonymizationSession()
    with pytest.raises(ValueError, match=r"Overlapping detections at spans"):
        session.pseudonymize("0123456789 [IR_MOBILE_1]", detectors=[OverlapDetector()])

    res = session.pseudonymize("تماس: 09123456789")
    assert res == "تماس: [IR_MOBILE_1]"


def test_existing_assigned_placeholder_conflict_leaves_state_unchanged() -> None:
    """Verify assigned placeholder conflict error does not corrupt session state."""
    session = PseudonymizationSession()
    session.pseudonymize("تماس: 09123456789")  # maps [IR_MOBILE_1]
    assert session.mapping == {"[IR_MOBILE_1]": "09123456789"}

    with pytest.raises(
        ValueError, match=r"Input contains a placeholder already assigned"
    ):
        session.pseudonymize("پیام با [IR_MOBILE_1] و [IR_MOBILE_5]")

    # State unchanged: [IR_MOBILE_5] was not reserved because the call failed
    res = session.pseudonymize("تماس ۲: 09351234567")
    assert res == "تماس ۲: [IR_MOBILE_2]"


def test_restore_ignores_reserved_literals() -> None:
    """Verify restore replaces assigned placeholders but leaves reserved literals."""
    session = PseudonymizationSession()
    session.pseudonymize("متن [IR_MOBILE_2] و شماره: 09123456789")

    restored = session.restore("پاسخ: [IR_MOBILE_1] / [IR_MOBILE_2]")
    assert restored == "پاسخ: 09123456789 / [IR_MOBILE_2]"


def test_pseudonymize_iban_cross_script_identity_and_first_observed_restoration() -> (
    None
):
    """Verify cross-script IBAN identity reuse and first-observed raw restoration."""
    session = PseudonymizationSession()

    # First turn: Persian digits representation
    turn1 = session.pseudonymize("شبا ۱: IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲")
    assert turn1 == "شبا ۱: [IR_IBAN_1]"
    assert session.mapping == {"[IR_IBAN_1]": "IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲"}

    # Second turn: ASCII digits representation for the same IBAN
    turn2 = session.pseudonymize("شبا مجدد: IR641234567890123456789012")
    assert turn2 == "شبا مجدد: [IR_IBAN_1]"

    # Restoration recovers the first-observed Persian representation
    restored = session.restore("حساب [IR_IBAN_1] تایید گردید.")
    assert restored == "حساب IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲ تایید گردید."


def test_pseudonymize_multiple_distinct_ibans() -> None:
    """Verify multiple distinct IBANs receive independent sequential placeholders."""
    session = PseudonymizationSession()
    text = "شبا اول: IR641234567890123456789012 و شبا دوم: IR220000000000000000000001"
    result = session.pseudonymize(text)
    assert result == "شبا اول: [IR_IBAN_1] و شبا دوم: [IR_IBAN_2]"
    assert session.mapping == {
        "[IR_IBAN_1]": "IR641234567890123456789012",
        "[IR_IBAN_2]": "IR220000000000000000000001",
    }
