"""Safe placeholder-based redaction for fa-redact."""

from __future__ import annotations

from collections.abc import Sequence

from fa_redact.protocols import Detector
from fa_redact.pseudonymization import PseudonymizationSession


def redact(
    text: str,
    *,
    detectors: Sequence[Detector] | None = None,
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

    Returns:
        The redacted string with detected spans replaced by placeholders.

    Raises:
        TypeError: If `text` is not a string.
        ValueError: If any detected spans overlap, are nested, or are exact duplicates.
    """
    session = PseudonymizationSession()
    return session.pseudonymize(text, detectors=detectors)
