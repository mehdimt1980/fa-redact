"""Detector for conservative ASCII Internet Email addresses."""

from __future__ import annotations

import re
from collections.abc import Sequence

from fa_redact.models import Detection
from fa_redact.validators.email import is_valid_email

_ENTITY_TYPE: str = "EMAIL"

# Candidate pattern for ASCII email address discovery.
# Negative lookbehind and lookahead ensure clean token boundaries without
# capturing trailing sentence punctuation (such as '.', ',', ';', ':', ')', '>').
_CANDIDATE_PATTERN: re.Pattern[str] = re.compile(
    r"(?<![\w!#$%&'*+\-/=?^_`{|}~.])"
    r"[A-Za-z0-9!#$%&'*+\-/=?^_`{|}~]+(?:\.[A-Za-z0-9!#$%&'*+\-/=?^_`{|}~]+)*"
    r"@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+"
    r"(?![\w-])"
)


class EmailDetector:
    """Detects conservative ASCII Internet Email addresses in text.

    Scans the original input text for ASCII email candidates, validates their
    structure with is_valid_email, and constructs Detection instances preserving
    exact character offsets.

    Note:
        Candidate scanning operates on original_text rather than normalized_text
        to ensure that non-ASCII forms (such as Persian/Arabic-Indic digits in
        email addresses) are not falsely converted and detected as ASCII emails.
    """

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        """Detect conservative ASCII email addresses across source texts.

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
        for match in _CANDIDATE_PATTERN.finditer(original_text):
            candidate = match.group(0)
            if is_valid_email(candidate):
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
