"""High-level detection pipeline for fa-redact."""

from __future__ import annotations

from collections.abc import Sequence

from fa_redact.detectors.iranian_iban import IranianIBANDetector
from fa_redact.detectors.mobile import IranianMobileNumberDetector
from fa_redact.detectors.national_id import IranianNationalIDDetector
from fa_redact.models import Detection
from fa_redact.normalization import normalize_text
from fa_redact.protocols import Detector

_DEFAULT_DETECTORS: tuple[Detector, ...] = (
    IranianNationalIDDetector(),
    IranianMobileNumberDetector(),
    IranianIBANDetector(),
)


def detect(
    text: str,
    *,
    detectors: Sequence[Detector] | None = None,
) -> list[Detection]:
    """Detect Iranian PII entities in text using built-in or custom detectors.

    Applies position-preserving normalization at the pipeline boundary and runs
    each configured detector, returning detected entity spans sorted deterministically
    by character offset.

    Args:
        text: Input string to scan for PII.
        detectors: Sequence of Detector instances to execute. If None (default),
            uses all built-in default detectors (IranianNationalIDDetector,
            IranianMobileNumberDetector, IranianIBANDetector). If an explicit empty
            sequence (e.g. `[]`), no detectors are executed and an empty list is
            returned.

    Returns:
        List of Detection instances sorted by `(start, end, type)`.

    Raises:
        TypeError: If `text` is not a string.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")

    if detectors is None:
        active_detectors: Sequence[Detector] = _DEFAULT_DETECTORS
    else:
        active_detectors = detectors

    if not active_detectors:
        return []

    normalized_text = normalize_text(text)
    detections: list[Detection] = []

    for detector in active_detectors:
        detections.extend(detector.detect(text, normalized_text))

    detections.sort(key=lambda d: (d.start, d.end, d.type))
    return detections
