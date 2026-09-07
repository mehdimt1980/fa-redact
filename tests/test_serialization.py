"""Comprehensive unit and regression tests for fa-redact structured serialization."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import MappingProxyType

import pytest

import fa_redact
from fa_redact import (
    Detection,
    detection_report,
    detection_to_dict,
    detections_to_list,
    dumps_detections,
    dumps_report,
    dumps_reports,
    report_detections,
    report_fields,
    report_to_dict,
    reports_to_dict,
)
from fa_redact.cli import main as cli_main

# ============================================================================
# 1. Detection structural serialization tests
# ============================================================================


def test_detection_to_dict_positive() -> None:
    """Verify detection_to_dict returns expected structure."""
    det = Detection(
        type="IR_NATIONAL_ID",
        value="0012345678",
        normalized_value="0012345678",
        start=10,
        end=20,
    )
    res = detection_to_dict(det)
    assert res == {
        "type": "IR_NATIONAL_ID",
        "start": 10,
        "end": 20,
    }


def test_detection_to_dict_exact_keys() -> None:
    """Verify detection_to_dict contains exactly 'type', 'start', 'end' keys."""
    det = Detection(
        type="IR_MOBILE",
        value="09123456789",
        normalized_value="09123456789",
        start=5,
        end=16,
    )
    res = detection_to_dict(det)
    assert set(res.keys()) == {"type", "start", "end"}


def test_detection_to_dict_value_absent() -> None:
    """Verify Detection.value is absent from serialized dictionary."""
    raw_marker = "SECRET_10C"
    norm_marker = "NORMALIZE1"
    det = Detection(
        type="IR_NATIONAL_ID",
        value=raw_marker,
        normalized_value=norm_marker,
        start=0,
        end=10,
    )
    res = detection_to_dict(det)
    assert "value" not in res
    assert raw_marker not in str(res)


def test_detection_to_dict_normalized_value_absent() -> None:
    """Verify Detection.normalized_value is absent from serialized dictionary."""
    raw_marker = "RAW_VAL_10"
    norm_marker = "NORM_VAL10"
    det = Detection(
        type="IR_NATIONAL_ID",
        value=raw_marker,
        normalized_value=norm_marker,
        start=0,
        end=10,
    )
    res = detection_to_dict(det)
    assert "normalized_value" not in res
    assert norm_marker not in str(res)


def test_detection_to_dict_no_source_snippet_hash_keys() -> None:
    """Verify no unexpected context, snippet, or hash keys are included."""
    val = "test@example.com"
    det = Detection(
        type="EMAIL",
        value=val,
        normalized_value=val,
        start=2,
        end=2 + len(val),
    )
    res = detection_to_dict(det)
    forbidden_keys = {
        "source",
        "snippet",
        "hash",
        "confidence",
        "detector",
        "model",
        "context",
        "text",
    }
    assert forbidden_keys.isdisjoint(set(res.keys()))


def test_detection_to_dict_custom_type_preserved() -> None:
    """Verify custom Detection.type string is preserved exactly."""
    val = "MRN-123456"
    det = Detection(
        type="CUSTOM_HOSPITAL_MRN_TYPE",
        value=val,
        normalized_value=val,
        start=8,
        end=8 + len(val),
    )
    res = detection_to_dict(det)
    assert res["type"] == "CUSTOM_HOSPITAL_MRN_TYPE"


def test_detection_to_dict_start_and_end_preserved() -> None:
    """Verify exact character start and end offsets are preserved unchanged."""
    val = "IR641234567890123456789012"
    det = Detection(
        type="IR_IBAN",
        value=val,
        normalized_value=val,
        start=105,
        end=105 + len(val),
    )
    res = detection_to_dict(det)
    assert res["start"] == 105
    assert res["end"] == 105 + len(val)


def test_detection_to_dict_input_type_validation() -> None:
    """Verify detection_to_dict raises TypeError on non-Detection input."""
    with pytest.raises(TypeError, match="detection must be a Detection instance"):
        detection_to_dict("not_a_detection")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="detection must be a Detection instance"):
        detection_to_dict(123)  # type: ignore[arg-type]


def test_detection_to_dict_error_does_not_reveal_raw_value() -> None:
    """Verify error messages on invalid input do not echo raw values or secrets."""
    secret_val = "SECRET_STRING_VALUE"
    with pytest.raises(TypeError) as excinfo:
        detection_to_dict(secret_val)  # type: ignore[arg-type]
    assert secret_val not in str(excinfo.value)
    assert "got str" in str(excinfo.value)


# ============================================================================
# 2. Detections sequence serialization tests
# ============================================================================


def test_detections_to_list_empty() -> None:
    """Verify detections_to_list on empty sequence returns empty list."""
    assert detections_to_list([]) == []
    assert detections_to_list(()) == []


def test_detections_to_list_preserves_order() -> None:
    """Verify detections_to_list preserves input sequence order exactly."""
    det1 = Detection(type="T1", value="v1", normalized_value="v1", start=20, end=22)
    det2 = Detection(type="T2", value="v2", normalized_value="v2", start=5, end=7)
    det3 = Detection(type="T3", value="v3", normalized_value="v3", start=40, end=42)

    # Intentionally pass out-of-offset-order list
    res = detections_to_list([det1, det2, det3])
    assert len(res) == 3
    assert res[0]["type"] == "T1"
    assert res[1]["type"] == "T2"
    assert res[2]["type"] == "T3"


def test_detections_to_list_preserves_duplicates() -> None:
    """Verify detections_to_list preserves exact duplicates without deduplicating."""
    det = Detection(
        type="T1",
        value="1234567890",
        normalized_value="1234567890",
        start=10,
        end=20,
    )
    res = detections_to_list([det, det, det])
    assert len(res) == 3
    assert res == [
        {"type": "T1", "start": 10, "end": 20},
        {"type": "T1", "start": 10, "end": 20},
        {"type": "T1", "start": 10, "end": 20},
    ]


def test_detections_to_list_preserves_overlapping() -> None:
    """Verify detections_to_list preserves overlaps without conflict resolution."""
    det1 = Detection(
        type="T1",
        value="a" * 20,
        normalized_value="a" * 20,
        start=10,
        end=30,
    )
    det2 = Detection(
        type="T2",
        value="b" * 20,
        normalized_value="b" * 20,
        start=20,
        end=40,
    )
    res = detections_to_list([det1, det2])
    assert len(res) == 2
    assert res[0]["start"] == 10 and res[0]["end"] == 30
    assert res[1]["start"] == 20 and res[1]["end"] == 40


def test_detections_to_list_preserves_nested() -> None:
    """Verify detections_to_list preserves nested/contained detections."""
    det_outer = Detection(
        type="OUTER",
        value="a" * 45,
        normalized_value="a" * 45,
        start=5,
        end=50,
    )
    det_inner = Detection(
        type="INNER",
        value="b" * 15,
        normalized_value="b" * 15,
        start=10,
        end=25,
    )
    res = detections_to_list([det_outer, det_inner])
    assert len(res) == 2
    assert res[0]["type"] == "OUTER"
    assert res[1]["type"] == "INNER"


def test_detections_to_list_rejects_str() -> None:
    """Verify detections_to_list rejects str input."""
    with pytest.raises(
        TypeError,
        match="detections must be a Sequence of Detection instances, got str",
    ):
        detections_to_list("not_a_sequence")  # type: ignore[arg-type]


def test_detections_to_list_rejects_bytes() -> None:
    """Verify detections_to_list rejects bytes input."""
    with pytest.raises(
        TypeError,
        match="detections must be a Sequence of Detection instances, got bytes",
    ):
        detections_to_list(b"not_a_sequence")  # type: ignore[arg-type]


def test_detections_to_list_rejects_bytearray() -> None:
    """Verify detections_to_list rejects bytearray input."""
    with pytest.raises(
        TypeError,
        match="detections must be a Sequence of Detection instances, got bytearray",
    ):
        detections_to_list(bytearray(b"not_a_sequence"))  # type: ignore[arg-type]


def test_detections_to_list_rejects_non_sequence() -> None:
    """Verify detections_to_list rejects non-Sequence input like integer, set, None."""
    with pytest.raises(
        TypeError, match="detections must be a Sequence of Detection instances"
    ):
        detections_to_list(123)  # type: ignore[arg-type]

    with pytest.raises(
        TypeError, match="detections must be a Sequence of Detection instances"
    ):
        detections_to_list({1, 2, 3})  # type: ignore[arg-type]

    with pytest.raises(
        TypeError, match="detections must be a Sequence of Detection instances"
    ):
        detections_to_list(None)  # type: ignore[arg-type]


def test_detections_to_list_rejects_non_detection_item_safe_error() -> None:
    """Verify error diagnostics report safe index and type without echoing item."""
    det1 = Detection(type="T1", value="12345", normalized_value="12345", start=0, end=5)
    secret_item = "SECRET_STRING"

    with pytest.raises(TypeError) as excinfo:
        detections_to_list([det1, secret_item])  # type: ignore[list-item]

    msg = str(excinfo.value)
    assert "item at index 1 must be a Detection instance, got str" in msg
    assert secret_item not in msg


def test_detection_dict_mutation_does_not_alter_detection() -> None:
    """Verify mutating returned dict does not mutate Detection object."""
    det = Detection(
        type="IR_MOBILE",
        value="09123456789",
        normalized_value="09123456789",
        start=0,
        end=11,
    )
    res = detection_to_dict(det)
    res["type"] = "MUTATED"
    res["start"] = 999

    assert det.type == "IR_MOBILE"
    assert det.start == 0


# ============================================================================
# 3. DetectionReport serialization tests
# ============================================================================


def test_report_to_dict_positive() -> None:
    """Verify report_to_dict returns exact expected keys and values."""
    text = "کد ملی ۱۲۳۴۵۶۷۸۹۱ و همراه ۰۹۱۲۳۴۵۶۷۸۹"
    report = detection_report(text)
    res = report_to_dict(report)

    assert res == {
        "total_detections": 2,
        "counts": {"IR_MOBILE": 1, "IR_NATIONAL_ID": 1},
        "distinct_types": 2,
        "has_conflicts": False,
        "conflict_pairs": 0,
        "conflicting_detections": 0,
        "duplicate_groups": 0,
    }


def test_report_to_dict_exact_key_set() -> None:
    """Verify report_to_dict contains exactly the 7 public report keys."""
    text = "متن بدون شناسه"
    report = detection_report(text)
    res = report_to_dict(report)
    expected_keys = {
        "total_detections",
        "counts",
        "distinct_types",
        "has_conflicts",
        "conflict_pairs",
        "conflicting_detections",
        "duplicate_groups",
    }
    assert set(res.keys()) == expected_keys


def test_report_to_dict_counts_is_ordinary_dict() -> None:
    """Verify returned counts is a fresh ordinary dict, not MappingProxyType."""
    text = "کد ملی ۱۲۳۴۵۶۷۸۹۱"
    report = detection_report(text)
    res = report_to_dict(report)

    assert type(res["counts"]) is dict
    assert not isinstance(res["counts"], MappingProxyType)


def test_report_to_dict_counts_ordering_preserved() -> None:
    """Verify counts ordering matches report.counts deterministic ordering."""
    det1 = Detection(type="Z_TYPE", value="v", normalized_value="v", start=0, end=1)
    det2 = Detection(type="A_TYPE", value="v", normalized_value="v", start=2, end=3)
    report = report_detections([det1, det2])
    res = report_to_dict(report)

    counts = res["counts"]
    assert isinstance(counts, dict)
    assert list(counts.keys()) == list(report.counts.keys())


def test_report_to_dict_raw_values_and_spans_absent() -> None:
    """Verify report_to_dict contains no values, normalized values, or offsets."""
    text = "کد ملی ۱۲۳۴۵۶۷۸۹۱"
    report = detection_report(text)
    res = report_to_dict(report)
    res_str = str(res)

    assert "۱۲۳۴۵۶۷۸۹۱" not in res_str
    assert "1234567891" not in res_str
    assert "start" not in res
    assert "end" not in res
    assert "spans" not in res


def test_report_to_dict_source_snippet_hash_absent() -> None:
    """Verify report_to_dict contains no source text, snippets, or hashes."""
    text = "سند محرمانه بالینی ۱۲۳۴۵۶۷۸۹۱"
    report = detection_report(text)
    res = report_to_dict(report)
    res_str = str(res)

    assert "سند محرمانه بالینی" not in res_str
    assert "snippet" not in res
    assert "hash" not in res


def test_report_to_dict_input_type_validation() -> None:
    """Verify report_to_dict raises TypeError on non-DetectionReport input."""
    with pytest.raises(TypeError, match="report must be a DetectionReport instance"):
        report_to_dict("not_a_report")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="report must be a DetectionReport instance"):
        report_to_dict(None)  # type: ignore[arg-type]


def test_report_to_dict_empty_report() -> None:
    """Verify empty DetectionReport serializes cleanly."""
    report = report_detections([])
    res = report_to_dict(report)

    assert res["total_detections"] == 0
    assert res["counts"] == {}
    assert res["distinct_types"] == 0
    assert res["has_conflicts"] is False
    assert res["conflict_pairs"] == 0
    assert res["conflicting_detections"] == 0
    assert res["duplicate_groups"] == 0


def test_report_to_dict_mutation_safety() -> None:
    """Verify mutating returned report dict does not mutate DetectionReport."""
    text = "کد ملی ۱۲۳۴۵۶۷۸۹۱"
    report = detection_report(text)
    res = report_to_dict(report)

    counts_dict = res["counts"]
    assert isinstance(counts_dict, dict)
    counts_dict["MUTATED_KEY"] = 999
    res["total_detections"] = 999

    assert "MUTATED_KEY" not in report.counts
    assert report.total_detections == 1


# ============================================================================
# 4. Multiple reports mapping serialization tests
# ============================================================================


def test_reports_to_dict_empty_mapping() -> None:
    """Verify reports_to_dict on empty mapping returns empty dict."""
    assert reports_to_dict({}) == {}


def test_reports_to_dict_multiple_reports() -> None:
    """Verify reports_to_dict serializes multi-field report mapping."""
    record = {
        "note": "کد ملی ۱۲۳۴۵۶۷۸۹۱",
        "contact": "موبایل ۰۹۱۲۳۴۵۶۷۸۹",
    }
    field_reports = report_fields(record, ["note", "contact"])
    res = reports_to_dict(field_reports)

    assert set(res.keys()) == {"note", "contact"}
    assert res["note"]["total_detections"] == 1
    assert res["contact"]["total_detections"] == 1
    assert res["note"]["counts"] == {"IR_NATIONAL_ID": 1}
    assert res["contact"]["counts"] == {"IR_MOBILE": 1}


def test_reports_to_dict_mapping_order_preserved() -> None:
    """Verify reports_to_dict preserves mapping key iteration order."""
    r1 = detection_report("کد ملی ۱۲۳۴۵۶۷۸۹۱")
    r2 = detection_report("موبایل ۰۹۱۲۳۴۵۶۷۸۹")
    r3 = detection_report("شبا IR641234567890123456789012")

    mapping = {"field_c": r1, "field_a": r2, "field_b": r3}
    res = reports_to_dict(mapping)
    assert list(res.keys()) == ["field_c", "field_a", "field_b"]


def test_reports_to_dict_mapping_input_not_mutated() -> None:
    """Verify caller mapping is not mutated."""
    r1 = detection_report("کد ملی ۱۲۳۴۵۶۷۸۹۱")
    mapping = {"field_1": r1}
    res = reports_to_dict(mapping)
    res["field_new"] = {}

    assert "field_new" not in mapping
    assert len(mapping) == 1


def test_reports_to_dict_rejects_non_mapping() -> None:
    """Verify reports_to_dict raises TypeError on non-Mapping input."""
    with pytest.raises(
        TypeError, match="reports must be a Mapping of str to DetectionReport"
    ):
        reports_to_dict(["not", "a", "mapping"])  # type: ignore[arg-type]

    with pytest.raises(
        TypeError, match="reports must be a Mapping of str to DetectionReport"
    ):
        reports_to_dict(123)  # type: ignore[arg-type]


def test_reports_to_dict_rejects_non_string_key_safely() -> None:
    """Verify reports_to_dict rejects non-string keys with safe error."""
    r = detection_report("کد ملی ۱۲۳۴۵۶۷۸۹۱")
    with pytest.raises(
        TypeError, match="key at mapping entry 0 must be a str, got int"
    ):
        reports_to_dict({123: r})  # type: ignore[dict-item]


def test_reports_to_dict_rejects_non_report_value_safely() -> None:
    """Verify reports_to_dict rejects non-DetectionReport values with safe error."""
    secret_value = "SECRET_NON_REPORT"
    with pytest.raises(TypeError) as excinfo:
        reports_to_dict({"valid_key": secret_value})  # type: ignore[dict-item]

    msg = str(excinfo.value)
    assert "value at mapping entry 0 must be a DetectionReport instance, got str" in msg
    assert secret_value not in msg


def test_reports_to_dict_mapping_errors_do_not_echo_key_contents() -> None:
    """Verify mapping validation errors do not echo invalid key contents."""
    secret_key = ("SECRET", "KEY")
    r = detection_report("کد ملی ۱۲۳۴۵۶۷۸۹۱")
    with pytest.raises(TypeError) as excinfo:
        reports_to_dict({secret_key: r})  # type: ignore[dict-item]

    msg = str(excinfo.value)
    assert "key at mapping entry 0 must be a str, got tuple" in msg
    assert "SECRET" not in msg


# ============================================================================
# 5. JSON dump helpers tests
# ============================================================================


def test_dumps_detections_valid_json() -> None:
    """Verify dumps_detections outputs valid parseable JSON."""
    det = Detection(
        type="IR_NATIONAL_ID",
        value="0012345678",
        normalized_value="0012345678",
        start=0,
        end=10,
    )
    output = dumps_detections([det])
    parsed = json.loads(output)
    assert parsed == [{"type": "IR_NATIONAL_ID", "start": 0, "end": 10}]


def test_dumps_detections_ensure_ascii_false() -> None:
    """Verify dumps_detections preserves Unicode characters (ensure_ascii=False)."""
    det = Detection(
        type="شناسه_سازمانی",
        value="۱۲۳",
        normalized_value="123",
        start=0,
        end=3,
    )
    output = dumps_detections([det])
    assert "شناسه_سازمانی" in output
    assert "\\u" not in output


def test_dumps_detections_default_indent_2() -> None:
    """Verify dumps_detections formats with 2-space indentation by default."""
    det = Detection(
        type="IR_NATIONAL_ID",
        value="0012345678",
        normalized_value="0012345678",
        start=0,
        end=10,
    )
    output = dumps_detections([det])
    expected = (
        "[\n"
        "  {\n"
        '    "type": "IR_NATIONAL_ID",\n'
        '    "start": 0,\n'
        '    "end": 10\n'
        "  }\n"
        "]\n"
    )
    assert output == expected


def test_dumps_detections_trailing_newline_exactly_one() -> None:
    """Verify dumps_detections appends exactly one trailing newline."""
    output = dumps_detections([])
    assert output.endswith("\n")
    assert not output.endswith("\n\n")


def test_dumps_detections_empty_list() -> None:
    """Verify dumps_detections on empty list returns '[]\\n'."""
    assert dumps_detections([]) == "[]\n"


def test_dumps_report_valid_json() -> None:
    """Verify dumps_report outputs valid parseable JSON."""
    report = detection_report("کد ملی ۱۲۳۴۵۶۷۸۹۱")
    output = dumps_report(report)
    parsed = json.loads(output)
    assert parsed["total_detections"] == 1
    assert parsed["counts"] == {"IR_NATIONAL_ID": 1}


def test_dumps_report_trailing_newline() -> None:
    """Verify dumps_report ends with exactly one trailing newline."""
    report = detection_report("کد ملی ۱۲۳۴۵۶۷۸۹۱")
    output = dumps_report(report)
    assert output.endswith("\n")
    assert not output.endswith("\n\n")


def test_dumps_reports_valid_json() -> None:
    """Verify dumps_reports outputs valid JSON for field report mappings."""
    record = {"note": "کد ملی ۱۲۳۴۵۶۷۸۹۱"}
    field_reps = report_fields(record, ["note"])
    output = dumps_reports(field_reps)
    parsed = json.loads(output)
    assert "note" in parsed
    assert parsed["note"]["total_detections"] == 1


def test_dumps_reports_empty_mapping() -> None:
    """Verify dumps_reports on empty mapping produces '{}\\n'."""
    assert dumps_reports({}) == "{}\n"


def test_repeated_dump_deterministic() -> None:
    """Verify repeated dumps produce byte-for-byte identical output."""
    det = Detection(
        type="IR_NATIONAL_ID",
        value="0012345678",
        normalized_value="0012345678",
        start=5,
        end=15,
    )
    out1 = dumps_detections([det])
    out2 = dumps_detections([det])
    assert out1 == out2

    rep = detection_report("کد ملی ۱۲۳۴۵۶۷۸۹۱ و همراه ۰۹۱۲۳۴۵۶۷۸۹")
    rep_out1 = dumps_report(rep)
    rep_out2 = dumps_report(rep)
    assert rep_out1 == rep_out2


def test_indent_none_supported() -> None:
    """Verify indent=None produces compact JSON with one trailing newline."""
    det = Detection(
        type="IR_NATIONAL_ID",
        value="0012345678",
        normalized_value="0012345678",
        start=0,
        end=10,
    )
    output = dumps_detections([det], indent=None)
    assert output == '[{"type": "IR_NATIONAL_ID", "start": 0, "end": 10}]\n'

    rep = detection_report("کد ملی ۱۲۳۴۵۶۷۸۹۱")
    rep_out = dumps_report(rep, indent=None)
    assert "\n" not in rep_out[:-1]
    assert rep_out.endswith("\n")


def test_no_volatile_metadata_in_output() -> None:
    """Verify output contains no volatile fields like timestamps, UUIDs, or paths."""
    det = Detection(
        type="IR_MOBILE",
        value="09123456789",
        normalized_value="09123456789",
        start=0,
        end=11,
    )
    out = dumps_detections([det])
    parsed = json.loads(out)
    for entry in parsed:
        for k in entry.keys():
            assert k in ("type", "start", "end")


# ============================================================================
# 6. Privacy regression tests with synthetic markers
# ============================================================================


def test_detection_privacy_regression_synthetic_raw_marker() -> None:
    """Assert synthetic secret raw marker is absent from all serialized forms."""
    raw_marker = "SYNTHETIC_SECRET_MARKER_RAW_98765"
    norm_marker = "0" * len(raw_marker)
    det = Detection(
        type="IR_NATIONAL_ID",
        value=raw_marker,
        normalized_value=norm_marker,
        start=0,
        end=len(raw_marker),
    )

    d_dict = detection_to_dict(det)
    assert raw_marker not in str(d_dict)
    assert raw_marker not in json.dumps(d_dict)

    d_list = detections_to_list([det])
    assert raw_marker not in str(d_list)

    d_json = dumps_detections([det])
    assert raw_marker not in d_json


def test_detection_privacy_regression_synthetic_normalized_marker() -> None:
    """Assert synthetic secret normalized marker is absent from all forms."""
    norm_marker = "SYNTHETIC_SECRET_MARKER_NORMALIZED_54321"
    raw_marker = "0" * len(norm_marker)
    det = Detection(
        type="IR_NATIONAL_ID",
        value=raw_marker,
        normalized_value=norm_marker,
        start=0,
        end=len(norm_marker),
    )

    d_dict = detection_to_dict(det)
    assert norm_marker not in str(d_dict)
    assert norm_marker not in json.dumps(d_dict)

    d_list = detections_to_list([det])
    assert norm_marker not in str(d_list)

    d_json = dumps_detections([det])
    assert norm_marker not in d_json


def test_report_privacy_regression_synthetic_markers() -> None:
    """Assert synthetic markers in detections do not leak into serialized reports."""
    raw_marker = "SYNTHETIC_SECRET_RAW_ABC"
    norm_marker = "SYNTHETIC_SECRET_NRM_XYZ"
    assert len(raw_marker) == len(norm_marker)
    det = Detection(
        type="IR_NATIONAL_ID",
        value=raw_marker,
        normalized_value=norm_marker,
        start=0,
        end=len(raw_marker),
    )

    rep = report_detections([det])
    rep_dict = report_to_dict(rep)
    assert raw_marker not in str(rep_dict)
    assert norm_marker not in str(rep_dict)

    rep_json = dumps_report(rep)
    assert raw_marker not in rep_json
    assert norm_marker not in rep_json

    reps_dict = reports_to_dict({"safe_field": rep})
    assert raw_marker not in str(reps_dict)
    assert norm_marker not in str(reps_dict)

    reps_json = dumps_reports({"safe_field": rep})
    assert raw_marker not in reps_json
    assert norm_marker not in reps_json


# ============================================================================
# 7. CLI backward-compatibility and reuse regression tests
# ============================================================================


def test_cli_detect_output_byte_compatible(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify CLI detect command produces exact byte-compatible JSON output."""
    sample_text = "کد ملی ۱۲۳۴۵۶۷۸۹۱ و همراه ۰۹۱۲۳۴۵۶۷۸۹"
    in_file = tmp_path / "input.txt"
    in_file.write_text(sample_text, encoding="utf-8")
    code = cli_main(["detect", str(in_file)])
    assert code == 0

    captured = capsys.readouterr()
    # Check exact expected JSON format
    parsed = json.loads(captured.out)
    assert len(parsed) == 2
    assert parsed[0]["type"] == "IR_NATIONAL_ID"
    assert parsed[1]["type"] == "IR_MOBILE"
    assert captured.out.endswith("\n")
    assert not captured.out.endswith("\n\n")


def test_cli_report_output_byte_compatible(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify CLI report command produces exact byte-compatible JSON output."""
    sample_text = "کد ملی ۱۲۳۴۵۶۷۸۹۱"
    in_file = tmp_path / "input.txt"
    in_file.write_text(sample_text, encoding="utf-8")
    code = cli_main(["report", str(in_file)])
    assert code == 0

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["total_detections"] == 1
    assert parsed["counts"] == {"IR_NATIONAL_ID": 1}
    assert parsed["has_conflicts"] is False
    assert captured.out.endswith("\n")


def test_cli_internally_uses_serialization_helpers() -> None:
    """Verify CLI module imports and calls serialization helpers."""
    import fa_redact.cli as cli_mod

    assert hasattr(cli_mod, "dumps_detections")
    assert hasattr(cli_mod, "dumps_report")
    assert getattr(cli_mod, "dumps_detections") is dumps_detections
    assert getattr(cli_mod, "dumps_report") is dumps_report


def test_no_new_cli_commands_or_flags() -> None:
    """Verify CLI parser has only detect, redact, report and standard flags."""
    from fa_redact.cli import create_parser

    parser = create_parser()
    subparsers_actions = [
        action
        for action in parser._actions
        if action.__class__.__name__ == "_SubParsersAction"
    ]
    assert len(subparsers_actions) == 1
    choices = subparsers_actions[0].choices
    assert choices is not None
    subparser_choices = set(choices)
    assert subparser_choices == {"detect", "redact", "report"}

    # Ensure no serialization/export command or flags added
    for forbidden_cmd in ("serialize", "export", "json", "fhir", "hl7"):
        assert forbidden_cmd not in subparser_choices


# ============================================================================
# 8. Negative scope & architectural boundary tests
# ============================================================================


def test_pseudonymization_session_mapping_not_exposed() -> None:
    """Verify PseudonymizationSession mapping has no serializer function."""
    import fa_redact.serialization as ser_mod

    for forbidden in (
        "mapping_to_dict",
        "mapping_to_json",
        "session_to_dict",
        "session_to_json",
        "export_mapping",
        "dump_mapping",
    ):
        assert not hasattr(ser_mod, forbidden)
        assert not hasattr(fa_redact, forbidden)


def test_no_serialization_api_includes_raw_opt_in() -> None:
    """Verify serialization functions do not offer include_values/raw flags."""
    for fn in (
        detection_to_dict,
        detections_to_list,
        report_to_dict,
        reports_to_dict,
        dumps_detections,
        dumps_report,
        dumps_reports,
    ):
        sig = inspect.signature(fn)
        for param in sig.parameters.values():
            assert param.name not in (
                "include_values",
                "include_raw",
                "include_normalized",
                "raw",
                "unsafe",
                "full",
            )


def test_no_generic_serializer_exported() -> None:
    """Verify no generic arbitrary-object serialize/to_dict function exists."""
    for fn_name in ("serialize", "to_dict", "to_json", "dump_json"):
        assert not hasattr(fa_redact, fn_name)


def test_no_deserializer_exported() -> None:
    """Verify no deserialization functions are exported."""
    for fn_name in (
        "detection_from_dict",
        "detection_from_json",
        "report_from_dict",
        "report_from_json",
        "loads_detection",
        "loads_detections",
        "loads_report",
        "loads_reports",
    ):
        assert not hasattr(fa_redact, fn_name)


def test_no_record_serializer_exported() -> None:
    """Verify no arbitrary record serialization function is exported."""
    for fn_name in ("record_to_json", "redacted_record_to_json", "serialize_record"):
        assert not hasattr(fa_redact, fn_name)


def test_no_fhir_or_hl7_modules() -> None:
    """Verify no healthcare format or FHIR/HL7 modules exist."""
    import sys

    assert "fa_redact.fhir" not in sys.modules
    assert "fa_redact.hl7" not in sys.modules
    assert not hasattr(fa_redact, "fhir")
    assert not hasattr(fa_redact, "hl7")


def test_package_version_remains_0_3_0() -> None:
    """Verify package version remains 0.3.0 without bumping."""
    assert fa_redact.__version__ == "0.3.0"


# ============================================================================
# 9. Top-level exports verification
# ============================================================================


def test_root_serialization_exports() -> None:
    """Verify all 7 serialization helpers are exported from top-level fa_redact."""
    exported_helpers = [
        "detection_to_dict",
        "detections_to_list",
        "report_to_dict",
        "reports_to_dict",
        "dumps_detections",
        "dumps_report",
        "dumps_reports",
    ]
    for name in exported_helpers:
        assert hasattr(fa_redact, name)
        assert callable(getattr(fa_redact, name))
        assert name in fa_redact.__all__
