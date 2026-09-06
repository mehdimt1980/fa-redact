"""Stateful pseudonymization sessions with stable mappings and safe restoration."""

from __future__ import annotations

import re
from collections.abc import Sequence

from fa_redact.conflicts import ConflictPolicy, resolve_detection_conflicts
from fa_redact.pipeline import detect
from fa_redact.protocols import Detector

_PLACEHOLDER_PATTERN = re.compile(r"\[[^\[\]\r\n]+_[1-9][0-9]*\]")


class PseudonymizationSession:
    """Stateful pseudonymization session for Iranian PII.

    Maintains a local-only mapping between detected PII identities and stable,
    typed placeholders across multiple messages or conversation turns. Allows
    safe restoration of placeholders in downstream AI/LLM responses.
    """

    def __init__(self) -> None:
        self._identity_to_placeholder: dict[tuple[str, str], str] = {}
        self._placeholder_to_value: dict[str, str] = {}
        self._counters_by_type: dict[str, int] = {}
        self._reserved_placeholders: set[str] = set()

    @property
    def mapping(self) -> dict[str, str]:
        """Return a shallow copy of the placeholder-to-value mapping.

        The returned mapping contains original sensitive PII values and must
        be treated as sensitive data.
        """
        return self._placeholder_to_value.copy()

    def pseudonymize(
        self,
        text: str,
        *,
        detectors: Sequence[Detector] | None = None,
        conflict_policy: ConflictPolicy = "reject",
        type_priority: Sequence[str] | None = None,
    ) -> str:
        """Pseudonymize detected PII in text using stable, typed placeholders.

        Identities are tracked across calls on this session. If an identifier
        with the same entity type and normalized value was previously observed,
        its existing placeholder is reused. New identifiers receive subsequent
        per-type indices and record their first-observed raw representation for
        future restoration.

        Args:
            text: Input string to pseudonymize.
            detectors: Optional sequence of Detector instances to execute. If None,
                uses default built-in detectors. If `[]`, no detectors run.
            conflict_policy: Policy for resolving conflicting, overlapping, or
                duplicate detections ('reject', 'longest', or 'priority').
                Default is 'reject'.
            type_priority: Sequence of entity type names in descending priority
                order. Required when conflict_policy='priority', must be None
                otherwise.

        Returns:
            The pseudonymized string with detected spans replaced by placeholders.

        Raises:
            TypeError: If `text` is not a string, or if policy arguments have
                invalid types.
            ValueError: If `text` contains a placeholder already assigned by this
                session, or if conflict resolution encounters unresolvable conflicts.
        """
        if not isinstance(text, str):
            raise TypeError(f"text must be a str, got {type(text).__name__}")

        # Extract placeholder-shaped literal tokens from input
        literal_tokens = set(_PLACEHOLDER_PATTERN.findall(text))

        # Check for conflicts with existing mapped placeholders in this session
        assigned_keys = set(self._placeholder_to_value.keys())
        conflicts = sorted(literal_tokens & assigned_keys)
        if conflicts:
            raise ValueError(
                "Input contains a placeholder already assigned by this "
                f"session: {conflicts[0]}"
            )

        # Work on isolated copies to guarantee atomic updates
        temp_reserved_placeholders = self._reserved_placeholders.copy()
        temp_reserved_placeholders.update(literal_tokens)
        temp_identity_to_placeholder = self._identity_to_placeholder.copy()
        temp_placeholder_to_value = self._placeholder_to_value.copy()
        temp_counters_by_type = self._counters_by_type.copy()
        assigned_placeholders = assigned_keys.copy()

        detections = detect(text, detectors=detectors)
        detections = resolve_detection_conflicts(
            detections,
            policy=conflict_policy,
            type_priority=type_priority,
        )
        if not detections:
            # Commit reserved literals even when no PII is detected
            self._reserved_placeholders = temp_reserved_placeholders
            return text

        pieces: list[str] = []
        cursor = 0

        for d in detections:
            identity = (d.type, d.normalized_value)
            placeholder: str | None = temp_identity_to_placeholder.get(identity)
            if placeholder is None:
                counter = temp_counters_by_type.get(d.type, 0)
                while True:
                    counter += 1
                    candidate = f"[{d.type}_{counter}]"
                    if (
                        candidate not in text
                        and candidate not in assigned_placeholders
                        and candidate not in temp_reserved_placeholders
                    ):
                        placeholder = candidate
                        break
                temp_counters_by_type[d.type] = counter
                temp_identity_to_placeholder[identity] = placeholder
                # Record first observed raw representation for restoration:
                temp_placeholder_to_value[placeholder] = d.value
                assigned_placeholders.add(placeholder)

            assert placeholder is not None
            pieces.append(text[cursor : d.start])
            pieces.append(placeholder)
            cursor = d.end

        pieces.append(text[cursor:])
        result = "".join(pieces)

        # Commit state atomically
        self._reserved_placeholders = temp_reserved_placeholders
        self._identity_to_placeholder = temp_identity_to_placeholder
        self._placeholder_to_value = temp_placeholder_to_value
        self._counters_by_type = temp_counters_by_type
        return result

    def restore(self, text: str) -> str:
        """Restore mapped placeholders in text to their original raw values.

        Performs a single-pass regex replacement of exact known placeholders to
        prevent cascading restoration. Unrecognized placeholders remain untouched.

        Args:
            text: Input string (e.g. LLM response) containing placeholders.

        Returns:
            The restored string with known placeholders replaced.

        Raises:
            TypeError: If `text` is not a string.
        """
        if not isinstance(text, str):
            raise TypeError(f"text must be a str, got {type(text).__name__}")

        if not self._placeholder_to_value or not text:
            return text

        # Sort descending by length for defensive matching
        patterns = sorted(self._placeholder_to_value.keys(), key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(p) for p in patterns))
        return pattern.sub(lambda m: self._placeholder_to_value[m.group(0)], text)
