"""Tests for Detection data model and Detector protocol (Phase 3)."""

from collections.abc import Sequence
from dataclasses import FrozenInstanceError

import pytest

from fa_redact import Detection, normalize_text
from fa_redact.protocols import Detector


def test_detection_basic_construction() -> None:
    """Verify a valid Detection instance can be constructed and accessed."""
    detection = Detection(
        type="IR_NATIONAL_ID",
        start=10,
        end=20,
        value="۰۰۱۲۳۴۵۶۷۸",
        normalized_value="0012345678",
    )
    assert detection.type == "IR_NATIONAL_ID"
    assert detection.start == 10
    assert detection.end == 20
    assert detection.value == "۰۰۱۲۳۴۵۶۷۸"
    assert detection.normalized_value == "0012345678"


def test_detection_immutability() -> None:
    """Verify that Detection is frozen and fields cannot be mutated."""
    detection = Detection(
        type="TEST",
        start=0,
        end=3,
        value="۱۲۳",
        normalized_value="123",
    )
    with pytest.raises(FrozenInstanceError):
        detection.start = 1  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        detection.type = "NEW_TYPE"  # type: ignore[misc]


def test_detection_equality_and_hashing() -> None:
    """Verify value equality and hashing for identical and differing instances."""
    d1 = Detection(
        type="IR_MOBILE",
        start=0,
        end=11,
        value="۰۹۱۲۳۴۵۶۷۸۹",
        normalized_value="09123456789",
    )
    d2 = Detection(
        type="IR_MOBILE",
        start=0,
        end=11,
        value="۰۹۱۲۳۴۵۶۷۸۹",
        normalized_value="09123456789",
    )
    d3 = Detection(
        type="IR_MOBILE",
        start=1,
        end=12,
        value="۰۹۱۲۳۴۵۶۷۸۹",
        normalized_value="09123456789",
    )

    assert d1 == d2
    assert hash(d1) == hash(d2)
    assert d1 != d3


def test_detection_invalid_type() -> None:
    """Verify rejection of empty, whitespace-only, or non-string entity types."""
    with pytest.raises(ValueError, match="type must be a non-empty"):
        Detection(type="", start=0, end=3, value="123", normalized_value="123")

    with pytest.raises(ValueError, match="type must be a non-empty"):
        Detection(type="   ", start=0, end=3, value="123", normalized_value="123")

    with pytest.raises(ValueError, match="type must be a non-empty"):
        Detection(
            type=None,  # type: ignore[arg-type]
            start=0,
            end=3,
            value="123",
            normalized_value="123",
        )


def test_detection_invalid_spans() -> None:
    """Verify rejection of negative or inverted start/end offsets."""
    with pytest.raises(ValueError, match="start must be >= 0"):
        Detection(
            type="TEST",
            start=-1,
            end=2,
            value="123",
            normalized_value="123",
        )

    with pytest.raises(ValueError, match="must be strictly greater than start"):
        Detection(
            type="TEST",
            start=5,
            end=5,
            value="",
            normalized_value="",
        )

    with pytest.raises(ValueError, match="must be strictly greater than start"):
        Detection(
            type="TEST",
            start=5,
            end=2,
            value="123",
            normalized_value="123",
        )


def test_detection_value_length_mismatch() -> None:
    """Verify rejection when value length does not match (end - start)."""
    with pytest.raises(ValueError, match="len\\(value\\)"):
        Detection(
            type="TEST",
            start=0,
            end=5,
            value="123",  # len 3 != 5
            normalized_value="12345",
        )


def test_detection_normalized_value_length_mismatch() -> None:
    """Verify rejection when normalized_value length does not match (end - start)."""
    with pytest.raises(ValueError, match="len\\(normalized_value\\)"):
        Detection(
            type="TEST",
            start=0,
            end=3,
            value="123",
            normalized_value="1234",  # len 4 != 3
        )


def test_detection_from_texts_valid() -> None:
    """Verify safe construction using Detection.from_texts with real normalization."""
    original = "شناسه: ۱۲٣۴۵"
    normalized = normalize_text(original)

    start = original.index("۱۲٣۴۵")
    end = start + len("۱۲٣۴۵")

    detection = Detection.from_texts(
        type="ID",
        original_text=original,
        normalized_text=normalized,
        start=start,
        end=end,
    )

    assert detection.type == "ID"
    assert detection.start == start
    assert detection.end == end
    assert detection.value == "۱۲٣۴۵"
    assert detection.normalized_value == "12345"
    assert len(detection.value) == end - start
    assert len(detection.normalized_value) == end - start


def test_detection_from_texts_different_length_inputs() -> None:
    """Verify from_texts rejects source texts of differing lengths."""
    with pytest.raises(ValueError, match="must equal normalized_text length"):
        Detection.from_texts(
            type="TEST",
            original_text="abc",
            normalized_text="abcd",
            start=0,
            end=2,
        )


def test_detection_from_texts_out_of_bounds() -> None:
    """Verify from_texts rejects spans that exceed the text boundary or are negative."""
    text = "سلام ۱۲۳"
    norm = normalize_text(text)

    with pytest.raises(ValueError, match="out of bounds"):
        Detection.from_texts(
            type="TEST",
            original_text=text,
            normalized_text=norm,
            start=0,
            end=len(text) + 1,
        )

    with pytest.raises(ValueError, match="out of bounds"):
        Detection.from_texts(
            type="TEST",
            original_text=text,
            normalized_text=norm,
            start=-1,
            end=3,
        )

    with pytest.raises(ValueError, match="must be strictly greater than start"):
        Detection.from_texts(
            type="TEST",
            original_text=text,
            normalized_text=norm,
            start=4,
            end=4,
        )


def test_detection_healthcare_offset_identity() -> None:
    """Verify slicing on clinical text retrieves matching raw/norm values."""
    original = "بیمار با شناسه پرونده ۱۲۳٤٥ و شماره ملی ۰۰۱٢٣٤٥٦٧٨ بستری شد."
    normalized = normalize_text(original)

    # Validate that lengths match
    assert len(original) == len(normalized)

    # 1. MRN / case ID extraction
    mrn_raw = "۱۲۳٤٥"
    mrn_start = original.index(mrn_raw)
    mrn_end = mrn_start + len(mrn_raw)

    mrn_det = Detection.from_texts(
        type="CASE_ID",
        original_text=original,
        normalized_text=normalized,
        start=mrn_start,
        end=mrn_end,
    )
    assert mrn_det.value == mrn_raw
    assert mrn_det.normalized_value == "12345"
    assert original[mrn_det.start : mrn_det.end] == mrn_raw
    assert normalized[mrn_det.start : mrn_det.end] == "12345"

    # 2. National ID extraction
    nid_raw = "۰۰۱٢٣٤٥٦٧٨"
    nid_start = original.index(nid_raw)
    nid_end = nid_start + len(nid_raw)

    nid_det = Detection.from_texts(
        type="NATIONAL_ID",
        original_text=original,
        normalized_text=normalized,
        start=nid_start,
        end=nid_end,
    )
    assert nid_det.value == nid_raw
    assert nid_det.normalized_value == "0012345678"
    assert original[nid_det.start : nid_det.end] == nid_raw
    assert normalized[nid_det.start : nid_det.end] == "0012345678"


def test_detector_protocol_type_compatibility() -> None:
    """Verify a conforming detector class satisfies the Detector Protocol."""

    class DummyDetector:
        """Conforming dummy detector implementing the Detector protocol."""

        def detect(
            self,
            original_text: str,
            normalized_text: str,
        ) -> Sequence[Detection]:
            if not original_text:
                return []
            return [
                Detection.from_texts(
                    type="DUMMY",
                    original_text=original_text,
                    normalized_text=normalized_text,
                    start=0,
                    end=len(original_text),
                )
            ]

    # Type check contract conformance
    detector: Detector = DummyDetector()
    results = detector.detect("تست", "تست")
    assert len(results) == 1
    assert results[0].type == "DUMMY"
    assert results[0].value == "تست"
