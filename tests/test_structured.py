"""Tests for structured data helpers in fa-redact."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

import pytest

from fa_redact import (
    BankCardDetector,
    DetectionReport,
    Detector,
    EmailDetector,
    IranianNationalIDDetector,
    PatternDetector,
    PatternRule,
    detect_fields,
    redact_fields,
    report_fields,
)

# --- 1. Basic Single and Multiple Field Processing ---


def test_detect_fields_single_top_level() -> None:
    """Verify detect_fields on a single top-level field."""
    record = {
        "name": "سارا",
        "note": "کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره ۰۹۱۲۳۴۵۶۷۸۹",
        "age": 30,
    }
    results = detect_fields(record, ["note"])
    assert "note" in results
    assert len(results["note"]) == 2
    types = [d.type for d in results["note"]]
    assert types == ["IR_NATIONAL_ID", "IR_MOBILE"]
    assert "name" not in results
    assert "age" not in results


def test_redact_fields_single_top_level() -> None:
    """Verify redact_fields on a single top-level field."""
    record = {
        "name": "سارا",
        "note": "کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره ۰۹۱۲۳۴۵۶۷۸۹",
        "age": 30,
    }
    redacted = redact_fields(record, ["note"])
    assert "[IR_NATIONAL_ID_1]" in redacted["note"]
    assert "[IR_MOBILE_1]" in redacted["note"]
    assert redacted["name"] == "سارا"
    assert redacted["age"] == 30


def test_report_fields_single_top_level() -> None:
    """Verify report_fields on a single top-level field."""
    record = {
        "name": "سارا",
        "note": "کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره ۰۹۱۲۳۴۵۶۷۸۹",
        "age": 30,
    }
    reports = report_fields(record, ["note"])
    assert "note" in reports
    report = reports["note"]
    assert isinstance(report, DetectionReport)
    assert report.total_detections == 2
    assert report.counts["IR_NATIONAL_ID"] == 1
    assert report.counts["IR_MOBILE"] == 1
    assert "۱۲۳۴۵۶۷۸۹۱" not in repr(report)
    assert "۰۹۱۲۳۴۵۶۷۸۹" not in repr(report)


def test_multiple_top_level_and_nested_fields() -> None:
    """Verify processing multiple top-level and nested fields in one call."""
    record = {
        "patient_id": "کد ملی ۱۲۳۴۵۶۷۸۹۱",
        "note": "تماس با ۰۹۱۲۳۴۵۶۷۸۹",
        "metadata": {
            "contact": "شبا IR641234567890123456789012",
            "visit_count": 4,
        },
        "active": True,
    }
    fields = ["patient_id", "note", "metadata.contact"]

    # Detect
    detections = detect_fields(record, fields)
    assert set(detections.keys()) == set(fields)
    assert detections["patient_id"][0].type == "IR_NATIONAL_ID"
    assert detections["note"][0].type == "IR_MOBILE"
    assert detections["metadata.contact"][0].type == "IR_IBAN"

    # Redact
    redacted = redact_fields(record, fields)
    assert "[IR_NATIONAL_ID_1]" in redacted["patient_id"]
    assert "[IR_MOBILE_1]" in redacted["note"]
    assert "[IR_IBAN_1]" in redacted["metadata"]["contact"]
    assert redacted["metadata"]["visit_count"] == 4
    assert redacted["active"] is True

    # Report
    reports = report_fields(record, fields)
    assert set(reports.keys()) == set(fields)
    assert reports["patient_id"].total_detections == 1
    assert reports["note"].total_detections == 1
    assert reports["metadata.contact"].total_detections == 1


def test_deeply_nested_paths() -> None:
    """Verify deep path navigation (e.g. a.b.c.d)."""
    record = {
        "level1": {
            "level2": {
                "level3": {
                    "secret": "شماره همراه ۰۹۱۲۳۴۵۶۷۸۹",
                    "sibling": 999,
                },
                "other2": "unmodified",
            },
            "other1": "unmodified",
        }
    }
    redacted = redact_fields(record, ["level1.level2.level3.secret"])
    assert "[IR_MOBILE_1]" in redacted["level1"]["level2"]["level3"]["secret"]
    assert redacted["level1"]["level2"]["level3"]["sibling"] == 999
    assert redacted["level1"]["level2"]["other2"] == "unmodified"
    assert redacted["level1"]["other1"] == "unmodified"


# --- 2. Immutability and Non-Destructive Behavior ---


def test_original_input_not_mutated() -> None:
    """Verify caller input mapping and nested structures are not mutated."""
    original_contact = "تماس ۰۹۱۲۳۴۵۶۷۸۹"
    original_meta = {"contact": original_contact, "tags": [1, 2, 3]}
    record: dict[str, Any] = {
        "patient": "علی",
        "note": "کد ۱۲۳۴۵۶۷۸۹۱",
        "metadata": original_meta,
    }

    redacted = redact_fields(record, ["note", "metadata.contact"])

    # Output modified
    assert "[IR_NATIONAL_ID_1]" in redacted["note"]
    assert "[IR_MOBILE_1]" in redacted["metadata"]["contact"]

    # Original completely intact
    assert record["note"] == "کد ۱۲۳۴۵۶۷۸۹۱"
    assert original_meta["contact"] == original_contact
    assert record["metadata"] is original_meta
    assert original_meta["tags"] == [1, 2, 3]


def test_non_target_types_preserved_exactly() -> None:
    """Verify non-target values (int, float, bool, None, lists) are preserved."""
    sample_list = [1, 2, {"a": "test"}]
    record: dict[str, Any] = {
        "integer": 42,
        "floating": 3.14159,
        "boolean_true": True,
        "boolean_false": False,
        "none_val": None,
        "list_val": sample_list,
        "unrelated_str": "کد ملی ۱۲۳۴۵۶۷۸۹۱",  # PII in unselected field
        "target_str": "کد ملی ۱۲۳۴۵۶۷۸۹۱",
    }

    redacted = redact_fields(record, ["target_str"])

    assert redacted["integer"] == 42
    assert isinstance(redacted["integer"], int)
    assert redacted["floating"] == 3.14159
    assert isinstance(redacted["floating"], float)
    assert redacted["boolean_true"] is True
    assert redacted["boolean_false"] is False
    assert redacted["none_val"] is None
    assert redacted["list_val"] == sample_list
    assert redacted["list_val"] is sample_list
    # Unselected field with PII remains untouched
    assert redacted["unrelated_str"] == "کد ملی ۱۲۳۴۵۶۷۸۹۱"
    assert "[IR_NATIONAL_ID_1]" in redacted["target_str"]


# --- 3. Empty Fields Selection Behavior ---


def test_empty_fields_selection_redact() -> None:
    """Verify fields=[] returns unchanged copy without full-scan redaction."""
    record = {
        "pii1": "کد ملی ۱۲۳۴۵۶۷۸۹۱",
        "pii2": "شماره ۰۹۱۲۳۴۵۶۷۸۹",
        "age": 25,
    }
    redacted = redact_fields(record, [])
    assert redacted == record
    assert redacted is not record
    assert redacted["pii1"] == "کد ملی ۱۲۳۴۵۶۷۸۹۱"
    assert redacted["pii2"] == "شماره ۰۹۱۲۳۴۵۶۷۸۹"


def test_empty_fields_selection_detect_and_report() -> None:
    """Verify fields=[] returns empty dictionary for detect and report."""
    record = {
        "pii1": "کد ملی ۱۲۳۴۵۶۷۸۹۱",
        "pii2": "شماره ۰۹۱۲۳۴۵۶۷۸۹",
    }
    assert detect_fields(record, []) == {}
    assert report_fields(record, []) == {}


# --- 4. Validation, Missing Paths, and Privacy-Safe Errors ---


def test_invalid_record_type() -> None:
    """Verify non-mapping records raise TypeError."""
    with pytest.raises(TypeError, match="record must be a Mapping"):
        detect_fields("not a mapping", ["field"])  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="record must be a Mapping"):
        redact_fields(["list", "of", "items"], ["field"])  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="record must be a Mapping"):
        report_fields(12345, ["field"])  # type: ignore[arg-type]


def test_invalid_fields_type() -> None:
    """Verify non-sequence fields arguments raise TypeError."""
    record = {"note": "text"}
    with pytest.raises(TypeError, match="fields must be a Sequence"):
        detect_fields(record, "note")

    with pytest.raises(TypeError, match="fields must be a Sequence"):
        redact_fields(record, 123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="Field path at index 0 must be a str"):
        report_fields(record, [123])  # type: ignore[list-item]


def test_invalid_path_syntax() -> None:
    """Verify invalid path strings raise ValueError."""
    record = {"note": "text"}
    invalid_paths = ["", ".note", "note.", "metadata..contact", ".", ".."]

    for path in invalid_paths:
        with pytest.raises(ValueError):
            detect_fields(record, [path])
        with pytest.raises(ValueError):
            redact_fields(record, [path])
        with pytest.raises(ValueError):
            report_fields(record, [path])


def test_duplicate_path_rejection() -> None:
    """Verify duplicate paths in fields sequence raise ValueError."""
    record = {"note": "text", "other": "text"}
    with pytest.raises(ValueError, match="Duplicate field path"):
        detect_fields(record, ["note", "note"])

    with pytest.raises(ValueError, match="Duplicate field path"):
        redact_fields(record, ["note", "other", "note"])

    with pytest.raises(ValueError, match="Duplicate field path"):
        report_fields(record, ["note", "note"])


def test_missing_path_key_error() -> None:
    """Verify missing keys raise KeyError with privacy safety."""
    record = {"note": "text", "meta": {"sub": "val"}}

    with pytest.raises(KeyError, match="missing key 'nonexistent'"):
        detect_fields(record, ["nonexistent"])

    with pytest.raises(KeyError, match="missing intermediate key 'missing_meta'"):
        redact_fields(record, ["missing_meta.field"])

    with pytest.raises(KeyError, match="missing key 'missing_leaf'"):
        report_fields(record, ["meta.missing_leaf"])


def test_intermediate_non_mapping_type_error() -> None:
    """Verify non-mapping intermediate containers raise TypeError."""
    record = {"meta": "this is a string, not a dict", "other": [1, 2, 3]}

    with pytest.raises(TypeError, match="is not a Mapping"):
        detect_fields(record, ["meta.contact"])

    with pytest.raises(TypeError, match="is not a Mapping"):
        redact_fields(record, ["other.item"])


def test_target_non_string_type_error() -> None:
    """Verify non-string target values raise TypeError."""
    record = {
        "age": 42,
        "is_active": True,
        "scores": [10, 20],
        "metadata": {"visit_count": 5},
    }

    with pytest.raises(TypeError, match="must be a str, got int"):
        detect_fields(record, ["age"])

    with pytest.raises(TypeError, match="must be a str, got bool"):
        redact_fields(record, ["is_active"])

    with pytest.raises(TypeError, match="must be a str, got list"):
        report_fields(record, ["scores"])

    with pytest.raises(TypeError, match="must be a str, got int"):
        redact_fields(record, ["metadata.visit_count"])


def test_parent_and_child_conflicting_paths() -> None:
    """Verify parent/child path combinations fail conservatively."""
    record = {"profile": {"note": "کد ۱۲۳۴۵۶۷۸۹۱"}}

    # If both "profile" and "profile.note" are passed:
    # "profile" target is a dict -> raises TypeError
    with pytest.raises(TypeError, match="must be a str, got dict"):
        detect_fields(record, ["profile", "profile.note"])


def test_error_privacy_no_target_value_leakage() -> None:
    """Verify exception messages NEVER contain target or sibling field values."""
    sensitive_value = "SECRET_PATIENT_VALUE_9988776655"
    record = {
        "sensitive_target": 12345,  # non-str target
        "sensitive_sibling": sensitive_value,
        "meta": {"sub_int": 99},
    }

    try:
        redact_fields(record, ["sensitive_target"])
    except TypeError as e:
        msg = str(e)
        assert sensitive_value not in msg
        assert "12345" not in msg

    try:
        detect_fields(record, ["meta.sub_int"])
    except TypeError as e:
        msg = str(e)
        assert sensitive_value not in msg
        assert "99" not in msg


# --- 5. Detector Override and Opt-In Detector Semantics ---


def test_detectors_default_set() -> None:
    """Verify default detectors cover national ID, mobile, and IBAN."""
    record = {
        "a": "کد ملی ۱۲۳۴۵۶۷۸۹۱",
        "b": "شماره ۰۹۱۲۳۴۵۶۷۸۹",
        "c": "شبا IR641234567890123456789012",
        "d": "test@example.com",  # opt-in email should NOT be detected by default
    }
    detections = detect_fields(record, ["a", "b", "c", "d"])
    assert len(detections["a"]) == 1
    assert detections["a"][0].type == "IR_NATIONAL_ID"
    assert len(detections["b"]) == 1
    assert detections["b"][0].type == "IR_MOBILE"
    assert len(detections["c"]) == 1
    assert detections["c"][0].type == "IR_IBAN"
    assert len(detections["d"]) == 0


def test_detectors_explicit_override() -> None:
    """Verify explicit detectors replaces defaults."""
    record = {
        "note": "کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره ۰۹۱۲۳۴۵۶۷۸۹",
    }
    # Pass ONLY national ID detector
    detections = detect_fields(
        record,
        ["note"],
        detectors=[IranianNationalIDDetector()],
    )
    assert len(detections["note"]) == 1
    assert detections["note"][0].type == "IR_NATIONAL_ID"


def test_detectors_empty_list() -> None:
    """Verify detectors=[] runs no detectors."""
    record = {
        "note": "کد ملی ۱۲۳۴۵۶۷۸۹۱ و شماره ۰۹۱۲۳۴۵۶۷۸۹",
    }
    detections = detect_fields(record, ["note"], detectors=[])
    assert detections["note"] == []

    redacted = redact_fields(record, ["note"], detectors=[])
    assert redacted["note"] == record["note"]


def test_opt_in_email_and_bank_card_detectors() -> None:
    """Verify opt-in Email and BankCard detectors work when explicitly supplied."""
    record = {
        "email_field": "ایمیل info@example.com است",
        "card_field": "کارت ۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۲ پرداخت شد",
    }
    fields = ["email_field", "card_field"]
    detectors: list[Detector] = [EmailDetector(), BankCardDetector()]

    # Detect
    dets = detect_fields(record, fields, detectors=detectors)
    assert dets["email_field"][0].type == "EMAIL"
    assert dets["card_field"][0].type == "BANK_CARD"

    # Redact
    redacted = redact_fields(record, fields, detectors=detectors)
    assert "[EMAIL_1]" in redacted["email_field"]
    assert "[BANK_CARD_1]" in redacted["card_field"]


def test_custom_pattern_detector() -> None:
    """Verify custom PatternDetector operates on structured fields."""
    rule = PatternRule(
        type="CASE_ID",
        pattern=r"CASE-\d{4}",
    )
    pattern_detector = PatternDetector([rule])
    record = {"ref": "پرونده CASE-1234 در دست بررسی است."}

    dets = detect_fields(record, ["ref"], detectors=[pattern_detector])
    assert len(dets["ref"]) == 1
    assert dets["ref"][0].type == "CASE_ID"

    redacted = redact_fields(record, ["ref"], detectors=[pattern_detector])
    assert "[CASE_ID_1]" in redacted["ref"]


# --- 6. Conflict Policy Semantics ---


def test_conflict_policy_reject_default() -> None:
    """Verify default conflict_policy='reject' fails on overlapping detectors."""
    # Overlapping detectors: national ID (10 digits) and sub-pattern
    rule = PatternRule(
        type="SUB_NUM",
        pattern=r"\d{5}",
    )
    detectors: list[Detector] = [
        IranianNationalIDDetector(),
        PatternDetector([rule]),
    ]
    record = {"note": "کد ۱۲۳۴۵۶۷۸۹۱"}

    # detect_fields preserves raw overlapping detections
    dets = detect_fields(record, ["note"], detectors=detectors)
    assert len(dets["note"]) >= 2

    # redact_fields with default 'reject' policy raises ValueError
    with pytest.raises(ValueError, match="Overlapping detections"):
        redact_fields(record, ["note"], detectors=detectors)


def test_conflict_policy_longest() -> None:
    """Verify conflict_policy='longest' resolves overlapping spans favoring longer."""
    rule = PatternRule(
        type="SHORT_NUM",
        pattern=r"\d{5}",
    )
    detectors: list[Detector] = [
        IranianNationalIDDetector(),
        PatternDetector([rule]),
    ]
    record = {"note": "کد ۱۲۳۴۵۶۷۸۹۱"}

    redacted = redact_fields(
        record,
        ["note"],
        detectors=detectors,
        conflict_policy="longest",
    )
    assert "[IR_NATIONAL_ID_1]" in redacted["note"]
    assert "[SHORT_NUM" not in redacted["note"]


def test_conflict_policy_priority() -> None:
    """Verify conflict_policy='priority' resolves according to type_priority."""
    rule = PatternRule(
        type="PATIENT_ID",
        pattern=r"\d{10}",
    )
    detectors: list[Detector] = [
        IranianNationalIDDetector(),
        PatternDetector([rule]),
    ]
    record = {"note": "کد ۱۲۳۴۵۶۷۸۹۱"}

    redacted = redact_fields(
        record,
        ["note"],
        detectors=detectors,
        conflict_policy="priority",
        type_priority=["PATIENT_ID", "IR_NATIONAL_ID"],
    )
    assert "[PATIENT_ID_1]" in redacted["note"]


# --- 7. Script Variations and Normalization ---


def test_persian_and_arabic_indic_digits_normalized() -> None:
    """Verify Persian and Arabic-Indic digits are normalized and redacted."""
    record = {
        "persian": "کد ۱۲۳۴۵۶۷۸۹۱",
        "arabic": "کد ١٢٣٤٥٦٧٨٩١",
        "ascii": "کد 1234567891",
    }
    redacted = redact_fields(record, ["persian", "arabic", "ascii"])
    assert "[IR_NATIONAL_ID_1]" in redacted["persian"]
    assert "[IR_NATIONAL_ID_1]" in redacted["arabic"]
    assert "[IR_NATIONAL_ID_1]" in redacted["ascii"]


# --- 8. Custom Mapping Types ---


def test_custom_mapping_type_support() -> None:
    """Verify MappingProxyType is accepted as input and returns a plain dict copy."""
    inner = {"note": "کد ملی ۱۲۳۴۵۶۷۸۹۱", "age": 35}
    proxy = MappingProxyType(inner)

    redacted = redact_fields(proxy, ["note"])
    assert isinstance(redacted, dict)
    assert "[IR_NATIONAL_ID_1]" in redacted["note"]
    assert redacted["age"] == 35
    # Original untouched
    assert proxy["note"] == "کد ملی ۱۲۳۴۵۶۷۸۹۱"


# --- 9. Cross-Field Referential Consistency and Literal Reservation ---


def test_cross_field_referential_consistency_same_identifier() -> None:
    """Verify identical identifiers across fields receive the same placeholder."""
    record = {
        "contact": "09123456789",
        "summary": "تماس با ۰۹۱۲۳۴۵۶۷۸۹ و کد ملی ۱۲۳۴۵۶۷۸۹۱",
    }
    redacted = redact_fields(record, ["contact", "summary"])

    assert redacted["contact"] == "[IR_MOBILE_1]"
    assert "[IR_MOBILE_1]" in redacted["summary"]
    assert "[IR_NATIONAL_ID_1]" in redacted["summary"]
    # Verify original record is unchanged
    assert record["contact"] == "09123456789"
    assert record["summary"] == "تماس با ۰۹۱۲۳۴۵۶۷۸۹ و کد ملی ۱۲۳۴۵۶۷۸۹۱"


def test_cross_field_referential_consistency_multiple_identifiers() -> None:
    """Verify multiple identifiers retain stable identities across fields."""
    record = {
        "field_a": "a@example.com b@example.com",
        "field_b": "b@example.com",
    }
    detectors: list[Detector] = [EmailDetector()]
    redacted = redact_fields(record, ["field_a", "field_b"], detectors=detectors)

    assert redacted["field_a"] == "[EMAIL_1] [EMAIL_2]"
    assert redacted["field_b"] == "[EMAIL_2]"


def test_cross_field_fields_ordering_determinism() -> None:
    """Verify fields order determines placeholder assignment deterministically."""
    record = {
        "field_a": "a@example.com b@example.com",
        "field_b": "b@example.com",
    }
    detectors: list[Detector] = [EmailDetector()]

    # field_b processed first -> b@example.com gets [EMAIL_1]
    redacted = redact_fields(record, ["field_b", "field_a"], detectors=detectors)
    assert redacted["field_b"] == "[EMAIL_1]"
    assert redacted["field_a"] == "[EMAIL_2] [EMAIL_1]"


def test_cross_field_placeholder_literal_reservation() -> None:
    """Verify placeholder-like literal in earlier field is reserved for later fields."""
    record = {
        "field_1": "Token literal [EMAIL_1] present",
        "field_2": "Real email user@example.com",
    }
    detectors: list[Detector] = [EmailDetector()]
    redacted = redact_fields(record, ["field_1", "field_2"], detectors=detectors)

    assert redacted["field_1"] == "Token literal [EMAIL_1] present"
    assert redacted["field_2"] == "Real email [EMAIL_2]"


def test_cross_field_unselected_fields_not_scanned() -> None:
    """Verify unselected fields do not participate in session mapping or scanning."""
    record = {
        "unselected": "Real email user@example.com and [EMAIL_1]",
        "selected": "Real email user@example.com",
    }
    detectors: list[Detector] = [EmailDetector()]
    redacted = redact_fields(record, ["selected"], detectors=detectors)

    # user@example.com gets [EMAIL_1] since unselected field is never inspected
    assert redacted["selected"] == "Real email [EMAIL_1]"
    assert redacted["unselected"] == "Real email user@example.com and [EMAIL_1]"
