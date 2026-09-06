"""Privacy-safe detection reporting for fa-redact.

This module provides value-free aggregate detection reporting functions
and models that summarize detection evidence without storing, returning,
or persisting raw or normalized PII values, spans, snippets, or PII hashes.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fa_redact.models import Detection
from fa_redact.pipeline import detect
from fa_redact.protocols import Detector


@dataclass(frozen=True, slots=True)
class DetectionReport:
    """Privacy-safe aggregate summary of detector output evidence.

    This report is value-free by design: it does NOT retain source text,
    raw detected values, normalized values, character offsets/spans,
    context snippets, or hashes of detected values.

    Attributes:
        total_detections: Total number of raw Detection instances summarized.
        counts: Immutable mapping from entity type to raw detection count,
            ordered deterministically by entity type name.
        distinct_types: Number of distinct entity types detected (len(counts)).
        has_conflicts: True if at least one pair of detections conflict
            (conflict_pairs > 0).
        conflict_pairs: Number of unordered pairs of overlapping detections.
        conflicting_detections: Number of unique Detection instances
            participating in at least one conflict.
        duplicate_groups: Number of equivalence groups of exactly identical
            Detection objects with multiplicity >= 2.
    """

    total_detections: int
    counts: Mapping[str, int]
    distinct_types: int
    has_conflicts: bool
    conflict_pairs: int
    conflicting_detections: int
    duplicate_groups: int

    def __post_init__(self) -> None:
        """Validate structural invariants and enforce counts immutability."""
        # Validate integer fields (reject bool subclasses of int)
        for field_name, val in (
            ("total_detections", self.total_detections),
            ("distinct_types", self.distinct_types),
            ("conflict_pairs", self.conflict_pairs),
            ("conflicting_detections", self.conflicting_detections),
            ("duplicate_groups", self.duplicate_groups),
        ):
            if type(val) is not int:
                raise TypeError(
                    f"{field_name} must be an integer (got {type(val).__name__})"
                )
            if val < 0:
                raise ValueError(f"{field_name} must be non-negative (got {val})")

        if not isinstance(self.has_conflicts, bool):
            tname = type(self.has_conflicts).__name__
            raise TypeError(f"has_conflicts must be a bool (got {tname})")

        if not isinstance(self.counts, Mapping):
            raise TypeError(
                f"counts must be a Mapping (got {type(self.counts).__name__})"
            )

        # Validate counts items
        for k, v in self.counts.items():
            if not isinstance(k, str):
                tname = type(k).__name__
                raise TypeError(
                    f"Entity type keys in counts must be strings (got {tname})"
                )
            if len(k) == 0:
                raise ValueError("Entity type keys in counts must be non-empty strings")
            if type(v) is not int:
                raise TypeError(
                    f"Count values in counts must be integers (got {type(v).__name__})"
                )
            if v <= 0:
                raise ValueError(
                    f"Count values in counts must be positive integers (got {v})"
                )

        # Validate invariants
        if self.distinct_types != len(self.counts):
            raise ValueError(
                f"distinct_types ({self.distinct_types}) must equal "
                f"len(counts) ({len(self.counts)})"
            )

        if sum(self.counts.values()) != self.total_detections:
            raise ValueError(
                f"sum(counts.values()) ({sum(self.counts.values())}) must equal "
                f"total_detections ({self.total_detections})"
            )

        if self.conflicting_detections > self.total_detections:
            raise ValueError(
                f"conflicting_detections ({self.conflicting_detections}) cannot "
                f"exceed total_detections ({self.total_detections})"
            )

        if self.has_conflicts != (self.conflict_pairs > 0):
            raise ValueError(
                f"has_conflicts ({self.has_conflicts}) must match "
                f"conflict_pairs > 0 ({self.conflict_pairs > 0})"
            )

        if self.duplicate_groups > self.total_detections // 2:
            raise ValueError(
                f"duplicate_groups ({self.duplicate_groups}) cannot exceed "
                f"total_detections // 2 ({self.total_detections // 2})"
            )

        # Snapshot counts to sorted dict and wrap in MappingProxyType
        sorted_counts = {k: self.counts[k] for k in sorted(self.counts.keys())}
        object.__setattr__(self, "counts", MappingProxyType(sorted_counts))


def report_detections(
    detections: Sequence[Detection],
) -> DetectionReport:
    """Summarize a sequence of Detection objects into a privacy-safe DetectionReport.

    Analyzes raw detection evidence to compute entity counts, conflict metrics,
    and duplicate group metrics without retaining or exposing detected values.

    Args:
        detections: Sequence of Detection instances to summarize.

    Returns:
        DetectionReport containing value-free aggregate metadata.

    Raises:
        TypeError: If detections is not a Sequence, is a str or bytes, or contains
            elements that are not Detection instances (with privacy-safe error message).
    """
    if isinstance(detections, (str, bytes, bytearray)):
        raise TypeError(
            "detections must be a Sequence of Detection instances, not str or bytes"
        )

    if not isinstance(detections, Sequence):
        raise TypeError(
            f"detections must be a Sequence, got {type(detections).__name__}"
        )

    for idx, item in enumerate(detections):
        if not isinstance(item, Detection):
            raise TypeError(
                f"Item at index {idx} is not a Detection; got {type(item).__name__}"
            )

    total_detections = len(detections)
    if total_detections == 0:
        return DetectionReport(
            total_detections=0,
            counts={},
            distinct_types=0,
            has_conflicts=False,
            conflict_pairs=0,
            conflicting_detections=0,
            duplicate_groups=0,
        )

    # Count by entity type
    type_counts = Counter(d.type for d in detections)
    sorted_counts = {k: type_counts[k] for k in sorted(type_counts.keys())}
    distinct_types = len(sorted_counts)

    # Conflict audit: half-open span overlap (a.start < b.end and b.start < a.end)
    conflict_pairs = 0
    conflicting_indices: set[int] = set()
    n = total_detections
    for i in range(n):
        d_i = detections[i]
        for j in range(i + 1, n):
            d_j = detections[j]
            if d_i.start < d_j.end and d_j.start < d_i.end:
                conflict_pairs += 1
                conflicting_indices.add(i)
                conflicting_indices.add(j)

    conflicting_detections = len(conflicting_indices)
    has_conflicts = conflict_pairs > 0

    # Duplicate groups: count of Detection equivalence groups with count >= 2
    multiplicity = Counter(detections)
    duplicate_groups = sum(1 for count in multiplicity.values() if count >= 2)

    return DetectionReport(
        total_detections=total_detections,
        counts=sorted_counts,
        distinct_types=distinct_types,
        has_conflicts=has_conflicts,
        conflict_pairs=conflict_pairs,
        conflicting_detections=conflicting_detections,
        duplicate_groups=duplicate_groups,
    )


def detection_report(
    text: str,
    *,
    detectors: Sequence[Detector] | None = None,
) -> DetectionReport:
    """Detect PII in text and return a privacy-safe DetectionReport.

    Convenience function that executes raw detection via `detect()` and
    summarizes the resulting detections via `report_detections()`. Raw
    detector output is preserved without automatic conflict resolution.

    Args:
        text: Input string to scan for PII.
        detectors: Sequence of Detector instances to execute. If None (default),
            uses all built-in default detectors. If explicit list, replaces defaults.

    Returns:
        DetectionReport containing value-free aggregate metadata.
    """
    detections = detect(text, detectors=detectors)
    return report_detections(detections)
