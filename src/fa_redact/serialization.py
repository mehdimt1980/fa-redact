"""Privacy-safe structured serialization helpers for fa-redact.

Provides explicit, standard-library-only serialization helpers for:
1. Detection structural metadata (type, start, end)
2. DetectionReport aggregate metadata (total_detections, counts, conflict flags)

Privacy contract:
- Detection structural metadata is VALUE-FREE (never contains raw value or
  normalized_value), but contains character offsets (start, end).
- DetectionReport metadata is fully VALUE-FREE and SPAN-FREE.
- Deserialization and arbitrary object serialization are intentionally omitted.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from fa_redact.models import Detection
from fa_redact.reporting import DetectionReport

__all__: list[str] = [
    "detection_to_dict",
    "detections_to_list",
    "dumps_detections",
    "dumps_report",
    "dumps_reports",
    "report_to_dict",
    "reports_to_dict",
]


def detection_to_dict(
    detection: Detection,
) -> dict[str, str | int]:
    """Serialize Detection structural metadata to a primitive dictionary.

    Returns exactly:
    {
        "type": detection.type,
        "start": detection.start,
        "end": detection.end,
    }

    This output is VALUE-FREE (omits raw and normalized values) but retains
    character offsets (start, end).
    """
    if not isinstance(detection, Detection):
        raise TypeError(
            f"detection must be a Detection instance, got {type(detection).__name__}"
        )

    return {
        "type": detection.type,
        "start": detection.start,
        "end": detection.end,
    }


def detections_to_list(
    detections: Sequence[Detection],
) -> list[dict[str, str | int]]:
    """Serialize a sequence of Detection objects to a list of primitive dictionaries.

    Preserves exact sequence order, duplicates, and overlapping spans without
    sorting or filtering.

    Rejects str, bytes, bytearray, and non-Sequence inputs.
    """
    if isinstance(detections, (str, bytes, bytearray)) or not isinstance(
        detections, Sequence
    ):
        type_name = type(detections).__name__
        raise TypeError(
            f"detections must be a Sequence of Detection instances, got {type_name}"
        )

    result: list[dict[str, str | int]] = []
    for idx, item in enumerate(detections):
        if not isinstance(item, Detection):
            type_name = type(item).__name__
            raise TypeError(
                f"item at index {idx} must be a Detection instance, got {type_name}"
            )
        result.append(detection_to_dict(item))
    return result


def report_to_dict(
    report: DetectionReport,
) -> dict[str, object]:
    """Serialize a DetectionReport to a primitive dictionary.

    Returns aggregate counts and conflict indicators only. This representation
    is strictly VALUE-FREE and SPAN-FREE.
    """
    if not isinstance(report, DetectionReport):
        raise TypeError(
            f"report must be a DetectionReport instance, got {type(report).__name__}"
        )

    return {
        "total_detections": report.total_detections,
        "counts": dict(report.counts),
        "distinct_types": report.distinct_types,
        "has_conflicts": report.has_conflicts,
        "conflict_pairs": report.conflict_pairs,
        "conflicting_detections": report.conflicting_detections,
        "duplicate_groups": report.duplicate_groups,
    }


def reports_to_dict(
    reports: Mapping[str, DetectionReport],
) -> dict[str, dict[str, object]]:
    """Serialize a mapping of field paths to DetectionReports to primitive dictionaries.

    Preserves mapping iteration order. Caller-supplied keys (e.g. field paths)
    are preserved as metadata and are not modified or inspected.
    """
    if not isinstance(reports, Mapping):
        type_name = type(reports).__name__
        raise TypeError(
            f"reports must be a Mapping of str to DetectionReport, got {type_name}"
        )

    result: dict[str, dict[str, object]] = {}
    for idx, (key, value) in enumerate(reports.items()):
        if not isinstance(key, str):
            type_name = type(key).__name__
            raise TypeError(
                f"key at mapping entry {idx} must be a str, got {type_name}"
            )
        if not isinstance(value, DetectionReport):
            type_name = type(value).__name__
            raise TypeError(
                f"value at mapping entry {idx} must be a DetectionReport "
                f"instance, got {type_name}"
            )
        result[key] = report_to_dict(value)
    return result


def dumps_detections(
    detections: Sequence[Detection],
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a sequence of Detections to a deterministic JSON string.

    Uses ensure_ascii=False and appends exactly one trailing newline.
    """
    return (
        json.dumps(
            detections_to_list(detections),
            indent=indent,
            ensure_ascii=False,
        )
        + "\n"
    )


def dumps_report(
    report: DetectionReport,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a DetectionReport to a deterministic JSON string.

    Uses ensure_ascii=False and appends exactly one trailing newline.
    """
    return (
        json.dumps(
            report_to_dict(report),
            indent=indent,
            ensure_ascii=False,
        )
        + "\n"
    )


def dumps_reports(
    reports: Mapping[str, DetectionReport],
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a mapping of DetectionReports to a deterministic JSON string.

    Uses ensure_ascii=False and appends exactly one trailing newline.
    """
    return (
        json.dumps(
            reports_to_dict(reports),
            indent=indent,
            ensure_ascii=False,
        )
        + "\n"
    )
