"""Safe placeholder-based redaction for fa-redact."""

from __future__ import annotations

from collections.abc import Sequence

from fa_redact.pipeline import detect
from fa_redact.protocols import Detector


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
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")

    detections = detect(text, detectors=detectors)
    if not detections:
        return text

    # Validate that detections do not overlap, nest, or duplicate
    for i in range(1, len(detections)):
        prev = detections[i - 1]
        curr = detections[i]
        if curr.start < prev.end:
            raise ValueError(
                f"Overlapping detections at spans [{prev.start}:{prev.end}] "
                f"({prev.type}) and [{curr.start}:{curr.end}] ({curr.type})"
            )

    placeholder_by_identity: dict[tuple[str, str], str] = {}
    assigned_placeholders: set[str] = set()
    counters_by_type: dict[str, int] = {}

    pieces: list[str] = []
    cursor = 0

    for d in detections:
        identity = (d.type, d.normalized_value)
        placeholder = placeholder_by_identity.get(identity)
        if placeholder is None:
            counter = counters_by_type.get(d.type, 0)
            while True:
                counter += 1
                candidate = f"[{d.type}_{counter}]"
                if candidate not in text and candidate not in assigned_placeholders:
                    placeholder = candidate
                    break
            counters_by_type[d.type] = counter
            placeholder_by_identity[identity] = placeholder
            assigned_placeholders.add(placeholder)

        pieces.append(text[cursor : d.start])
        pieces.append(placeholder)
        cursor = d.end

    pieces.append(text[cursor:])
    return "".join(pieces)
