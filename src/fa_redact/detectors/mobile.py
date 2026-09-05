"""Detector for Iranian mobile phone numbers."""

from __future__ import annotations

import re
from collections.abc import Sequence

from fa_redact.models import Detection
from fa_redact.validators.mobile import is_valid_mobile_number

_ENTITY_TYPE: str = "IR_MOBILE"
_CANDIDATE_PATTERN: re.Pattern[str] = re.compile(
    r"(?<![0-9+])(?:\+98[0-9]{10}|0098[0-9]{10}|0[0-9]{10})(?![0-9])"
)


class IranianMobileNumberDetector:
    """Detects prefix-valid Iranian mobile numbers in text.

    Scans position-preserving normalized text for compact domestic and international
    mobile candidates, validates them against official 2026 CRA NDC mobile prefixes,
    and returns Detection instances preserving both raw and normalized representations.
    """

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        """Detect Iranian mobile numbers across source texts.

        Args:
            original_text: Raw input text.
            normalized_text: Position-preserving normalized text of identical length.

        Returns:
            List of detected Detection instances in textual order.

        Raises:
            ValueError: If original_text and normalized_text differ in length.
        """
        if len(original_text) != len(normalized_text):
            raise ValueError(
                f"original_text length ({len(original_text)}) must equal "
                f"normalized_text length ({len(normalized_text)})"
            )

        detections: list[Detection] = []
        for match in _CANDIDATE_PATTERN.finditer(normalized_text):
            candidate = match.group(0)
            if is_valid_mobile_number(candidate):
                detections.append(
                    Detection.from_texts(
                        type=_ENTITY_TYPE,
                        original_text=original_text,
                        normalized_text=normalized_text,
                        start=match.start(),
                        end=match.end(),
                    )
                )

        return detections
