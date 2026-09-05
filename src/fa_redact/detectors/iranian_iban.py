"""Detector for Iranian International Bank Account Numbers (IBAN / Sheba)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from fa_redact.models import Detection
from fa_redact.validators.iranian_iban import is_valid_iranian_iban

_ENTITY_TYPE: str = "IR_IBAN"
_CANDIDATE_PATTERN: re.Pattern[str] = re.compile(r"(?<!\w)IR[0-9]{24}(?!\w)")


class IranianIBANDetector:
    """Detects checksum-valid Iranian IBANs (Sheba) in text.

    Scans position-preserving normalized text for 26-character Iranian IBAN candidates,
    validates their MOD-97 checksums, and constructs Detection instances preserving both
    original raw and normalized representations.
    """

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        """Detect Iranian IBANs across source texts.

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
            if is_valid_iranian_iban(candidate):
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
