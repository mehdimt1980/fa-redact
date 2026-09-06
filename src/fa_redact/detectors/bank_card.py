"""Detector for 16-digit payment card numbers (Primary Account Number / PAN)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from fa_redact.models import Detection
from fa_redact.validators.bank_card import is_valid_bank_card_number

_ENTITY_TYPE: str = "BANK_CARD"
_CANDIDATE_PATTERN: re.Pattern[str] = re.compile(r"(?<!\w)[0-9]{16}(?!\w)")


class BankCardDetector:
    """Detects checksum-valid 16-digit bank card numbers (PAN) in text.

    Scans position-preserving normalized text for 16-digit candidate sequences,
    validates their Luhn checksums and defensive structure via
    is_valid_bank_card_number, and constructs Detection instances preserving
    both original raw and normalized representations.
    """

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        """Detect 16-digit payment card numbers across source texts.

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
            if is_valid_bank_card_number(candidate):
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
