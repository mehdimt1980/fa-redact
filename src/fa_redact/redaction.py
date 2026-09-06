"""Safe placeholder-based redaction for fa-redact."""

from __future__ import annotations

from collections.abc import Sequence

from fa_redact.conflicts import ConflictPolicy
from fa_redact.protocols import Detector
from fa_redact.pseudonymization import PseudonymizationSession


def redact(
    text: str,
    *,
    detectors: Sequence[Detector] | None = None,
    conflict_policy: ConflictPolicy = "reject",
    type_priority: Sequence[str] | None = None,
) -> str:
    """Redact detected Iranian PII using typed, referentially-consistent placeholders.

    Runs the detection pipeline and replaces identified spans with deterministic,
    typed placeholders (e.g. `[IR_NATIONAL_ID_1]`, `[IR_MOBILE_1]`). Within a single
    call, repeated occurrences of the same identifier (matching entity type and
    normalized value) receive the same placeholder.

    Args:
        text: Input string to redact.
        detectors: Optional sequence of Detector instances to execute. If None,
            uses all default built-in detectors. If an explicit empty sequence
            (e.g. `[]`), no detectors run and the original text is returned unchanged.
        conflict_policy: Policy for resolving conflicting, overlapping, or
            duplicate detections ('reject', 'longest', or 'priority').
            Default is 'reject'.
        type_priority: Sequence of entity type names in descending priority
            order. Required when conflict_policy='priority', must be None
            otherwise.

    Returns:
        The redacted string with detected spans replaced by placeholders.

    Raises:
        TypeError: If `text` is not a string, or if policy arguments have invalid types.
        ValueError: If any detected spans overlap, are nested, or are exact duplicates
            under the selected conflict policy.
    """
    session = PseudonymizationSession()
    return session.pseudonymize(
        text,
        detectors=detectors,
        conflict_policy=conflict_policy,
        type_priority=type_priority,
    )
