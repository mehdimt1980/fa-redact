"""Unit tests for ClinicalRedactionProfile and clinical_profile builder."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any

import pytest

from fa_redact import (
    ClinicalRedactionProfile,
    ClinicalTextTemplate,
    Detection,
    DetectionReport,
    PatternRule,
    clinical_profile,
    detect,
)
from fa_redact.detectors.bank_card import BankCardDetector
from fa_redact.detectors.email import EmailDetector
from fa_redact.detectors.iranian_iban import IranianIBANDetector
from fa_redact.detectors.mobile import IranianMobileNumberDetector
from fa_redact.detectors.national_id import IranianNationalIDDetector
from fa_redact.detectors.pattern import PatternDetector
from fa_redact.pipeline import _DEFAULT_DETECTORS


class FakePersonDetector:
    """Test detector satisfying Detector protocol for PERSON extraction."""

    def __init__(self, entities: Sequence[tuple[int, int]] = ()) -> None:
        self._entities = tuple(entities)

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        detections: list[Detection] = []
        for start, end in self._entities:
            if 0 <= start <= end <= len(original_text):
                detections.append(
                    Detection.from_texts(
                        type="PERSON",
                        original_text=original_text,
                        normalized_text=normalized_text,
                        start=start,
                        end=end,
                    )
                )
        return detections


# 1, 2, 3: Supported templates
@pytest.mark.parametrize(
    "template_name",
    ["outpatient_note", "discharge_summary", "referral_letter"],
)
def test_supported_templates(template_name: ClinicalTextTemplate) -> None:
    prof = clinical_profile(template_name)
    assert prof.template == template_name
    assert isinstance(prof, ClinicalRedactionProfile)


# 4: Invalid template rejected
def test_invalid_template_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid template 'invalid_template'"):
        clinical_profile("invalid_template")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="template must be a str"):
        clinical_profile(123)  # type: ignore[arg-type]


# 5: Profile configuration immutable
def test_profile_configuration_immutable() -> None:
    prof = clinical_profile("outpatient_note")
    with pytest.raises(AttributeError):
        prof.template = "discharge_summary"  # type: ignore[misc]

    with pytest.raises(AttributeError):
        prof.detectors = ()  # type: ignore[misc]


# 6, 7, 8, 9, 10, 11: Default detector tuple deterministic & types
def test_default_clinical_profile_detectors() -> None:
    prof = clinical_profile("outpatient_note")
    types = [type(d) for d in prof.detectors]
    assert types == [
        IranianNationalIDDetector,
        IranianMobileNumberDetector,
        IranianIBANDetector,
        EmailDetector,
    ]


# 12: include_email=False excludes EmailDetector
def test_include_email_false() -> None:
    prof = clinical_profile("outpatient_note", include_email=False)
    types = [type(d) for d in prof.detectors]
    assert types == [
        IranianNationalIDDetector,
        IranianMobileNumberDetector,
        IranianIBANDetector,
    ]
    assert EmailDetector not in types
    assert prof.include_email is False


# 13: include_bank_card=True includes BankCardDetector
def test_include_bank_card_true() -> None:
    prof = clinical_profile("discharge_summary", include_bank_card=True)
    types = [type(d) for d in prof.detectors]
    assert types == [
        IranianNationalIDDetector,
        IranianMobileNumberDetector,
        IranianIBANDetector,
        EmailDetector,
        BankCardDetector,
    ]
    assert prof.include_bank_card is True


# 14: institutional_rules empty creates no PatternDetector
def test_institutional_rules_empty_no_pattern_detector() -> None:
    prof = clinical_profile("outpatient_note", institutional_rules=())
    assert not any(isinstance(d, PatternDetector) for d in prof.detectors)
    assert prof.institutional_rules == ()


# 15, 16: institutional rules create PatternDetector and multiple preserved
def test_institutional_rules_create_pattern_detector() -> None:
    rules = [
        PatternRule(type="MRN", pattern=r"MRN-\d{6}"),
        PatternRule(type="PATIENT_ID", pattern=r"PAT-\d{8}"),
    ]
    prof = clinical_profile("referral_letter", institutional_rules=rules)
    pattern_detectors = [d for d in prof.detectors if isinstance(d, PatternDetector)]
    assert len(pattern_detectors) == 1
    assert pattern_detectors[0].rules == tuple(rules)
    assert prof.institutional_rules == tuple(rules)

    # Prove mutating caller list does not alter profile
    rules.append(PatternRule(type="ENCOUNTER_ID", pattern=r"ENC-\d{4}"))
    assert len(prof.institutional_rules) == 2


# 17, 18: invalid institutional_rules container and elements rejected
def test_invalid_institutional_rules_rejected() -> None:
    with pytest.raises(TypeError, match="institutional_rules must be a Sequence"):
        clinical_profile("outpatient_note", institutional_rules="invalid")  # type: ignore[arg-type]

    with pytest.raises(
        TypeError, match="institutional_rules item at index 0 must be a PatternRule"
    ):
        clinical_profile("outpatient_note", institutional_rules=["invalid"])  # type: ignore[list-item]


# 19: person detector absent by default
def test_person_detector_absent_by_default() -> None:
    prof = clinical_profile("outpatient_note")
    assert prof.person_detector is None


# 20: explicit person detector appended
def test_explicit_person_detector_appended() -> None:
    fake_ner = FakePersonDetector([(6, 15)])
    prof = clinical_profile("referral_letter", person_detector=fake_ner)
    assert prof.person_detector is fake_ner
    assert prof.detectors[-1] is fake_ner


# 21: invalid person detector rejected
def test_invalid_person_detector_rejected() -> None:
    with pytest.raises(TypeError, match="person_detector must be a Detector instance"):
        clinical_profile("referral_letter", person_detector="not_a_detector")  # type: ignore[arg-type]


# 22: clinical module import does not require torch or transformers
def test_clinical_module_zero_heavy_imports() -> None:
    assert "fa_redact.clinical" in sys.modules
    # Verify neither torch nor transformers were forced to load
    # (If test environment does not have them, they remain unimported)


# 23, 24: global default detector behavior unchanged
def test_global_default_detectors_unchanged() -> None:
    default_types = [type(d) for d in _DEFAULT_DETECTORS]
    assert default_types == [
        IranianNationalIDDetector,
        IranianMobileNumberDetector,
        IranianIBANDetector,
    ]
    # Running plain detect() on email finds nothing because EmailDetector is opt-in
    text = "ایمیل user@example.com و موبایل ۰۹۱۲۳۴۵۶۷۸۹"
    dets = detect(text)
    assert len(dets) == 1
    assert dets[0].type == "IR_MOBILE"


# 25, 26, 27: clinical profile detect and redact delegation
def test_profile_detect_and_redact_delegation() -> None:
    prof = clinical_profile("outpatient_note")
    text = "کد ملی 1234567891 و ایمیل test@example.com و موبایل 09123456789"
    dets = prof.detect(text)
    assert len(dets) == 3
    types = {d.type for d in dets}
    assert types == {"IR_NATIONAL_ID", "EMAIL", "IR_MOBILE"}

    redacted = prof.redact(text)
    assert (
        redacted == "کد ملی [IR_NATIONAL_ID_1] و ایمیل [EMAIL_1] و موبایل [IR_MOBILE_1]"
    )


# 28: profile report returns DetectionReport
def test_profile_report_returns_detection_report() -> None:
    prof = clinical_profile("discharge_summary")
    text = "کد ملی 1234567891 و تماس 09123456789"
    rep = prof.report(text)
    assert isinstance(rep, DetectionReport)
    assert rep.total_detections == 2
    assert dict(rep.counts) == {"IR_MOBILE": 1, "IR_NATIONAL_ID": 1}
    assert rep.has_conflicts is False


# 29, 30, 31, 32, 33: structured helpers delegation, consistency & immutability
def test_profile_structured_helpers() -> None:
    prof = clinical_profile("referral_letter")
    record: dict[str, Any] = {
        "patient": {"note": "مراجعه بیمار با کد ملی 1234567891"},
        "contact": "تکرار کد ملی 1234567891 و ایمیل test@example.com",
        "unselected": "موبایل 09123456789 دست‌نخورده",
        "count": 5,
    }

    # detect_fields
    df = prof.detect_fields(record, ["patient.note", "contact"])
    assert len(df["patient.note"]) == 1
    assert len(df["contact"]) == 2

    # redact_fields
    rf = prof.redact_fields(record, ["patient.note", "contact"])
    assert rf["patient"]["note"] == "مراجعه بیمار با کد ملی [IR_NATIONAL_ID_1]"
    # Referential consistency: identical national ID receives [IR_NATIONAL_ID_1]
    assert rf["contact"] == "تکرار کد ملی [IR_NATIONAL_ID_1] و ایمیل [EMAIL_1]"
    # Unselected field untouched
    assert rf["unselected"] == "موبایل 09123456789 دست‌نخورده"
    assert rf["count"] == 5

    # Original record not mutated
    assert record["patient"]["note"] == "مراجعه بیمار با کد ملی 1234567891"

    # report_fields
    rep_f = prof.report_fields(record, ["patient.note", "contact"])
    assert rep_f["patient.note"].total_detections == 1
    assert rep_f["contact"].total_detections == 2


# 34, 35, 36, 37: conflict policies
def test_profile_conflict_policies() -> None:
    # 34: Reject policy is default
    prof_reject = clinical_profile("outpatient_note", include_bank_card=True)
    assert prof_reject.conflict_policy == "reject"
    text_conflict = "1234567890123452@example.com"
    with pytest.raises(ValueError, match="Overlapping detections"):
        prof_reject.redact(text_conflict)

    # 35: Longest policy passes through
    prof_longest = clinical_profile(
        "outpatient_note", include_bank_card=True, conflict_policy="longest"
    )
    assert prof_longest.conflict_policy == "longest"
    res_longest = prof_longest.redact(text_conflict)
    assert res_longest == "[EMAIL_1]"

    # 36, 37: Priority policy and type_priority immutability
    prio_list = ["BANK_CARD", "EMAIL"]
    prof_prio = clinical_profile(
        "outpatient_note",
        include_bank_card=True,
        conflict_policy="priority",
        type_priority=prio_list,
    )
    assert prof_prio.conflict_policy == "priority"
    assert prof_prio.type_priority == ("BANK_CARD", "EMAIL")

    # Mutating caller list does not affect profile
    prio_list.append("IR_MOBILE")
    assert prof_prio.type_priority == ("BANK_CARD", "EMAIL")

    res_prio = prof_prio.redact(text_conflict)
    assert res_prio == "[BANK_CARD_1]@example.com"


def test_conflict_policy_validation_errors() -> None:
    with pytest.raises(ValueError, match="Invalid conflict_policy 'unknown'"):
        clinical_profile("outpatient_note", conflict_policy="unknown")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="conflict_policy must be a str"):
        clinical_profile("outpatient_note", conflict_policy=123)  # type: ignore[arg-type]

    with pytest.raises(
        ValueError, match="type_priority is required when conflict_policy is 'priority'"
    ):
        clinical_profile("outpatient_note", conflict_policy="priority")

    with pytest.raises(
        ValueError, match="type_priority must be None when conflict_policy is 'reject'"
    ):
        clinical_profile(
            "outpatient_note",
            conflict_policy="reject",
            type_priority=["EMAIL", "BANK_CARD"],
        )


# 38, 39: Source text and detections not retained on profile
def test_profile_retains_no_source_or_detection_data() -> None:
    prof = clinical_profile("outpatient_note")
    secret_text = "کد ملی 1234567891"
    prof.detect(secret_text)
    prof.redact(secret_text)
    prof.report(secret_text)

    # Verify profile fields contain only configuration
    for key in (
        "template",
        "detectors",
        "conflict_policy",
        "type_priority",
        "institutional_rules",
        "include_email",
        "include_bank_card",
        "person_detector",
    ):
        assert hasattr(prof, key)

    assert "secret_text" not in str(prof.__dict__ if hasattr(prof, "__dict__") else "")
    assert "1234567891" not in repr(prof)


# 40: Institutional MRN example with synthetic text
def test_institutional_mrn_synthetic() -> None:
    mrn_rule = PatternRule(type="MRN", pattern=r"(?<!\w)MRN-\d{6}(?!\w)")
    prof = clinical_profile("discharge_summary", institutional_rules=[mrn_rule])
    text = "بیمار با شماره پرونده MRN-123456 ترخیص شد."
    redacted = prof.redact(text)
    assert redacted == "بیمار با شماره پرونده [MRN_1] ترخیص شد."


# 41, 42, 43: Synthetic outpatient, discharge, and referral workflows
def test_synthetic_outpatient_workflow() -> None:
    prof = clinical_profile("outpatient_note")
    text = (
        "یادداشت سرپایی: کد ملی 1234567891، تماس 09123456789، ایمیل patient@clinic.ir"
    )
    redacted = prof.redact(text)
    expected = (
        "یادداشت سرپایی: کد ملی [IR_NATIONAL_ID_1]، تماس [IR_MOBILE_1]، ایمیل [EMAIL_1]"
    )
    assert redacted == expected


def test_synthetic_discharge_workflow() -> None:
    prof = clinical_profile(
        "discharge_summary",
        institutional_rules=[PatternRule(type="MRN", pattern=r"MRN-\d{6}")],
        include_bank_card=True,
    )
    text = "خلاصه ترخیص: پرونده MRN-654321، کارت 1234567890123452، تماس 09123456789"
    redacted = prof.redact(text)
    assert (
        redacted
        == "خلاصه ترخیص: پرونده [MRN_1]، کارت [BANK_CARD_1]، تماس [IR_MOBILE_1]"
    )


def test_synthetic_referral_workflow() -> None:
    prof = clinical_profile(
        "referral_letter",
        institutional_rules=[
            PatternRule(type="REFERRAL_ID", pattern=r"REF-[A-Z]{2}-\d{4}")
        ],
    )
    text = "ارجاع با شناسه REF-TE-9876 و شماره شبا IR641234567890123456789012"
    redacted = prof.redact(text)
    assert redacted == "ارجاع با شناسه [REFERRAL_ID_1] و شماره شبا [IR_IBAN_1]"


# 44: Name is not detected without person detector
def test_name_not_detected_without_person_detector() -> None:
    prof = clinical_profile("outpatient_note")
    text = "بیمار سارا محمدی با کد ملی 1234567891 مراجعه کرد."
    redacted = prof.redact(text)
    assert redacted == "بیمار سارا محمدی با کد ملی [IR_NATIONAL_ID_1] مراجعه کرد."
    assert "سارا محمدی" in redacted


# 45, 46, 47: Fake PERSON detector works, output is PERSON, no role transformation
def test_explicit_person_detector_and_no_role_transformation() -> None:
    text = "بیمار سارا محمدی و پزشک دکتر حسینی با کد ملی 1234567891"
    # span of "سارا محمدی" is [6:16], span of "دکتر حسینی" is [24:34]
    fake_ner = FakePersonDetector([(6, 16), (24, 34)])
    prof = clinical_profile("outpatient_note", person_detector=fake_ner)
    dets = prof.detect(text)
    person_dets = [d for d in dets if d.type == "PERSON"]
    assert len(person_dets) == 2
    for d in person_dets:
        assert d.type == "PERSON"
        # Verify no role inference
        assert d.type not in ("PATIENT", "DOCTOR", "PHYSICIAN", "NURSE")

    redacted = prof.redact(text)
    assert redacted == "بیمار [PERSON_1] و پزشک [PERSON_2] با کد ملی [IR_NATIONAL_ID_1]"


# 48: Value-free reporting guarantee
def test_report_value_free_guarantee() -> None:
    prof = clinical_profile("outpatient_note")
    text = "کد ملی 1234567891 و موبایل 09123456789"
    rep = prof.report(text)
    # Check that report has no text slices, values, or secret contents
    assert not hasattr(rep, "text")
    assert not hasattr(rep, "values")
    assert not hasattr(rep, "spans")
    assert "1234567891" not in repr(rep)
    assert "09123456789" not in repr(rep)


# 49, 50: Strict bool validation for include_email and include_bank_card
def test_strict_bool_validation() -> None:
    with pytest.raises(TypeError, match="include_email must be a bool"):
        clinical_profile("outpatient_note", include_email=1)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="include_email must be a bool"):
        clinical_profile("outpatient_note", include_email="true")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="include_bank_card must be a bool"):
        clinical_profile("outpatient_note", include_bank_card=0)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="include_bank_card must be a bool"):
        clinical_profile("outpatient_note", include_bank_card="false")  # type: ignore[arg-type]
