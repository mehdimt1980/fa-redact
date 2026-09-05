"""Data models for detected identifiers and PII in fa-redact."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Detection:
    """Represents an immutable detected identifier span in text.

    Preserves both the original raw string representation and the
    position-preserving normalized representation.

    Attributes:
        type: Extensible entity identifier type (e.g., 'IR_NATIONAL_ID', 'PATIENT_ID').
        start: Inclusive start character offset in original text.
        end: Exclusive end character offset in original text.
        value: Exact substring extracted from original text.
        normalized_value: Exact substring extracted from normalized text.
    """

    type: str
    start: int
    end: int
    value: str
    normalized_value: str

    def __post_init__(self) -> None:
        """Validate detection field invariants."""
        if not isinstance(self.type, str) or not self.type.strip():
            raise ValueError("type must be a non-empty, non-whitespace string")
        if self.start < 0:
            raise ValueError(f"start must be >= 0, got {self.start}")
        if self.end <= self.start:
            raise ValueError(
                f"end ({self.end}) must be strictly greater than start ({self.start})"
            )
        expected_len = self.end - self.start
        if len(self.value) != expected_len:
            raise ValueError(
                f"len(value) ({len(self.value)}) does not match "
                f"span length ({expected_len})"
            )
        if len(self.normalized_value) != expected_len:
            raise ValueError(
                f"len(normalized_value) ({len(self.normalized_value)}) "
                f"does not match span length ({expected_len})"
            )

    @classmethod
    def from_texts(
        cls,
        *,
        type: str,
        original_text: str,
        normalized_text: str,
        start: int,
        end: int,
    ) -> Detection:
        """Safely construct a Detection by slicing source texts.

        Extracts `value` from `original_text[start:end]` and `normalized_value`
        from `normalized_text[start:end]`.

        Args:
            type: Extensible entity identifier type.
            original_text: Raw input text.
            normalized_text: Position-preserving normalized text of equal length.
            start: Inclusive start character index.
            end: Exclusive end character index.

        Returns:
            Immutable Detection with slices from original and normalized texts.

        Raises:
            ValueError: If texts differ in length, offsets are invalid, or
                offsets fall outside string boundaries.
        """
        if len(original_text) != len(normalized_text):
            raise ValueError(
                f"original_text length ({len(original_text)}) must equal "
                f"normalized_text length ({len(normalized_text)})"
            )
        if start < 0 or end > len(original_text):
            raise ValueError(
                f"Offsets [{start}:{end}] are out of bounds [0:{len(original_text)}]"
            )
        if end <= start:
            raise ValueError(
                f"end ({end}) must be strictly greater than start ({start})"
            )

        value = original_text[start:end]
        normalized_value = normalized_text[start:end]

        return cls(
            type=type,
            start=start,
            end=end,
            value=value,
            normalized_value=normalized_value,
        )
