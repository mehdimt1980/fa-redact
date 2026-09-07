"""Lazy batch-processing helpers for fa-redact.

This module provides lightweight, lazy streaming helpers over existing
fa-redact detection, redaction, and reporting APIs for processing multiple
independent text documents one item at a time.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence

from fa_redact.conflicts import ConflictPolicy
from fa_redact.models import Detection
from fa_redact.pipeline import detect
from fa_redact.protocols import Detector
from fa_redact.redaction import redact
from fa_redact.reporting import DetectionReport, detection_report


def _validate_texts_container(texts: Iterable[str]) -> None:
    """Validate that texts is an iterable container and not a string or bytes object."""
    if isinstance(texts, (str, bytes, bytearray)):
        raise TypeError("texts must be an iterable of str documents, not str or bytes")
    if not isinstance(texts, Iterable):
        raise TypeError(f"texts must be an Iterable, got {type(texts).__name__}")


def _snapshot_detectors(
    detectors: Sequence[Detector] | None,
) -> tuple[Detector, ...] | None:
    """Validate and snapshot caller-supplied detector sequence."""
    if detectors is None:
        return None
    if isinstance(detectors, (str, bytes, bytearray)) or not isinstance(
        detectors, Sequence
    ):
        raise TypeError(
            f"detectors must be a Sequence of Detector instances, "
            f"got {type(detectors).__name__}"
        )
    return tuple(detectors)


def _validate_and_snapshot_conflict_config(
    policy: ConflictPolicy,
    type_priority: Sequence[str] | None,
) -> tuple[ConflictPolicy, tuple[str, ...] | None]:
    """Validate and snapshot conflict resolution configuration."""
    if policy not in ("reject", "longest", "priority"):
        raise ValueError(
            f"Invalid conflict policy {policy!r}: policy must be "
            f"'reject', 'longest', or 'priority'"
        )

    if policy in ("reject", "longest"):
        if type_priority is not None:
            raise ValueError(
                f"type_priority is only valid when policy='priority', "
                f"got policy={policy!r}"
            )
        return policy, None

    # policy == "priority"
    if type_priority is None:
        raise ValueError("type_priority must be provided when policy='priority'")
    if isinstance(type_priority, (str, bytes, bytearray)) or not isinstance(
        type_priority, Sequence
    ):
        raise TypeError(
            f"type_priority must be a Sequence of strings, "
            f"got {type(type_priority).__name__}"
        )
    if len(type_priority) == 0:
        raise ValueError("type_priority must be a non-empty sequence of strings")

    seen_types: set[str] = set()
    for idx, t in enumerate(type_priority):
        if not isinstance(t, str):
            raise TypeError(
                f"Item at index {idx} in type_priority is not a string: "
                f"got {type(t).__name__}"
            )
        if not t:
            raise ValueError(f"Item at index {idx} in type_priority is an empty string")
        if t in seen_types:
            raise ValueError(f"Duplicate entity type {t!r} in type_priority")
        seen_types.add(t)

    return policy, tuple(type_priority)


def _detect_many_gen(
    texts: Iterable[str],
    detectors: tuple[Detector, ...] | None,
) -> Iterator[list[Detection]]:
    """Inner generator for detect_many."""
    for idx, item in enumerate(texts):
        if not isinstance(item, str):
            raise TypeError(
                f"item at index {idx} must be a str, got {type(item).__name__}"
            )
        yield detect(item, detectors=detectors)


def _redact_many_gen(
    texts: Iterable[str],
    detectors: tuple[Detector, ...] | None,
    conflict_policy: ConflictPolicy,
    type_priority: tuple[str, ...] | None,
) -> Iterator[str]:
    """Inner generator for redact_many."""
    for idx, item in enumerate(texts):
        if not isinstance(item, str):
            raise TypeError(
                f"item at index {idx} must be a str, got {type(item).__name__}"
            )
        yield redact(
            item,
            detectors=detectors,
            conflict_policy=conflict_policy,
            type_priority=type_priority,
        )


def _report_many_gen(
    texts: Iterable[str],
    detectors: tuple[Detector, ...] | None,
) -> Iterator[DetectionReport]:
    """Inner generator for report_many."""
    for idx, item in enumerate(texts):
        if not isinstance(item, str):
            raise TypeError(
                f"item at index {idx} must be a str, got {type(item).__name__}"
            )
        yield detection_report(item, detectors=detectors)


def detect_many(
    texts: Iterable[str],
    *,
    detectors: Sequence[Detector] | None = None,
) -> Iterator[list[Detection]]:
    """Lazily detect Iranian PII across multiple independent text documents.

    Processes documents one at a time as the returned iterator is consumed,
    preserving input order and without materializing the complete document collection.

    Args:
        texts: Iterable of input strings to scan.
        detectors: Optional sequence of Detector instances to execute. If None,
            uses default built-in detectors. If explicit empty sequence ([]),
            no detectors run.

    Returns:
        Iterator yielding lists of raw Detection instances sorted by
        `(start, end, type)`.

    Raises:
        TypeError: If `texts` is a string/bytes or not an Iterable, or if any
            encountered item is not a string, or if `detectors` has an invalid type.
    """
    _validate_texts_container(texts)
    snapshotted_detectors = _snapshot_detectors(detectors)
    return _detect_many_gen(texts, snapshotted_detectors)


def redact_many(
    texts: Iterable[str],
    *,
    detectors: Sequence[Detector] | None = None,
    conflict_policy: ConflictPolicy = "reject",
    type_priority: Sequence[str] | None = None,
) -> Iterator[str]:
    """Lazily redact detected PII across multiple independent text documents.

    Each document is redacted independently using typed placeholders. Placeholder
    counters restart for each document (no cross-document session sharing).

    Args:
        texts: Iterable of input strings to redact.
        detectors: Optional sequence of Detector instances to execute.
        conflict_policy: Policy for resolving conflicting, overlapping, or
            duplicate detections ('reject', 'longest', or 'priority').
            Default is 'reject'.
        type_priority: Sequence of entity type names in descending priority
            order. Required when conflict_policy='priority', must be None
            otherwise.

    Returns:
        Iterator yielding redacted document strings.

    Raises:
        TypeError: If `texts` is a string/bytes or not an Iterable, or if any
            encountered item is not a string, or if policy arguments have invalid types.
        ValueError: If conflict configuration is invalid or conflict resolution fails.
    """
    _validate_texts_container(texts)
    snapshotted_detectors = _snapshot_detectors(detectors)
    policy, snapshotted_priority = _validate_and_snapshot_conflict_config(
        conflict_policy, type_priority
    )
    return _redact_many_gen(texts, snapshotted_detectors, policy, snapshotted_priority)


def report_many(
    texts: Iterable[str],
    *,
    detectors: Sequence[Detector] | None = None,
) -> Iterator[DetectionReport]:
    """Lazily generate privacy-safe DetectionReports for multiple text documents.

    Processes documents one at a time and returns one value-free DetectionReport
    per document without cross-document aggregation.

    Args:
        texts: Iterable of input strings to scan.
        detectors: Optional sequence of Detector instances to execute.

    Returns:
        Iterator yielding DetectionReport instances.

    Raises:
        TypeError: If `texts` is a string/bytes or not an Iterable, or if any
            encountered item is not a string, or if `detectors` has an invalid type.
    """
    _validate_texts_container(texts)
    snapshotted_detectors = _snapshot_detectors(detectors)
    return _report_many_gen(texts, snapshotted_detectors)


__all__: list[str] = [
    "detect_many",
    "redact_many",
    "report_many",
]
