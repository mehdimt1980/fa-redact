"""Comprehensive test suite for privacy-safe detection reporting in fa-redact."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

import pytest

from fa_redact import (
    BankCardDetector,
    Detection,
    DetectionReport,
    Detector,
    EmailDetector,
    PatternDetector,
    PatternRule,
    detection_report,
    report_detections,
    resolve_detection_conflicts,
)

# ============================================================================
# Unit Tests: report_detections & DetectionReport Basics
# ============================================================================


def test_empty_report() -> None:
    """Empty detection list produces zeroed DetectionReport."""
    report = report_detections([])
    assert report.total_detections == 0
    assert len(report.counts) == 0
    assert dict(report.counts) == {}
    assert report.distinct_types == 0
    assert report.has_conflicts is False
    assert report.conflict_pairs == 0
    assert report.conflicting_detections == 0
    assert report.duplicate_groups == 0


def test_single_detection_report() -> None:
    """Single detection produces a clean non-conflicting report."""
    d = Detection(
        type="IR_NATIONAL_ID",
        start=0,
        end=10,
        value="1234567891",
        normalized_value="1234567891",
    )
    report = report_detections([d])
    assert report.total_detections == 1
    assert report.counts["IR_NATIONAL_ID"] == 1
    assert report.distinct_types == 1
    assert report.has_conflicts is False
    assert report.conflict_pairs == 0
    assert report.conflicting_detections == 0
    assert report.duplicate_groups == 0


def test_multiple_entity_counts_and_distinct_types() -> None:
    """Multiple entity types are counted accurately without deduplication."""
    detections = [
        Detection("EMAIL", 0, 7, "a@b.com", "a@b.com"),
        Detection("EMAIL", 20, 27, "c@d.com", "c@d.com"),
        Detection("EMAIL", 40, 47, "e@f.com", "e@f.com"),
        Detection("IR_MOBILE", 60, 71, "09123456789", "09123456789"),
        Detection("IR_MOBILE", 80, 91, "09123456788", "09123456788"),
        Detection("IR_NATIONAL_ID", 100, 110, "1234567891", "1234567891"),
    ]
    report = report_detections(detections)
    assert report.total_detections == 6
    assert report.distinct_types == 3
    assert dict(report.counts) == {
        "EMAIL": 3,
        "IR_MOBILE": 2,
        "IR_NATIONAL_ID": 1,
    }
    assert report.has_conflicts is False
    assert report.conflict_pairs == 0
    assert report.conflicting_detections == 0
    assert report.duplicate_groups == 0


def test_deterministic_counts_ordering() -> None:
    """Counts mapping keys are ordered lexicographically regardless of input order."""
    detections_order1 = [
        Detection("IR_NATIONAL_ID", 0, 10, "1234567891", "1234567891"),
        Detection("EMAIL", 20, 27, "a@b.com", "a@b.com"),
        Detection(
            "IR_IBAN",
            40,
            66,
            "IR641234567890123456789012",
            "IR641234567890123456789012",
        ),
    ]
    detections_order2 = [
        Detection("EMAIL", 20, 27, "a@b.com", "a@b.com"),
        Detection(
            "IR_IBAN",
            40,
            66,
            "IR641234567890123456789012",
            "IR641234567890123456789012",
        ),
        Detection("IR_NATIONAL_ID", 0, 10, "1234567891", "1234567891"),
    ]
    report1 = report_detections(detections_order1)
    report2 = report_detections(detections_order2)
    assert list(report1.counts.keys()) == ["EMAIL", "IR_IBAN", "IR_NATIONAL_ID"]
    assert list(report2.counts.keys()) == ["EMAIL", "IR_IBAN", "IR_NATIONAL_ID"]
    assert report1 == report2


def test_counts_immutability() -> None:
    """Counts mapping cannot be modified in-place."""
    d = Detection("EMAIL", 0, 7, "a@b.com", "a@b.com")
    report = report_detections([d])
    with pytest.raises((TypeError, AttributeError)):
        report.counts["EMAIL"] = 999  # type: ignore[index]


def test_source_counts_snapshot_isolation() -> None:
    """Mutating source counts dict after constructing DetectionReport
    does not alter report.
    """
    source_counts = {"EMAIL": 1, "IR_MOBILE": 2}
    report = DetectionReport(
        total_detections=3,
        counts=source_counts,
        distinct_types=2,
        has_conflicts=False,
        conflict_pairs=0,
        conflicting_detections=0,
        duplicate_groups=0,
    )
    source_counts["EMAIL"] = 999
    source_counts["NEW_TYPE"] = 50
    assert report.counts["EMAIL"] == 1
    assert "NEW_TYPE" not in report.counts
    assert report.total_detections == 3


def test_input_order_independence() -> None:
    """Permuting input detections results in identical reports."""
    d1 = Detection("EMAIL", 0, 7, "a@b.com", "a@b.com")
    d2 = Detection("IR_MOBILE", 20, 31, "09123456789", "09123456789")
    d3 = Detection("IR_NATIONAL_ID", 50, 60, "1234567891", "1234567891")
    r1 = report_detections([d1, d2, d3])
    r2 = report_detections([d3, d1, d2])
    r3 = report_detections([d2, d3, d1])
    assert r1 == r2 == r3


def test_no_caller_sequence_mutation() -> None:
    """report_detections does not mutate or reorder the input list."""
    d1 = Detection("IR_NATIONAL_ID", 50, 60, "1234567891", "1234567891")
    d2 = Detection("EMAIL", 0, 7, "a@b.com", "a@b.com")
    original = [d1, d2]
    snapshot = list(original)
    report_detections(original)
    assert original == snapshot


# ============================================================================
# Unit Tests: Input Validation & Privacy-Safe Errors
# ============================================================================


def test_reject_string_input() -> None:
    """Passing a str raises TypeError."""
    with pytest.raises(
        TypeError,
        match="detections must be a Sequence of Detection instances, not str or bytes",
    ):
        report_detections("not a list of detections")  # type: ignore[arg-type]


def test_reject_bytes_input() -> None:
    """Passing bytes raises TypeError."""
    with pytest.raises(
        TypeError,
        match="detections must be a Sequence of Detection instances, not str or bytes",
    ):
        report_detections(b"bytes are not valid")  # type: ignore[arg-type]


def test_reject_non_sequence_input() -> None:
    """Passing non-sequence types raises TypeError."""
    with pytest.raises(TypeError, match="detections must be a Sequence"):
        report_detections(12345)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="detections must be a Sequence"):
        report_detections(None)  # type: ignore[arg-type]


def test_reject_invalid_element_with_privacy_safe_error() -> None:
    """Non-Detection elements raise TypeError without exposing item repr
    or secret data.
    """

    class SecretPayload:
        def __repr__(self) -> str:
            return "<SecretPayload patient_ssn='999-00-1111'>"

    bad_list: list[object] = [
        Detection("EMAIL", 0, 7, "a@b.com", "a@b.com"),
        SecretPayload(),
    ]
    with pytest.raises(TypeError) as exc_info:
        report_detections(bad_list)  # type: ignore[arg-type]

    msg = str(exc_info.value)
    assert "Item at index 1 is not a Detection; got SecretPayload" in msg
    assert "999-00-1111" not in msg
    assert "patient_ssn" not in msg


# ============================================================================
# Unit Tests: Conflict & Duplicate Semantics
# ============================================================================


def test_adjacent_spans_do_not_conflict() -> None:
    """Adjacent half-open intervals [0:5] and [5:10] do not conflict."""
    d1 = Detection("TYPE_A", 0, 5, "12345", "12345")
    d2 = Detection("TYPE_B", 5, 10, "67890", "67890")
    report = report_detections([d1, d2])
    assert report.total_detections == 2
    assert report.has_conflicts is False
    assert report.conflict_pairs == 0
    assert report.conflicting_detections == 0
    assert report.duplicate_groups == 0


def test_partial_overlap_conflicts() -> None:
    """Partially overlapping spans [0:10] and [5:15] conflict."""
    d1 = Detection("TYPE_A", 0, 10, "0123456789", "0123456789")
    d2 = Detection("TYPE_B", 5, 15, "5678901234", "5678901234")
    report = report_detections([d1, d2])
    assert report.total_detections == 2
    assert report.has_conflicts is True
    assert report.conflict_pairs == 1
    assert report.conflicting_detections == 2
    assert report.duplicate_groups == 0


def test_nested_overlap_conflicts() -> None:
    """Strictly nested span [5:10] inside [0:20] conflicts."""
    d1 = Detection("OUTER", 0, 20, "x" * 20, "x" * 20)
    d2 = Detection("INNER", 5, 10, "x" * 5, "x" * 5)
    report = report_detections([d1, d2])
    assert report.total_detections == 2
    assert report.has_conflicts is True
    assert report.conflict_pairs == 1
    assert report.conflicting_detections == 2
    assert report.duplicate_groups == 0


def test_transitive_conflict_semantics() -> None:
    """A overlaps B, B overlaps C, but A does not overlap C."""
    d_a = Detection("TYPE_A", 0, 10, "a" * 10, "a" * 10)
    d_b = Detection("TYPE_B", 8, 18, "b" * 10, "b" * 10)
    d_c = Detection("TYPE_C", 16, 26, "c" * 10, "c" * 10)
    report = report_detections([d_a, d_b, d_c])
    assert report.total_detections == 3
    assert report.has_conflicts is True
    assert report.conflict_pairs == 2
    assert report.conflicting_detections == 3
    assert report.duplicate_groups == 0


def test_three_way_complete_overlap() -> None:
    """Three different types occupying the exact same span."""
    d1 = Detection("TYPE_A", 0, 10, "1234567890", "1234567890")
    d2 = Detection("TYPE_B", 0, 10, "1234567890", "1234567890")
    d3 = Detection("TYPE_C", 0, 10, "1234567890", "1234567890")
    report = report_detections([d1, d2, d3])
    assert report.total_detections == 3
    assert report.has_conflicts is True
    assert report.conflict_pairs == 3  # (A-B, A-C, B-C)
    assert report.conflicting_detections == 3
    assert report.duplicate_groups == 0


def test_same_span_different_type() -> None:
    """Two different types on same span conflict with 0 duplicate groups."""
    d1 = Detection("TYPE_A", 0, 3, "val", "val")
    d2 = Detection("TYPE_B", 0, 3, "val", "val")
    report = report_detections([d1, d2])
    assert report.total_detections == 2
    assert report.has_conflicts is True
    assert report.conflict_pairs == 1
    assert report.conflicting_detections == 2
    assert report.duplicate_groups == 0


def test_exact_duplicates_semantics() -> None:
    """Two exactly identical Detection instances conflict and form 1 duplicate group."""
    d1 = Detection("EMAIL", 0, 10, "test@a.com", "test@a.com")
    d2 = Detection("EMAIL", 0, 10, "test@a.com", "test@a.com")
    report = report_detections([d1, d2])
    assert report.total_detections == 2
    assert report.counts["EMAIL"] == 2
    assert report.has_conflicts is True
    assert report.conflict_pairs == 1
    assert report.conflicting_detections == 2
    assert report.duplicate_groups == 1


def test_multiple_duplicate_groups() -> None:
    """Multiple repeated detections form multiple duplicate groups."""
    # Group 1: 3 copies of A
    d_a = Detection("TYPE_A", 0, 5, "val_a", "val_a")
    # Group 2: 2 copies of B
    d_b = Detection("TYPE_B", 20, 25, "val_b", "val_b")
    # Singleton: 1 copy of C
    d_c = Detection("TYPE_C", 40, 45, "val_c", "val_c")

    detections = [d_a, d_a, d_a, d_b, d_b, d_c]
    report = report_detections(detections)
    assert report.total_detections == 6
    assert report.distinct_types == 3
    assert report.duplicate_groups == 2
    # Group 1 has 3 pairwise conflicts (A1-A2, A1-A3, A2-A3);
    # Group 2 has 1 pairwise conflict (B1-B2)
    assert report.conflict_pairs == 4
    # 3 from A + 2 from B participate in conflicts
    assert report.conflicting_detections == 5


# ============================================================================
# Unit Tests: Privacy & Field Inventory
# ============================================================================


def test_report_field_inventory() -> None:
    """DetectionReport public dataclass fields match the exact 7 expected fields."""
    expected_fields = {
        "total_detections",
        "counts",
        "distinct_types",
        "has_conflicts",
        "conflict_pairs",
        "conflicting_detections",
        "duplicate_groups",
    }
    actual_fields = {f.name for f in dataclasses.fields(DetectionReport)}
    assert actual_fields == expected_fields, (
        f"Field inventory mismatch: {actual_fields ^ expected_fields}"
    )


def test_privacy_negative_sentinel_protection() -> None:
    """Sensitive sentinels in raw/normalized values do not appear in report,
    repr, or str.
    """
    sentinel_raw = "SUPER_SECRET_RAW_PII_998877"
    sentinel_norm = "SUPER_SECRET_NRM_PII_998877"
    assert len(sentinel_raw) == len(sentinel_norm)
    d = Detection("CUSTOM_ID", 0, len(sentinel_raw), sentinel_raw, sentinel_norm)
    report = report_detections([d])

    rep = repr(report)
    st = str(report)
    counts_rep = repr(report.counts)
    counts_st = str(report.counts)

    assert sentinel_raw not in rep
    assert sentinel_norm not in rep
    assert sentinel_raw not in st
    assert sentinel_norm not in st
    assert sentinel_raw not in counts_rep
    assert sentinel_norm not in counts_rep
    assert sentinel_raw not in counts_st
    assert sentinel_norm not in counts_st

    # Recursive check across all fields
    for f in dataclasses.fields(report):
        val = getattr(report, f.name)
        assert sentinel_raw not in str(val)
        assert sentinel_norm not in str(val)


def test_no_source_text_or_spans_stored() -> None:
    """DetectionReport does not contain attributes for text, spans, or values."""
    report = report_detections([])
    for prohibited in [
        "text",
        "source_text",
        "detections",
        "values",
        "normalized_values",
        "spans",
        "matches",
        "hashes",
    ]:
        assert not hasattr(report, prohibited)


# ============================================================================
# Unit Tests: Invariant Validation on Direct Construction
# ============================================================================


def test_direct_construction_valid() -> None:
    """Valid direct construction succeeds."""
    report = DetectionReport(
        total_detections=2,
        counts={"EMAIL": 2},
        distinct_types=1,
        has_conflicts=True,
        conflict_pairs=1,
        conflicting_detections=2,
        duplicate_groups=1,
    )
    assert report.total_detections == 2
    assert isinstance(report.counts, Mapping)


@pytest.mark.parametrize(
    "field_name",
    [
        "total_detections",
        "distinct_types",
        "conflict_pairs",
        "conflicting_detections",
        "duplicate_groups",
    ],
)
def test_reject_bool_as_integer_count(field_name: str) -> None:
    """Passing bool for integer count fields is rejected (bool is subclass of int)."""
    kwargs: dict[str, Any] = {
        "total_detections": 1,
        "counts": {"A": 1},
        "distinct_types": 1,
        "has_conflicts": False,
        "conflict_pairs": 0,
        "conflicting_detections": 0,
        "duplicate_groups": 0,
    }
    kwargs[field_name] = True
    with pytest.raises(TypeError, match="must be an integer"):
        DetectionReport(**kwargs)


@pytest.mark.parametrize(
    "field_name",
    [
        "total_detections",
        "distinct_types",
        "conflict_pairs",
        "conflicting_detections",
        "duplicate_groups",
    ],
)
def test_reject_negative_integer_count(field_name: str) -> None:
    """Passing negative values for integer count fields is rejected."""
    kwargs: dict[str, Any] = {
        "total_detections": 1,
        "counts": {"A": 1},
        "distinct_types": 1,
        "has_conflicts": False,
        "conflict_pairs": 0,
        "conflicting_detections": 0,
        "duplicate_groups": 0,
    }
    kwargs[field_name] = -1
    with pytest.raises(ValueError, match="must be non-negative"):
        DetectionReport(**kwargs)


def test_reject_non_bool_has_conflicts() -> None:
    """Passing non-bool for has_conflicts raises TypeError."""
    with pytest.raises(TypeError, match="has_conflicts must be a bool"):
        DetectionReport(
            total_detections=0,
            counts={},
            distinct_types=0,
            has_conflicts=1,  # type: ignore[arg-type]
            conflict_pairs=0,
            conflicting_detections=0,
            duplicate_groups=0,
        )


def test_reject_non_mapping_counts() -> None:
    """Passing non-mapping counts raises TypeError."""
    with pytest.raises(TypeError, match="counts must be a Mapping"):
        DetectionReport(
            total_detections=0,
            counts=[("A", 1)],  # type: ignore[arg-type]
            distinct_types=0,
            has_conflicts=False,
            conflict_pairs=0,
            conflicting_detections=0,
            duplicate_groups=0,
        )


def test_reject_invalid_counts_keys() -> None:
    """Empty or non-string entity type keys in counts raise errors."""
    with pytest.raises(TypeError, match="Entity type keys in counts must be strings"):
        DetectionReport(
            total_detections=1,
            counts={123: 1},  # type: ignore[dict-item]
            distinct_types=1,
            has_conflicts=False,
            conflict_pairs=0,
            conflicting_detections=0,
            duplicate_groups=0,
        )
    with pytest.raises(
        ValueError, match="Entity type keys in counts must be non-empty strings"
    ):
        DetectionReport(
            total_detections=1,
            counts={"": 1},
            distinct_types=1,
            has_conflicts=False,
            conflict_pairs=0,
            conflicting_detections=0,
            duplicate_groups=0,
        )


def test_reject_invalid_counts_values() -> None:
    """Non-positive or non-integer count values in counts raise errors."""
    with pytest.raises(TypeError, match="Count values in counts must be integers"):
        DetectionReport(
            total_detections=1,
            counts={"A": True},
            distinct_types=1,
            has_conflicts=False,
            conflict_pairs=0,
            conflicting_detections=0,
            duplicate_groups=0,
        )
    with pytest.raises(
        ValueError, match="Count values in counts must be positive integers"
    ):
        DetectionReport(
            total_detections=0,
            counts={"A": 0},
            distinct_types=1,
            has_conflicts=False,
            conflict_pairs=0,
            conflicting_detections=0,
            duplicate_groups=0,
        )
    with pytest.raises(
        ValueError, match="Count values in counts must be positive integers"
    ):
        DetectionReport(
            total_detections=0,
            counts={"A": -1},
            distinct_types=1,
            has_conflicts=False,
            conflict_pairs=0,
            conflicting_detections=0,
            duplicate_groups=0,
        )


def test_invariant_distinct_types_mismatch() -> None:
    """distinct_types must equal len(counts)."""
    with pytest.raises(
        ValueError, match="distinct_types .* must equal len\\(counts\\)"
    ):
        DetectionReport(
            total_detections=1,
            counts={"A": 1},
            distinct_types=2,  # mismatch
            has_conflicts=False,
            conflict_pairs=0,
            conflicting_detections=0,
            duplicate_groups=0,
        )


def test_invariant_sum_counts_mismatch() -> None:
    """sum(counts.values()) must equal total_detections."""
    with pytest.raises(
        ValueError, match="sum\\(counts.values\\(\\)\\) .* must equal total_detections"
    ):
        DetectionReport(
            total_detections=5,  # mismatch
            counts={"A": 1, "B": 2},
            distinct_types=2,
            has_conflicts=False,
            conflict_pairs=0,
            conflicting_detections=0,
            duplicate_groups=0,
        )


def test_invariant_conflicting_detections_exceeds_total() -> None:
    """conflicting_detections cannot exceed total_detections."""
    with pytest.raises(
        ValueError, match="conflicting_detections .* cannot exceed total_detections"
    ):
        DetectionReport(
            total_detections=2,
            counts={"A": 2},
            distinct_types=1,
            has_conflicts=True,
            conflict_pairs=1,
            conflicting_detections=3,  # exceeds total
            duplicate_groups=0,
        )


def test_invariant_has_conflicts_mismatch() -> None:
    """has_conflicts must match (conflict_pairs > 0)."""
    with pytest.raises(
        ValueError, match="has_conflicts .* must match conflict_pairs > 0"
    ):
        DetectionReport(
            total_detections=2,
            counts={"A": 2},
            distinct_types=1,
            has_conflicts=False,  # mismatch when conflict_pairs=1
            conflict_pairs=1,
            conflicting_detections=2,
            duplicate_groups=0,
        )
    with pytest.raises(
        ValueError, match="has_conflicts .* must match conflict_pairs > 0"
    ):
        DetectionReport(
            total_detections=2,
            counts={"A": 2},
            distinct_types=1,
            has_conflicts=True,  # mismatch when conflict_pairs=0
            conflict_pairs=0,
            conflicting_detections=0,
            duplicate_groups=0,
        )


def test_invariant_duplicate_groups_exceeds_max_possible() -> None:
    """duplicate_groups cannot exceed total_detections // 2."""
    with pytest.raises(
        ValueError, match="duplicate_groups .* cannot exceed total_detections // 2"
    ):
        DetectionReport(
            total_detections=3,
            counts={"A": 3},
            distinct_types=1,
            has_conflicts=True,
            conflict_pairs=3,
            conflicting_detections=3,
            duplicate_groups=2,  # 3 // 2 = 1, so 2 is impossible
        )


# ============================================================================
# Integration Tests: detection_report
# ============================================================================


def test_detection_report_default_detectors() -> None:
    """Default detection_report detects National ID, Mobile, and IBAN."""
    text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱، همراه: ۰۹۱۲۳۴۵۶۷۸۹، شبا: IR641234567890123456789012"
    report = detection_report(text)
    assert report.total_detections == 3
    assert report.distinct_types == 3
    assert report.counts["IR_NATIONAL_ID"] == 1
    assert report.counts["IR_MOBILE"] == 1
    assert report.counts["IR_IBAN"] == 1
    assert "EMAIL" not in report.counts
    assert "BANK_CARD" not in report.counts
    assert report.has_conflicts is False


def test_detection_report_email_opt_in_and_default_disabled() -> None:
    """Email detection is opt-in and absent from default detection_report."""
    text = "تماس: test@example.com"
    default_rep = detection_report(text)
    assert default_rep.total_detections == 0
    assert "EMAIL" not in default_rep.counts

    opt_in_rep = detection_report(text, detectors=[EmailDetector()])
    assert opt_in_rep.total_detections == 1
    assert opt_in_rep.counts["EMAIL"] == 1


def test_detection_report_bank_card_opt_in_and_default_disabled() -> None:
    """Bank card detection is opt-in and absent from default detection_report."""
    text = "کارت: 1234567890123452"
    default_rep = detection_report(text)
    assert default_rep.total_detections == 0
    assert "BANK_CARD" not in default_rep.counts

    opt_in_rep = detection_report(text, detectors=[BankCardDetector()])
    assert opt_in_rep.total_detections == 1
    assert opt_in_rep.counts["BANK_CARD"] == 1


def test_detection_report_pattern_detector_and_persian_digits() -> None:
    """PatternDetector rules detect identifiers with Persian digits and report
    without PII values.
    """
    detector = PatternDetector(
        [PatternRule(type="MRN", pattern=r"(?<!\w)MRN-[0-9]{6}(?!\w)")]
    )
    text = "پرونده اول: MRN-۱۲۳۴۵۶ و پرونده دوم: MRN-654321"
    report = detection_report(text, detectors=[detector])
    assert report.total_detections == 2
    assert report.counts["MRN"] == 2
    assert report.has_conflicts is False
    assert "۱۲۳۴۵۶" not in repr(report)
    assert "654321" not in repr(report)


def test_explicit_detectors_replace_defaults() -> None:
    """Passing explicit detectors replaces defaults completely."""
    text = "همراه: ۰۹۱۲۳۴۵۶۷۸۹، ایمیل: test@example.com"
    report = detection_report(text, detectors=[EmailDetector()])
    assert report.total_detections == 1
    assert report.counts["EMAIL"] == 1
    assert "IR_MOBILE" not in report.counts


def test_empty_detectors_list_produces_empty_report() -> None:
    """Passing detectors=[] produces an empty report even on text with PII."""
    text = "کد ملی ۱۲۳۴۵۶۷۸۹۱ همراه ۰۹۱۲۳۴۵۶۷۸۹"
    empty_detectors: list[Detector] = []
    report = detection_report(text, detectors=empty_detectors)
    assert report.total_detections == 0
    assert len(report.counts) == 0


def test_overlapping_email_and_bank_card_raw_conflict() -> None:
    """Overlapping email and bank card detections are reported with conflict
    metrics without error.
    """
    text = "1234567890123452@example.com"
    detectors: list[Detector] = [EmailDetector(), BankCardDetector()]
    report = detection_report(text, detectors=detectors)
    assert report.total_detections == 2
    assert report.counts["EMAIL"] == 1
    assert report.counts["BANK_CARD"] == 1
    assert report.has_conflicts is True
    assert report.conflict_pairs == 1
    assert report.conflicting_detections == 2
    assert report.duplicate_groups == 0


def test_duplicated_detector_produces_duplicate_groups() -> None:
    """Running duplicate identical detectors reports duplicates and conflicts."""
    text = "ایمیل: test@example.com"
    detectors: list[Detector] = [EmailDetector(), EmailDetector()]
    report = detection_report(text, detectors=detectors)
    assert report.total_detections == 2
    assert report.counts["EMAIL"] == 2
    assert report.has_conflicts is True
    assert report.conflict_pairs == 1
    assert report.conflicting_detections == 2
    assert report.duplicate_groups == 1


def test_detector_exception_propagates() -> None:
    """Exceptions raised by a detector propagate uncaught out of detection_report."""

    class FailingDetector:
        def detect(self, text: str, normalized_text: str) -> list[Detection]:
            raise RuntimeError("Detector failure")

    with pytest.raises(RuntimeError, match="Detector failure"):
        detection_report("any text", detectors=[FailingDetector()])


def test_report_before_and_after_conflict_resolution() -> None:
    """Demonstrates comparing raw detector evidence vs resolved detections."""
    from fa_redact import detect

    text = "1234567890123452@example.com"
    detectors: list[Detector] = [EmailDetector(), BankCardDetector()]

    # 1. Raw detection report
    raw_detections = detect(text, detectors=detectors)
    raw_report = report_detections(raw_detections)
    assert raw_report.total_detections == 2
    assert raw_report.has_conflicts is True
    assert raw_report.conflict_pairs == 1

    # 2. Resolved detection report (using longest policy)
    resolved_detections = resolve_detection_conflicts(raw_detections, policy="longest")
    resolved_report = report_detections(resolved_detections)
    assert resolved_report.total_detections == 1
    assert resolved_report.counts["EMAIL"] == 1
    assert resolved_report.has_conflicts is False
    assert resolved_report.conflict_pairs == 0
    assert resolved_report.conflicting_detections == 0
