"""Configurable pattern-based identifier detector."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from fa_redact.models import Detection

_ENTITY_TYPE_PATTERN: re.Pattern[str] = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


@dataclass(frozen=True, slots=True)
class PatternRule:
    """Immutable configuration rule for pattern-based identifier detection.

    Attributes:
        type: Detection entity type and placeholder prefix (e.g. 'MRN', 'PATIENT_ID').
            Must match ^[A-Z][A-Z0-9_]{0,63}$.
        pattern: Python standard-library regular expression string.
        source: Text representation to match against ('normalized' or 'original').
            Default is 'normalized'.
        group: Regex match group index (int) or group name (str) whose span becomes
            the Detection. Default is 0 (the full regex match).
        flags: Standard-library re flags (e.g. re.IGNORECASE). Default is 0.
    """

    type: str
    pattern: str
    source: Literal["normalized", "original"] = "normalized"
    group: int | str = 0
    flags: int = 0

    def __post_init__(self) -> None:
        """Validate pattern rule configuration parameters."""
        if not isinstance(self.type, str) or not _ENTITY_TYPE_PATTERN.fullmatch(
            self.type
        ):
            raise ValueError(
                f"Invalid entity type {self.type!r}: entity type must match "
                f"^[A-Z][A-Z0-9_]{{0,63}}$"
            )
        if not isinstance(self.pattern, str) or not self.pattern:
            raise ValueError(
                f"Invalid pattern for entity type {self.type!r}: "
                f"pattern must be a non-empty string"
            )
        if self.source not in ("normalized", "original"):
            raise ValueError(
                f"Invalid source {self.source!r} for entity type {self.type!r}: "
                f"source must be 'normalized' or 'original'"
            )
        if isinstance(self.group, int):
            if self.group < 0:
                raise ValueError(
                    f"Invalid group index {self.group} for entity type "
                    f"{self.type!r}: group index must be non-negative"
                )
        elif isinstance(self.group, str):
            if not self.group:
                raise ValueError(
                    f"Invalid group name {self.group!r} for entity type "
                    f"{self.type!r}: group name must be a non-empty string"
                )
        else:
            raise ValueError(
                f"Invalid group type {type(self.group).__name__} for entity type "
                f"{self.type!r}: group must be int or str"
            )
        if not isinstance(self.flags, int):
            raise ValueError(
                f"Invalid flags type {type(self.flags).__name__} for entity type "
                f"{self.type!r}: flags must be an int"
            )

        try:
            compiled = re.compile(self.pattern, self.flags)
        except re.error as err:
            raise ValueError(
                f"Invalid regular expression pattern {self.pattern!r} for "
                f"entity type {self.type!r}: {err}"
            ) from None

        if isinstance(self.group, int):
            if self.group > compiled.groups:
                raise ValueError(
                    f"Configured group index {self.group} out of range for "
                    f"entity type {self.type!r} "
                    f"(pattern has {compiled.groups} capture groups)"
                )
        elif isinstance(self.group, str):
            if self.group not in compiled.groupindex:
                raise ValueError(
                    f"Configured named group {self.group!r} not found in "
                    f"pattern for entity type {self.type!r}"
                )


class PatternDetector:
    """Detects configurable, institution-specific identifiers using custom regex rules.

    Satisfies the Detector structural protocol. Rules are compiled once during
    initialization and can be reused efficiently across multiple texts.
    """

    def __init__(self, rules: Sequence[PatternRule]) -> None:
        """Initialize PatternDetector with a sequence of PatternRule instances.

        Args:
            rules: Sequence of PatternRule configuration objects. Must be non-empty.

        Raises:
            ValueError: If rules is empty, regex compilation fails, or configured
                group index/name does not exist in the compiled pattern.
            TypeError: If rules is not a sequence or contains non-PatternRule items.
        """
        if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes)):
            raise TypeError(
                f"rules must be a sequence of PatternRule instances, "
                f"got {type(rules).__name__}"
            )
        if not rules:
            raise ValueError(
                "rules must be a non-empty sequence of PatternRule instances"
            )

        compiled_rules: list[tuple[PatternRule, re.Pattern[str]]] = []
        for i, rule in enumerate(rules):
            if not isinstance(rule, PatternRule):
                raise TypeError(
                    f"Rule at index {i} is not a PatternRule instance: "
                    f"got {type(rule).__name__}"
                )
            try:
                compiled = re.compile(rule.pattern, rule.flags)
            except re.error as err:
                raise ValueError(
                    f"Invalid regular expression pattern {rule.pattern!r} for "
                    f"entity type {rule.type!r}: {err}"
                ) from None

            if isinstance(rule.group, int):
                if not (0 <= rule.group <= compiled.groups):
                    raise ValueError(
                        f"Configured group index {rule.group} out of range for "
                        f"entity type {rule.type!r} "
                        f"(pattern has {compiled.groups} capture groups)"
                    )
            elif isinstance(rule.group, str):
                if rule.group not in compiled.groupindex:
                    raise ValueError(
                        f"Configured named group {rule.group!r} not found in "
                        f"pattern for entity type {rule.type!r}"
                    )
            compiled_rules.append((rule, compiled))

        self._rules: tuple[PatternRule, ...] = tuple(rule for rule, _ in compiled_rules)
        self._compiled_rules: tuple[tuple[PatternRule, re.Pattern[str]], ...] = tuple(
            compiled_rules
        )

    @property
    def rules(self) -> tuple[PatternRule, ...]:
        """Return an immutable tuple of configured PatternRule instances."""
        return self._rules

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        """Detect configured patterns across source texts.

        Args:
            original_text: Raw input text.
            normalized_text: Position-preserving normalized text of equal length.

        Returns:
            Sequence of Detection instances sorted by (start, end, type).

        Raises:
            ValueError: If original_text and normalized_text differ in length,
                or if a match produces a zero-length span or nonparticipating group.
        """
        if len(original_text) != len(normalized_text):
            raise ValueError(
                f"original_text length ({len(original_text)}) must equal "
                f"normalized_text length ({len(normalized_text)})"
            )

        detections: list[Detection] = []
        for rule, pattern in self._compiled_rules:
            target_text = (
                normalized_text if rule.source == "normalized" else original_text
            )
            for match in pattern.finditer(target_text):
                start, end = match.span(rule.group)
                if start == -1 or end == -1:
                    raise ValueError(
                        f"Capture group {rule.group!r} did not participate in "
                        f"match for rule {rule.type!r}"
                    )
                if start == end:
                    raise ValueError(
                        f"Zero-length match detected for rule {rule.type!r} "
                        f"at offset {start}"
                    )
                detections.append(
                    Detection.from_texts(
                        type=rule.type,
                        original_text=original_text,
                        normalized_text=normalized_text,
                        start=start,
                        end=end,
                    )
                )

        detections.sort(key=lambda d: (d.start, d.end, d.type))
        return detections
