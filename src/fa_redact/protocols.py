"""Protocols defining structural contracts for fa-redact components."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from fa_redact.models import Detection


class Detector(Protocol):
    """Structural interface for identifier detectors.

    Detectors receive both the raw original text and the position-preserving
    normalized text (guaranteed to have the exact same length), and return a
    sequence of detected entity spans whose offsets map identically onto both.
    """

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        """Detect identifier spans across source texts.

        Args:
            original_text: Original, unmodified input text.
            normalized_text: Position-preserving normalized text of identical length.

        Returns:
            Sequence of detected Detection instances.
        """
        ...
