"""Tests for configurable pattern-based identifier detector (Phase 15)."""

import re
from dataclasses import FrozenInstanceError

import pytest

from fa_redact import (
    Detector,
    IranianIBANDetector,
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
    PatternDetector,
    PatternRule,
    PseudonymizationSession,
    detect,
    redact,
)


class TestPatternRuleValidation:
    """Unit tests for PatternRule dataclass validation and immutability."""

    @pytest.mark.parametrize(
        "valid_type",
        [
            "MRN",
            "PATIENT_ID",
            "ADMISSION_ID",
            "ENCOUNTER_ID",
            "CASE_2",
            "HOSPITAL_MRN",
            "A",
            "A_1",
            "X" * 64,
        ],
    )
    def test_valid_entity_types(self, valid_type: str) -> None:
        """Verify compliant placeholder-safe entity types are accepted."""
        rule = PatternRule(type=valid_type, pattern=r"[0-9]+")
        assert rule.type == valid_type
        assert rule.pattern == r"[0-9]+"
        assert rule.source == "normalized"
        assert rule.group == 0
        assert rule.flags == 0

    @pytest.mark.parametrize(
        "invalid_type",
        [
            "",
            " ",
            "mrn",
            "PATIENT-ID",
            "PATIENT ID",
            "[MRN]",
            "_MRN",
            "1PATIENT",
            "MRN$",
            "MRN#",
            "X" * 65,
        ],
    )
    def test_invalid_entity_types(self, invalid_type: str) -> None:
        """Verify non-compliant entity types raise ValueError."""
        with pytest.raises(ValueError, match=r"Invalid entity type"):
            PatternRule(type=invalid_type, pattern=r"[0-9]+")

    def test_invalid_pattern_empty(self) -> None:
        """Verify empty pattern string raises ValueError."""
        with pytest.raises(ValueError, match=r"pattern must be a non-empty string"):
            PatternRule(type="MRN", pattern="")

    def test_invalid_pattern_type(self) -> None:
        """Verify non-string pattern raises ValueError."""
        with pytest.raises(ValueError, match=r"pattern must be a non-empty string"):
            PatternRule(type="MRN", pattern=None)  # type: ignore[arg-type]

    @pytest.mark.parametrize("valid_source", ["normalized", "original"])
    def test_valid_source_modes(self, valid_source: str) -> None:
        """Verify 'normalized' and 'original' sources are accepted."""
        rule = PatternRule(
            type="MRN",
            pattern=r"[0-9]+",
            source=valid_source,  # type: ignore[arg-type]
        )
        assert rule.source == valid_source

    @pytest.mark.parametrize("invalid_source", ["", "NORMALIZED", "raw", "other"])
    def test_invalid_source_modes(self, invalid_source: str) -> None:
        """Verify unaccepted source values raise ValueError."""
        with pytest.raises(
            ValueError, match=r"source must be 'normalized' or 'original'"
        ):
            PatternRule(type="MRN", pattern=r"[0-9]+", source=invalid_source)  # type: ignore[arg-type]

    def test_pattern_rule_immutability(self) -> None:
        """Verify PatternRule is a frozen dataclass and prevents mutation."""
        rule = PatternRule(type="MRN", pattern=r"MRN-[0-9]{6}")
        with pytest.raises((FrozenInstanceError, AttributeError)):
            rule.type = "OTHER"  # type: ignore[misc]
        with pytest.raises((FrozenInstanceError, AttributeError)):
            rule.pattern = r".*"  # type: ignore[misc]

    def test_invalid_regex_syntax_raises_value_error(self) -> None:
        """Verify invalid regex syntax raises ValueError with entity type."""
        with pytest.raises(
            ValueError,
            match=r"Invalid regular expression pattern.*for entity type 'MRN'",
        ):
            PatternRule(type="MRN", pattern=r"[0-9++")

    def test_invalid_integer_group_out_of_range(self) -> None:
        """Verify integer group exceeding pattern capture count raises ValueError."""
        with pytest.raises(
            ValueError,
            match=r"Configured group index 2 out of range for entity type 'MRN'",
        ):
            PatternRule(type="MRN", pattern=r"MRN-([0-9]{6})", group=2)

    def test_negative_integer_group_raises_value_error(self) -> None:
        """Verify negative integer group index raises ValueError."""
        with pytest.raises(ValueError, match=r"group index must be non-negative"):
            PatternRule(type="MRN", pattern=r"MRN-[0-9]{6}", group=-1)

    def test_invalid_named_group_nonexistent(self) -> None:
        """Verify named group missing from pattern raises ValueError."""
        with pytest.raises(
            ValueError,
            match=(
                r"Configured named group 'id' not found in pattern for "
                r"entity type 'MRN'"
            ),
        ):
            PatternRule(type="MRN", pattern=r"MRN-(?P<identifier>[0-9]{6})", group="id")

    def test_invalid_group_type_raises_value_error(self) -> None:
        """Verify group types other than int and str raise ValueError."""
        with pytest.raises(ValueError, match=r"group must be int or str"):
            PatternRule(type="MRN", pattern=r"MRN-[0-9]{6}", group=1.5)  # type: ignore[arg-type]

    def test_empty_named_group_raises_value_error(self) -> None:
        """Verify empty named group string raises ValueError."""
        with pytest.raises(ValueError, match=r"group name must be a non-empty string"):
            PatternRule(type="MRN", pattern=r"MRN-[0-9]{6}", group="")

    def test_invalid_flags_type_raises_value_error(self) -> None:
        """Verify non-integer flags raise ValueError."""
        with pytest.raises(ValueError, match=r"flags must be an int"):
            PatternRule(type="MRN", pattern=r"MRN-[0-9]{6}", flags="i")  # type: ignore[arg-type]

    def test_valid_flags_and_groups(self) -> None:
        """Verify valid flags and capture groups configure successfully."""
        rule_int = PatternRule(
            type="MRN",
            pattern=r"MRN\s*:\s*([0-9]{6})",
            group=1,
            flags=re.IGNORECASE,
        )
        assert rule_int.group == 1
        assert rule_int.flags == re.IGNORECASE

        rule_named = PatternRule(
            type="PATIENT_ID",
            pattern=r"Patient\s*ID\s*:\s*(?P<id>PAT-[0-9]{8})",
            group="id",
            flags=re.IGNORECASE,
        )
        assert rule_named.group == "id"


class TestPatternDetectorConstruction:
    """Unit tests for PatternDetector constructor and validation."""

    def test_empty_rules_raises_value_error(self) -> None:
        """Verify empty rules collection raises ValueError."""
        with pytest.raises(ValueError, match=r"rules must be a non-empty sequence"):
            PatternDetector([])

    def test_non_sequence_rules_raises_type_error(self) -> None:
        """Verify non-sequence argument raises TypeError."""
        with pytest.raises(TypeError, match=r"rules must be a sequence"):
            PatternDetector(None)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match=r"rules must be a sequence"):
            PatternDetector("MRN-[0-9]{6}")  # type: ignore[arg-type]

    def test_non_pattern_rule_element_raises_type_error(self) -> None:
        """Verify collection with non-PatternRule element raises TypeError."""
        invalid_rules: list[object] = [
            PatternRule(type="MRN", pattern=r"MRN-[0-9]{6}"),
            "invalid_rule",
        ]
        with pytest.raises(
            TypeError, match=r"Rule at index 1 is not a PatternRule instance"
        ):
            PatternDetector(invalid_rules)  # type: ignore[arg-type]

    def test_caller_list_mutation_isolation(self) -> None:
        """Verify mutating caller's rules list does not alter detector rules."""
        rule = PatternRule(type="MRN", pattern=r"MRN-[0-9]{6}")
        rules_list = [rule]
        detector = PatternDetector(rules_list)

        # Mutate caller list
        rules_list.clear()

        assert len(detector.rules) == 1
        assert detector.rules[0] == rule
        # Verify detector continues working
        detections = detector.detect("MRN-123456", "MRN-123456")
        assert len(detections) == 1
        assert detections[0].type == "MRN"


class TestPatternDetectorExecution:
    """Unit tests for detection execution, group matching, and edge cases."""

    def test_length_mismatch_raises_value_error(self) -> None:
        """Verify detector enforces equal length between source texts."""
        detector = PatternDetector([PatternRule(type="MRN", pattern=r"MRN-[0-9]{6}")])
        with pytest.raises(
            ValueError,
            match=r"original_text length .* must equal normalized_text length",
        ):
            detector.detect("MRN-123456", "MRN-123")

    def test_synthetic_healthcare_identifiers(self) -> None:
        """Verify detection of various synthetic healthcare identifier rules."""
        detector = PatternDetector(
            [
                PatternRule(type="MRN", pattern=r"(?<!\w)MRN-[0-9]{6}(?!\w)"),
                PatternRule(
                    type="PATIENT_ID", pattern=r"(?<!\w)PAT-[A-Z]{2}-[0-9]{8}(?!\w)"
                ),
                PatternRule(
                    type="ADMISSION_ID", pattern=r"(?<!\w)ADM-20[0-9]{2}-[0-9]{6}(?!\w)"
                ),
                PatternRule(type="ENCOUNTER_ID", pattern=r"(?<!\w)ENC-[0-9]{10}(?!\w)"),
            ]
        )
        text = (
            "پرونده MRN-123456، بیمار PAT-AB-12345678، "
            "پذیرش ADM-2026-000123 و ویزیت ENC-1234567890 ثبت شد."
        )
        detections = detector.detect(text, text)
        assert len(detections) == 4

        assert detections[0].type == "MRN"
        assert detections[0].value == "MRN-123456"
        assert detections[0].normalized_value == "MRN-123456"
        assert text[detections[0].start : detections[0].end] == "MRN-123456"

        assert detections[1].type == "PATIENT_ID"
        assert detections[1].value == "PAT-AB-12345678"

        assert detections[2].type == "ADMISSION_ID"
        assert detections[2].value == "ADM-2026-000123"

        assert detections[3].type == "ENCOUNTER_ID"
        assert detections[3].value == "ENC-1234567890"

    def test_normalized_persian_and_arabic_indic_digits(self) -> None:
        """Verify normalized matching detects Persian and Arabic digits."""
        detector = PatternDetector(
            [PatternRule(type="MRN", pattern=r"(?<!\w)MRN-[0-9]{6}(?!\w)")]
        )

        original = "پرونده: MRN-۱۲۳۴۵۶ و MRN-١٢٣٤٥٦ و MRN-123456"
        normalized = "پرونده: MRN-123456 و MRN-123456 و MRN-123456"

        detections = detector.detect(original, normalized)
        assert len(detections) == 3

        # Persian digits
        assert detections[0].type == "MRN"
        assert detections[0].value == "MRN-۱۲۳۴۵۶"
        assert detections[0].normalized_value == "MRN-123456"
        assert original[detections[0].start : detections[0].end] == "MRN-۱۲۳۴۵۶"

        # Arabic-Indic digits
        assert detections[1].type == "MRN"
        assert detections[1].value == "MRN-١٢٣٤٥٦"
        assert detections[1].normalized_value == "MRN-123456"
        assert original[detections[1].start : detections[1].end] == "MRN-١٢٣٤٥٦"

        # ASCII digits
        assert detections[2].type == "MRN"
        assert detections[2].value == "MRN-123456"
        assert detections[2].normalized_value == "MRN-123456"
        assert original[detections[2].start : detections[2].end] == "MRN-123456"

    def test_original_source_matching_mode(self) -> None:
        """Verify source='original' performs candidate matching against raw text."""
        # 1. Matching exact raw Persian string
        raw_rule = PatternRule(
            type="RAW_MRN",
            pattern=r"کد-۱۲۳۴۵۶",
            source="original",
        )
        detector_raw = PatternDetector([raw_rule])

        original = "شماره کد-۱۲۳۴۵۶ ثبت شد"
        normalized = "شماره کد-123456 ثبت شد"

        detections = detector_raw.detect(original, normalized)
        assert len(detections) == 1
        assert detections[0].type == "RAW_MRN"
        assert detections[0].value == "کد-۱۲۳۴۵۶"
        assert detections[0].normalized_value == "کد-123456"

        # 2. ASCII regex against source='original' does NOT match Persian digits
        ascii_rule_on_raw = PatternRule(
            type="ASCII_MRN",
            pattern=r"MRN-[0-9]{6}",
            source="original",
        )
        detector_ascii_raw = PatternDetector([ascii_rule_on_raw])

        persian_orig = "پرونده MRN-۱۲۳۴۵۶"
        persian_norm = "پرونده MRN-123456"

        # Should match nothing because raw text has Persian digits, not ASCII [0-9]
        assert detector_ascii_raw.detect(persian_orig, persian_norm) == []

    def test_selected_capture_group_integer(self) -> None:
        """Verify integer capture group span is isolated while leaving labels intact."""
        rule = PatternRule(
            type="MRN",
            pattern=r"MRN\s*:\s*([0-9]{6})",
            group=1,
            flags=re.IGNORECASE,
        )
        detector = PatternDetector([rule])
        text = "شماره MRN: 123456 پذیرش شد"

        detections = detector.detect(text, text)
        assert len(detections) == 1
        assert detections[0].type == "MRN"
        assert detections[0].value == "123456"
        assert detections[0].start == 11
        assert detections[0].end == 17
        assert text[detections[0].start : detections[0].end] == "123456"

    def test_selected_capture_group_named(self) -> None:
        """Verify named capture group span is correctly extracted."""
        rule = PatternRule(
            type="PATIENT_ID",
            pattern=r"Patient\s*ID\s*:\s*(?P<identifier>PAT-[0-9]{8})",
            group="identifier",
            flags=re.IGNORECASE,
        )
        detector = PatternDetector([rule])
        text = "Patient ID: PAT-12345678"

        detections = detector.detect(text, text)
        assert len(detections) == 1
        assert detections[0].type == "PATIENT_ID"
        assert detections[0].value == "PAT-12345678"
        assert text[detections[0].start : detections[0].end] == "PAT-12345678"

    def test_zero_length_match_raises_value_error(self) -> None:
        """Verify zero-length match raises ValueError identifying the rule type."""
        rule = PatternRule(
            type="EMPTY_MATCH",
            pattern=r"MRN(?P<empty>[0-9]*)",
            group="empty",
        )
        detector = PatternDetector([rule])
        # "MRN" with 0 digits will produce an empty group match at offset 3..3
        with pytest.raises(
            ValueError,
            match=r"Zero-length match detected for rule 'EMPTY_MATCH' at offset 3",
        ):
            detector.detect("MRN is here", "MRN is here")

    def test_nonparticipating_group_raises_value_error(self) -> None:
        """Verify non-participating capture group raises ValueError with rule type."""
        rule = PatternRule(
            type="OPTIONAL_GROUP",
            pattern=r"(A)|(?P<num>[0-9]+)",
            group="num",
        )
        detector = PatternDetector([rule])
        # Text "A" matches branch (A), leaving (?P<num>[0-9]+) nonparticipating
        with pytest.raises(
            ValueError,
            match=(
                r"Capture group 'num' did not participate in match for rule "
                r"'OPTIONAL_GROUP'"
            ),
        ):
            detector.detect("A", "A")

    def test_multi_rule_deterministic_sorting(self) -> None:
        """Verify output detections are sorted by (start, end, type) across rules."""
        rule_enc = PatternRule(type="ENCOUNTER_ID", pattern=r"ENC-[0-9]{4}")
        rule_mrn = PatternRule(type="MRN", pattern=r"MRN-[0-9]{4}")

        # Pass ENC rule first in detector
        detector = PatternDetector([rule_enc, rule_mrn])

        # But text has MRN at start and ENC at end
        text = "MRN-1000 then ENC-2000"
        detections = detector.detect(text, text)

        assert len(detections) == 2
        assert detections[0].type == "MRN"
        assert detections[0].start == 0
        assert detections[1].type == "ENCOUNTER_ID"
        assert detections[1].start == 14

    def test_overlapping_and_duplicate_spans_preserved(self) -> None:
        """Verify detect() preserves overlapping and duplicate spans without drop."""
        rule_full = PatternRule(type="FULL_MRN", pattern=r"MRN-[0-9]{6}")
        rule_num = PatternRule(type="NUM_PART", pattern=r"[0-9]{6}")
        rule_dup = PatternRule(type="DUP_MRN", pattern=r"MRN-[0-9]{6}")

        detector = PatternDetector([rule_full, rule_num, rule_dup])
        text = "MRN-123456"

        detections = detector.detect(text, text)
        assert len(detections) == 3

        types = [d.type for d in detections]
        assert "DUP_MRN" in types
        assert "FULL_MRN" in types
        assert "NUM_PART" in types


class TestPipelineAndRedactionIntegration:
    """Integration tests with detect(), redact(), and PseudonymizationSession."""

    def test_pipeline_defaults_exclude_pattern_detector(self) -> None:
        """Verify detect() default pipeline does NOT detect custom patterns."""
        text = "پرونده MRN-123456 ثبت شد"
        assert detect(text) == []

    def test_pipeline_explicit_detector_replaces_defaults(self) -> None:
        """Verify passing PatternDetector explicitly executes only PatternDetector."""
        detector = PatternDetector([PatternRule(type="MRN", pattern=r"MRN-[0-9]{6}")])
        text = "همراه: 09123456789، پرونده: MRN-123456"

        detections = detect(text, detectors=[detector])
        assert len(detections) == 1
        assert detections[0].type == "MRN"
        assert detections[0].value == "MRN-123456"

    def test_pipeline_combined_builtin_and_custom_detectors(self) -> None:
        """Verify combining built-in detectors with PatternDetector explicitly."""
        institutional_detector = PatternDetector(
            [PatternRule(type="MRN", pattern=r"MRN-[0-9]{6}")]
        )
        all_detectors: list[Detector] = [
            IranianNationalIDDetector(),
            IranianMobileNumberDetector(),
            IranianIBANDetector(),
            institutional_detector,
        ]

        text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱، همراه: ۰۹۱۲۳۴۵۶۷۸۹، پرونده: MRN-123456"
        detections = detect(text, detectors=all_detectors)

        assert len(detections) == 3
        assert detections[0].type == "IR_NATIONAL_ID"
        assert detections[1].type == "IR_MOBILE"
        assert detections[2].type == "MRN"

    def test_redaction_with_pattern_detector(self) -> None:
        """Verify redact() generates typed placeholders for custom entities."""
        detector = PatternDetector(
            [
                PatternRule(type="MRN", pattern=r"(?<!\w)MRN-[0-9]{6}(?!\w)"),
                PatternRule(type="ENCOUNTER_ID", pattern=r"(?<!\w)ENC-[0-9]{10}(?!\w)"),
            ]
        )
        text = "MRN-123456 / ENC-1234567890"
        redacted = redact(text, detectors=[detector])
        assert redacted == "[MRN_1] / [ENCOUNTER_ID_1]"

    def test_redaction_context_aware_label_preservation(self) -> None:
        """Verify capture-group redaction leaves labels intact."""
        detector = PatternDetector(
            [
                PatternRule(
                    type="MRN",
                    pattern=r"MRN\s*:\s*(?P<id>[0-9]{6})",
                    group="id",
                    flags=re.IGNORECASE,
                )
            ]
        )
        text = "شماره MRN: 123456 ثبت شد"
        redacted = redact(text, detectors=[detector])
        assert redacted == "شماره MRN: [MRN_1] ثبت شد"

    def test_redaction_fail_loud_on_overlapping_pattern_rules(self) -> None:
        """Verify overlapping pattern rules cause redact() to fail loud."""
        detector = PatternDetector(
            [
                PatternRule(type="FULL_ID", pattern=r"MRN-[0-9]{6}"),
                PatternRule(type="NUM_ID", pattern=r"[0-9]{6}"),
            ]
        )
        with pytest.raises(ValueError, match=r"[Oo]verlap"):
            redact("MRN-123456", detectors=[detector])

    def test_pseudonymization_session_cross_script_identity(self) -> None:
        """Verify cross-script Persian and ASCII digits share pseudonym in session."""
        detector = PatternDetector(
            [PatternRule(type="MRN", pattern=r"(?<!\w)MRN-[0-9]{6}(?!\w)")]
        )
        session = PseudonymizationSession()

        # Turn 1: Persian digits
        turn1 = session.pseudonymize("پرونده: MRN-۱۲۳۴۵۶", detectors=[detector])
        assert turn1 == "پرونده: [MRN_1]"

        # Turn 2: ASCII digits
        turn2 = session.pseudonymize("پیگیری MRN-123456", detectors=[detector])
        assert turn2 == "پیگیری [MRN_1]"

        # Restoration restores first-observed raw value (Persian digits)
        restored = session.restore("پاسخ به [MRN_1]")
        assert restored == "پاسخ به MRN-۱۲۳۴۵۶"

    def test_pseudonymization_session_independent_counters(self) -> None:
        """Verify per-type sequential counters for custom entity types."""
        detector = PatternDetector(
            [
                PatternRule(type="MRN", pattern=r"(?<!\w)MRN-[0-9]{6}(?!\w)"),
                PatternRule(type="ENCOUNTER_ID", pattern=r"(?<!\w)ENC-[0-9]{10}(?!\w)"),
            ]
        )
        session = PseudonymizationSession()

        text = "MRN-123456 و MRN-654321 و ENC-1234567890"
        pseudonymized = session.pseudonymize(text, detectors=[detector])
        assert pseudonymized == "[MRN_1] و [MRN_2] و [ENCOUNTER_ID_1]"

    def test_pseudonymization_session_fail_loud_on_overlap(self) -> None:
        """Verify session pseudonymize() raises ValueError on overlap."""
        detector = PatternDetector(
            [
                PatternRule(type="FULL_ID", pattern=r"MRN-[0-9]{6}"),
                PatternRule(type="NUM_ID", pattern=r"[0-9]{6}"),
            ]
        )
        session = PseudonymizationSession()
        with pytest.raises(ValueError, match=r"[Oo]verlap"):
            session.pseudonymize("MRN-123456", detectors=[detector])
