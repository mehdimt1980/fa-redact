"""Explicit conflict resolution for overlapping, nested, and duplicate detections."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from fa_redact.models import Detection

ConflictPolicy = Literal[
    "reject",
    "longest",
    "priority",
]


def _conflicts(a: Detection, b: Detection) -> bool:
    """Return True if two half-open spans [start, end) overlap."""
    return a.start < b.end and b.start < a.end


def resolve_detection_conflicts(
    detections: Sequence[Detection],
    *,
    policy: ConflictPolicy = "reject",
    type_priority: Sequence[str] | None = None,
) -> list[Detection]:
    """Resolve conflicts among overlapping, nested, and duplicate detections.

    Applies an explicit conflict resolution policy to a collection of detections
    and returns a deterministically sorted list of non-conflicting detections.
    The caller's collection is not modified.

    Policies:
        reject:
            Conservative default. Raises ValueError if any two detections
            overlap, nest, or are exact duplicates.
        longest:
            Greedy policy favoring longer spans. Discards shorter overlapping
            candidates. Collapses exact duplicate detections into one. Raises
            ValueError on ambiguous conflicts between equal-length non-identical
            overlapping spans.
        priority:
            Explicit entity type priority. Higher configured type priority wins
            over lower priority regardless of span length. Same-type conflicts
            are resolved by longer span length, collapsing exact duplicates and
            raising ValueError on equal-length non-identical overlapping spans.
            Every entity type participating in a conflict must be listed in
            type_priority.

    Args:
        detections: Sequence of Detection objects to resolve.
        policy: Conflict resolution policy ('reject', 'longest', or 'priority').
            Default is 'reject'.
        type_priority: Sequence of entity type names in descending priority order
            (first item = highest priority). Required when policy='priority',
            must be None for other policies.

    Returns:
        List of non-conflicting Detection objects sorted by (start, end, type).

    Raises:
        TypeError: If detections is not a Sequence, contains non-Detection items,
            or type_priority is not a Sequence of strings when policy='priority'.
        ValueError: If policy is unrecognized, type_priority configuration is
            invalid, an unlisted entity type participates in a priority conflict,
            equal-length ties cannot be resolved unambiguously, or policy='reject'
            encounters any overlapping/duplicate detections.
    """
    if not isinstance(detections, Sequence) or isinstance(detections, (str, bytes)):
        raise TypeError(
            f"detections must be a Sequence of Detection instances, "
            f"got {type(detections).__name__}"
        )
    for i, item in enumerate(detections):
        if not isinstance(item, Detection):
            raise TypeError(
                f"Item at index {i} is not a Detection instance: "
                f"got {type(item).__name__}"
            )

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
    else:  # policy == "priority"
        if type_priority is None:
            raise ValueError("type_priority must be provided when policy='priority'")
        if not isinstance(type_priority, Sequence) or isinstance(
            type_priority, (str, bytes)
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
                raise ValueError(
                    f"Item at index {idx} in type_priority is an empty string"
                )
            if t in seen_types:
                raise ValueError(f"Duplicate entity type {t!r} in type_priority")
            seen_types.add(t)

    if not detections:
        return []

    # Deterministic baseline sort without mutating caller's collection
    sorted_input = sorted(
        detections,
        key=lambda d: (d.start, d.end, d.type, d.normalized_value, d.value),
    )

    if policy == "reject":
        for i in range(len(sorted_input)):
            for j in range(i + 1, len(sorted_input)):
                d1 = sorted_input[i]
                d2 = sorted_input[j]
                if _conflicts(d1, d2):
                    raise ValueError(
                        f"Overlapping detections at spans [{d1.start}:{d1.end}] "
                        f"({d1.type}) and [{d2.start}:{d2.end}] ({d2.type})"
                    )
        return sorted(sorted_input, key=lambda d: (d.start, d.end, d.type))

    # Deduplicate exact identical detections
    unique_detections: list[Detection] = []
    seen_unique: set[Detection] = set()
    for d in sorted_input:
        if d not in seen_unique:
            seen_unique.add(d)
            unique_detections.append(d)

    if policy == "longest":
        active = list(unique_detections)
        accepted: list[Detection] = []

        while active:
            max_len = max(d.end - d.start for d in active)
            top_candidates = [d for d in active if (d.end - d.start) == max_len]

            # Check for ambiguous equal-length overlaps among top candidates
            for i in range(len(top_candidates)):
                for j in range(i + 1, len(top_candidates)):
                    d1 = top_candidates[i]
                    d2 = top_candidates[j]
                    if _conflicts(d1, d2):
                        raise ValueError(
                            "Ambiguous conflict between equal-length detections at "
                            f"spans [{d1.start}:{d1.end}] ({d1.type}) and "
                            f"[{d2.start}:{d2.end}] ({d2.type})"
                        )

            # Accept non-conflicting top candidates
            accepted.extend(top_candidates)

            # Filter remaining active candidates against newly accepted winners
            active = [
                d
                for d in active
                if not any(_conflicts(d, winner) for winner in top_candidates)
            ]

        accepted.sort(key=lambda d: (d.start, d.end, d.type))
        return accepted

    # policy == "priority"
    assert type_priority is not None
    priority_map = {t: idx for idx, t in enumerate(type_priority)}

    # Verify that all detections participating in any conflict have configured priority
    for i, d1 in enumerate(sorted_input):
        has_conflict = False
        for j, d2 in enumerate(sorted_input):
            if i != j and _conflicts(d1, d2):
                has_conflict = True
                break
        if has_conflict and d1.type not in priority_map:
            raise ValueError(
                f"Conflicting detection of type {d1.type!r} at span "
                f"[{d1.start}:{d1.end}] has no configured priority in type_priority"
            )

    infinity_rank = len(type_priority) + 1

    def candidate_key(d: Detection) -> tuple[int, int]:
        p_rank = priority_map.get(d.type, infinity_rank)
        span_len = d.end - d.start
        return (p_rank, -span_len)

    active = list(unique_detections)
    accepted = []

    while active:
        best_key = min(candidate_key(d) for d in active)
        top_candidates = [d for d in active if candidate_key(d) == best_key]

        # Check for ambiguous equal-priority equal-length overlaps among top candidates
        for i in range(len(top_candidates)):
            for j in range(i + 1, len(top_candidates)):
                d1 = top_candidates[i]
                d2 = top_candidates[j]
                if _conflicts(d1, d2):
                    raise ValueError(
                        "Ambiguous conflict between equal-priority detections at spans "
                        f"[{d1.start}:{d1.end}] ({d1.type}) and "
                        f"[{d2.start}:{d2.end}] ({d2.type})"
                    )

        # Accept non-conflicting top candidates
        accepted.extend(top_candidates)

        # Filter remaining active candidates against newly accepted winners
        active = [
            d
            for d in active
            if not any(_conflicts(d, winner) for winner in top_candidates)
        ]

    accepted.sort(key=lambda d: (d.start, d.end, d.type))
    return accepted
