"""Detector for Iranian Legal Entity National IDs (شناسه ملی اشخاص حقوقی)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from fa_redact.models import Detection
from fa_redact.validators.legal_entity_id import is_valid_iranian_legal_entity_id

_ENTITY_TYPE: str = "IR_LEGAL_ENTITY_ID"
_CANDIDATE_PATTERN: re.Pattern[str] = re.compile(r"(?<![0-9])[0-9]{11}(?![0-9])")


class IranianLegalEntityIDDetector:
    """Detects checksum-valid Iranian Legal Entity National IDs in text.

    Scans position-preserving normalized text for 11-digit candidate sequences,
    validates their modulo-11 checksums using the Variant A algorithm, and
    constructs Detection instances preserving both original raw and normalized
    representations.

    Integration Policy:
        Strictly OPT-IN. Never included in global default detector pipeline.
    """

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        """Detect Iranian Legal Entity National IDs across source texts.

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
            if is_valid_iranian_legal_entity_id(candidate):
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
