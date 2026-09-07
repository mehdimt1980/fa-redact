"""Clinical redaction profiles for Persian healthcare text workflows.

This module provides a lightweight, high-level composition layer for Persian
clinical text processing. It composes existing fa-redact detectors, institutional
pattern rules, and conflict resolution policies into immutable configuration
profiles without duplicating detection or transformation algorithms.

IMPORTANT DISCLAIMER:
    ClinicalRedactionProfile is a convenience composition layer over supported
    detectors. It does NOT guarantee complete clinical de-identification, HIPAA
    Safe Harbor compliance, GDPR compliance, Iranian healthcare data protection
    compliance, or absence of residual identifiers. Institutional and human
    review remains mandatory for clinical workflows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from fa_redact.conflicts import ConflictPolicy
from fa_redact.detectors.bank_card import BankCardDetector
from fa_redact.detectors.email import EmailDetector
from fa_redact.detectors.iranian_iban import IranianIBANDetector
from fa_redact.detectors.mobile import IranianMobileNumberDetector
from fa_redact.detectors.national_id import IranianNationalIDDetector
from fa_redact.detectors.pattern import PatternDetector, PatternRule
from fa_redact.models import Detection
from fa_redact.pipeline import detect
from fa_redact.protocols import Detector
from fa_redact.redaction import redact
from fa_redact.reporting import DetectionReport, detection_report
from fa_redact.structured import (
    detect_fields,
    redact_fields,
    report_fields,
)

ClinicalTextTemplate = Literal[
    "outpatient_note",
    "discharge_summary",
    "referral_letter",
]

_SUPPORTED_TEMPLATES: frozenset[str] = frozenset(
    {"outpatient_note", "discharge_summary", "referral_letter"}
)
_SUPPORTED_CONFLICT_POLICIES: frozenset[str] = frozenset(
    {"reject", "longest", "priority"}
)


@dataclass(frozen=True, slots=True)
class ClinicalRedactionProfile:
    """Immutable clinical redaction profile configuration.

    This profile encapsulates detector composition and conflict resolution
    settings for clinical text workflows. It does NOT retain processed source text,
    detected PII, redacted strings, patient data, report history, or session state.

    Attributes:
        template: Clinical text workflow label.
        detectors: Immutable tuple of configured Detector instances.
        conflict_policy: Conflict resolution policy for overlapping detections.
        type_priority: Immutable tuple of entity type priority hierarchy if configured.
        institutional_rules: Immutable tuple of institution-specific PatternRules.
        include_email: Whether ASCII email detector is active.
        include_bank_card: Whether payment card detector is active.
        person_detector: Optional person detector instance if supplied.
    """

    template: ClinicalTextTemplate
    detectors: tuple[Detector, ...]
    conflict_policy: ConflictPolicy = "reject"
    type_priority: tuple[str, ...] | None = None
    institutional_rules: tuple[PatternRule, ...] = ()
    include_email: bool = True
    include_bank_card: bool = False
    person_detector: Detector | None = None

    def detect(self, text: str) -> list[Detection]:
        """Detect identifiers in text using profile-configured detectors.

        Args:
            text: Input string to scan.

        Returns:
            List of Detection instances sorted by (start, end, type).
        """
        return detect(text, detectors=self.detectors)

    def redact(self, text: str) -> str:
        """Redact detected identifiers using typed placeholders.

        Args:
            text: Input string to redact.

        Returns:
            Redacted text with detected spans replaced by placeholders.
        """
        return redact(
            text,
            detectors=self.detectors,
            conflict_policy=self.conflict_policy,
            type_priority=self.type_priority,
        )

    def report(self, text: str) -> DetectionReport:
        """Generate privacy-safe, value-free detection report.

        Args:
            text: Input string to summarize.

        Returns:
            DetectionReport aggregate summary.
        """
        return detection_report(text, detectors=self.detectors)

    def detect_fields(
        self,
        record: Mapping[str, Any],
        fields: Sequence[str],
    ) -> dict[str, list[Detection]]:
        """Detect identifiers in explicitly selected fields of a mapping.

        Args:
            record: Root mapping structure.
            fields: Sequence of dot-separated field paths.

        Returns:
            Dictionary mapping each path to its Detection list.
        """
        return detect_fields(record, fields, detectors=self.detectors)

    def redact_fields(
        self,
        record: Mapping[str, Any],
        fields: Sequence[str],
    ) -> dict[str, Any]:
        """Redact explicitly selected fields with record-wide referential consistency.

        Args:
            record: Root mapping structure.
            fields: Sequence of dot-separated field paths.

        Returns:
            Transformed dictionary copy with redacted fields.
        """
        return redact_fields(
            record,
            fields,
            detectors=self.detectors,
            conflict_policy=self.conflict_policy,
            type_priority=self.type_priority,
        )

    def report_fields(
        self,
        record: Mapping[str, Any],
        fields: Sequence[str],
    ) -> dict[str, DetectionReport]:
        """Generate value-free DetectionReports for explicitly selected fields.

        Args:
            record: Root mapping structure.
            fields: Sequence of dot-separated field paths.

        Returns:
            Dictionary mapping each path to its DetectionReport.
        """
        return report_fields(record, fields, detectors=self.detectors)


def clinical_profile(
    template: ClinicalTextTemplate,
    *,
    institutional_rules: Sequence[PatternRule] = (),
    person_detector: Detector | None = None,
    include_email: bool = True,
    include_bank_card: bool = False,
    conflict_policy: ConflictPolicy = "reject",
    type_priority: Sequence[str] | None = None,
) -> ClinicalRedactionProfile:
    """Build an immutable ClinicalRedactionProfile for Persian clinical text workflows.

    Composes built-in direct identifier detectors (National ID, Mobile, IBAN),
    optional email and bank card detectors, optional institution-specific PatternRules,
    and an optional PERSON detector into a deterministic profile.

    Args:
        template: Clinical text workflow label ('outpatient_note', 'discharge_summary',
            or 'referral_letter').
        institutional_rules: Optional sequence of institution-specific PatternRule
            objects (e.g. for MRN, Patient ID, Encounter ID). If non-empty, creates
            a PatternDetector.
        person_detector: Optional Detector instance for personal name extraction
            (e.g., PersianNERDetector).
        include_email: Whether to include EmailDetector (default True).
        include_bank_card: Whether to include BankCardDetector (default False).
        conflict_policy: Conflict policy for redaction ('reject', 'longest',
            'priority'). Default is 'reject'.
        type_priority: Sequence of entity type names for 'priority' conflict policy.
            Must be None when conflict_policy is not 'priority'.

    Returns:
        Immutable ClinicalRedactionProfile instance.

    Raises:
        TypeError: If arguments are of incorrect types.
        ValueError: If template or conflict_policy is invalid, or if type_priority
            configuration is mismatched.
    """
    if not isinstance(template, str):
        raise TypeError(f"template must be a str, got {type(template).__name__}")
    if template not in _SUPPORTED_TEMPLATES:
        raise ValueError(
            f"Invalid template {template!r}: supported templates are "
            f"{sorted(_SUPPORTED_TEMPLATES)}"
        )

    if not isinstance(include_email, bool):
        raise TypeError(
            f"include_email must be a bool, got {type(include_email).__name__}"
        )
    if not isinstance(include_bank_card, bool):
        raise TypeError(
            f"include_bank_card must be a bool, got {type(include_bank_card).__name__}"
        )

    if isinstance(institutional_rules, (str, bytes, bytearray)) or not isinstance(
        institutional_rules, Sequence
    ):
        raise TypeError(
            f"institutional_rules must be a Sequence of PatternRule instances, "
            f"got {type(institutional_rules).__name__}"
        )
    for idx, rule in enumerate(institutional_rules):
        if not isinstance(rule, PatternRule):
            raise TypeError(
                f"institutional_rules item at index {idx} must be a PatternRule, "
                f"got {type(rule).__name__}"
            )
    rules_tuple = tuple(institutional_rules)

    if person_detector is not None:
        if not hasattr(person_detector, "detect") or not callable(
            person_detector.detect
        ):
            raise TypeError(
                f"person_detector must be a Detector instance with a callable "
                f"detect method, got {type(person_detector).__name__}"
            )

    if not isinstance(conflict_policy, str):
        raise TypeError(
            f"conflict_policy must be a str, got {type(conflict_policy).__name__}"
        )
    if conflict_policy not in _SUPPORTED_CONFLICT_POLICIES:
        raise ValueError(
            f"Invalid conflict_policy {conflict_policy!r}: must be 'reject', "
            f"'longest', or 'priority'"
        )

    type_priority_tuple: tuple[str, ...] | None
    if conflict_policy == "priority":
        if type_priority is None:
            raise ValueError(
                "type_priority is required when conflict_policy is 'priority'"
            )
        if isinstance(type_priority, (str, bytes, bytearray)) or not isinstance(
            type_priority, Sequence
        ):
            raise TypeError(
                "type_priority must be a Sequence of str, got "
                f"{type(type_priority).__name__}"
            )
        if not type_priority:
            raise ValueError(
                "type_priority sequence cannot be empty when conflict_policy "
                "is 'priority'"
            )
        for idx, item in enumerate(type_priority):
            if not isinstance(item, str):
                raise TypeError(
                    f"type_priority item at index {idx} must be a str, "
                    f"got {type(item).__name__}"
                )
        type_priority_tuple = tuple(type_priority)
    else:
        if type_priority is not None:
            raise ValueError(
                "type_priority must be None when conflict_policy is "
                f"{conflict_policy!r}"
            )
        type_priority_tuple = None

    # Deterministic detector sequence construction:
    # 1. IranianNationalIDDetector
    # 2. IranianMobileNumberDetector
    # 3. IranianIBANDetector
    # 4. EmailDetector if enabled
    # 5. BankCardDetector if enabled
    # 6. PatternDetector if institutional rules supplied
    # 7. person_detector if supplied
    detectors: list[Detector] = [
        IranianNationalIDDetector(),
        IranianMobileNumberDetector(),
        IranianIBANDetector(),
    ]

    if include_email:
        detectors.append(EmailDetector())

    if include_bank_card:
        detectors.append(BankCardDetector())

    if rules_tuple:
        detectors.append(PatternDetector(rules_tuple))

    if person_detector is not None:
        detectors.append(person_detector)

    return ClinicalRedactionProfile(
        template=template,
        detectors=tuple(detectors),
        conflict_policy=conflict_policy,
        type_priority=type_priority_tuple,
        institutional_rules=rules_tuple,
        include_email=include_email,
        include_bank_card=include_bank_card,
        person_detector=person_detector,
    )
