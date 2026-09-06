"""Structured data helpers for fa-redact.

This module provides conservative, non-destructive helpers for applying
fa-redact detection, redaction, and reporting capabilities to explicitly
selected fields in Python mappings / JSON-like records.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fa_redact.conflicts import ConflictPolicy
from fa_redact.models import Detection
from fa_redact.pipeline import detect
from fa_redact.protocols import Detector
from fa_redact.pseudonymization import PseudonymizationSession
from fa_redact.reporting import DetectionReport, report_detections


def _parse_path(path: str) -> tuple[str, ...]:
    """Parse and validate a dot-separated field path.

    Args:
        path: Dot-separated path string (e.g., 'note', 'metadata.contact').

    Returns:
        Tuple of path segment strings.

    Raises:
        ValueError: If path is empty, has leading/trailing dots, or contains
            consecutive empty segments (e.g., 'a..b').
    """
    if not isinstance(path, str):
        raise TypeError(f"Field path must be a str, got {type(path).__name__}")
    if not path:
        raise ValueError("Field path cannot be empty")

    segments = path.split(".")
    for seg in segments:
        if not seg:
            raise ValueError(f"Invalid field path syntax: {path!r}")

    return tuple(segments)


def _validate_fields(fields: Sequence[str]) -> list[tuple[str, tuple[str, ...]]]:
    """Validate fields sequence, check path syntax, and reject duplicate paths.

    Args:
        fields: Sequence of dot-separated field path strings.

    Returns:
        List of pairs (original_path_str, parsed_segments_tuple).

    Raises:
        TypeError: If fields is not a Sequence or contains non-string items.
        ValueError: If any path syntax is invalid or duplicate paths are provided.
    """
    if isinstance(fields, (str, bytes, bytearray)):
        raise TypeError(
            f"fields must be a Sequence of strings, not {type(fields).__name__}"
        )
    if not isinstance(fields, Sequence):
        raise TypeError(f"fields must be a Sequence, got {type(fields).__name__}")

    seen_paths: set[str] = set()
    validated: list[tuple[str, tuple[str, ...]]] = []

    for idx, f in enumerate(fields):
        if not isinstance(f, str):
            raise TypeError(
                f"Field path at index {idx} must be a str, got {type(f).__name__}"
            )
        if f in seen_paths:
            raise ValueError(f"Duplicate field path: {f!r}")
        seen_paths.add(f)
        parsed = _parse_path(f)
        validated.append((f, parsed))

    return validated


def _extract_target_string(
    record: Mapping[str, Any],
    path_str: str,
    segments: tuple[str, ...],
) -> str:
    """Extract string value at path from mapping, raising privacy-safe errors.

    Args:
        record: Root mapping structure.
        path_str: Original path string for diagnostic error messages.
        segments: Parsed tuple of path key segments.

    Returns:
        Target string value.

    Raises:
        KeyError: If an intermediate or leaf key is missing.
        TypeError: If an intermediate value is not a Mapping or leaf is not a str.
    """
    current: Any = record

    for _idx, key in enumerate(segments[:-1]):
        if not isinstance(current, Mapping) or isinstance(
            current, (str, bytes, bytearray)
        ):
            raise TypeError(
                f"Field path {path_str!r} failed: intermediate value before "
                f"{key!r} is not a Mapping (got {type(current).__name__})"
            )
        if key not in current:
            raise KeyError(
                f"Field path {path_str!r} not found: missing intermediate key {key!r}"
            )
        current = current[key]

    leaf_key = segments[-1]
    if not isinstance(current, Mapping) or isinstance(current, (str, bytes, bytearray)):
        raise TypeError(
            f"Field path {path_str!r} failed: intermediate container for "
            f"{leaf_key!r} is not a Mapping (got {type(current).__name__})"
        )
    if leaf_key not in current:
        raise KeyError(f"Field path {path_str!r} not found: missing key {leaf_key!r}")

    leaf_val = current[leaf_key]
    if not isinstance(leaf_val, str):
        raise TypeError(
            f"Field at path {path_str!r} must be a str, got {type(leaf_val).__name__}"
        )

    return leaf_val


def _copy_mapping_tree(val: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively copy mapping containers as plain dictionaries."""
    result: dict[str, Any] = {}
    for k, v in val.items():
        if isinstance(v, Mapping) and not isinstance(v, (str, bytes, bytearray)):
            result[k] = _copy_mapping_tree(v)
        else:
            result[k] = v
    return result


def detect_fields(
    record: Mapping[str, Any],
    fields: Sequence[str],
    *,
    detectors: Sequence[Detector] | None = None,
) -> dict[str, list[Detection]]:
    """Detect PII entities within explicitly selected string fields of a mapping.

    Processes only the exact paths provided in `fields`. Does NOT perform blind
    recursive traversal of the mapping.

    Args:
        record: Mapping (e.g. dictionary / JSON-like record) containing target fields.
        fields: Sequence of dot-separated path strings targeting string fields.
        detectors: Sequence of Detector instances to execute. If None (default),
            uses default built-in detectors. If explicit list, replaces defaults.

    Returns:
        Dictionary mapping each path in `fields` to its list of Detection objects
        sorted by `(start, end, type)`.

    Raises:
        TypeError: If `record` is not a Mapping, `fields` is not a Sequence of
            strings, an intermediate path element is not a Mapping, or a target
            field is not a string.
        ValueError: If a path has invalid syntax or duplicate paths are provided.
        KeyError: If any path or intermediate key does not exist in `record`.
    """
    if isinstance(record, (str, bytes, bytearray)) or not isinstance(record, Mapping):
        raise TypeError(f"record must be a Mapping, got {type(record).__name__}")

    validated_fields = _validate_fields(fields)
    results: dict[str, list[Detection]] = {}

    for path_str, segments in validated_fields:
        target_str = _extract_target_string(record, path_str, segments)
        results[path_str] = detect(target_str, detectors=detectors)

    return results


def report_fields(
    record: Mapping[str, Any],
    fields: Sequence[str],
    *,
    detectors: Sequence[Detector] | None = None,
) -> dict[str, DetectionReport]:
    """Generate privacy-safe DetectionReports for explicitly selected fields.

    Processes only the exact paths provided in `fields`. Does NOT perform blind
    recursive traversal of the mapping.

    Args:
        record: Mapping (e.g. dictionary / JSON-like record) containing target fields.
        fields: Sequence of dot-separated path strings targeting string fields.
        detectors: Sequence of Detector instances to execute. If None (default),
            uses default built-in detectors. If explicit list, replaces defaults.

    Returns:
        Dictionary mapping each path in `fields` to its privacy-safe DetectionReport.

    Raises:
        TypeError: If `record` is not a Mapping, `fields` is not a Sequence of
            strings, an intermediate path element is not a Mapping, or a target
            field is not a string.
        ValueError: If a path has invalid syntax or duplicate paths are provided.
        KeyError: If any path or intermediate key does not exist in `record`.
    """
    if isinstance(record, (str, bytes, bytearray)) or not isinstance(record, Mapping):
        raise TypeError(f"record must be a Mapping, got {type(record).__name__}")

    validated_fields = _validate_fields(fields)
    reports: dict[str, DetectionReport] = {}

    for path_str, segments in validated_fields:
        target_str = _extract_target_string(record, path_str, segments)
        detections = detect(target_str, detectors=detectors)
        reports[path_str] = report_detections(detections)

    return reports


def redact_fields(
    record: Mapping[str, Any],
    fields: Sequence[str],
    *,
    detectors: Sequence[Detector] | None = None,
    conflict_policy: ConflictPolicy = "reject",
    type_priority: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Redact PII within explicitly selected string fields of a mapping.

    Processes only the exact paths provided in `fields`. Maintains record-wide
    referential consistency and placeholder reservation across all selected
    fields within a single call.

    Does NOT mutate the caller's input mapping or nested mappings; returns a
    transformed dictionary copy with redacted string placeholders at target fields.

    All non-target keys, intermediate mappings, numbers, booleans, None, lists,
    and unaffected strings are preserved intact.

    Args:
        record: Mapping (e.g. dictionary / JSON-like record) containing target fields.
        fields: Sequence of dot-separated path strings targeting string fields.
        detectors: Optional sequence of Detector instances to execute. If None,
            uses default built-in detectors.
        conflict_policy: Policy for resolving conflicting, overlapping, or
            duplicate detections ('reject', 'longest', or 'priority').
            Default is 'reject'.
        type_priority: Sequence of entity type names in descending priority
            order. Required when conflict_policy='priority', must be None
            otherwise.

    Returns:
        Transformed dictionary copy with target fields redacted.

    Raises:
        TypeError: If `record` is not a Mapping, `fields` is not a Sequence of
            strings, an intermediate path element is not a Mapping, or a target
            field is not a string.
        ValueError: If a path has invalid syntax, duplicate paths are provided,
            or conflict resolution fails.
        KeyError: If any path or intermediate key does not exist in `record`.
    """
    if isinstance(record, (str, bytes, bytearray)) or not isinstance(record, Mapping):
        raise TypeError(f"record must be a Mapping, got {type(record).__name__}")

    validated_fields = _validate_fields(fields)
    if not validated_fields:
        return _copy_mapping_tree(record)

    # 1. Validate all fields and extract target strings before making any modifications
    target_strings: list[tuple[str, tuple[str, ...], str]] = []
    for path_str, segments in validated_fields:
        target_val = _extract_target_string(record, path_str, segments)
        target_strings.append((path_str, segments, target_val))

    # 2. Redact target strings using a single local PseudonymizationSession across
    # all selected fields in deterministic fields order. This underlying core mechanism
    # ensures record-wide referential consistency (identical entity instances across
    # multiple fields receive the same placeholder) and preserves placeholder literal
    # collision avoidance across fields without exposing session state to the caller.
    session = PseudonymizationSession()
    redacted_values: list[tuple[tuple[str, ...], str]] = []
    for _path_str, segments, target_val in target_strings:
        redacted_val = session.pseudonymize(
            target_val,
            detectors=detectors,
            conflict_policy=conflict_policy,
            type_priority=type_priority,
        )
        redacted_values.append((segments, redacted_val))

    # 3. Construct non-destructive transformed dictionary
    result: dict[str, Any] = _copy_mapping_tree(record)

    for segments, new_val in redacted_values:
        curr: dict[str, Any] = result
        for seg in segments[:-1]:
            curr = curr[seg]
        curr[segments[-1]] = new_val

    return result
