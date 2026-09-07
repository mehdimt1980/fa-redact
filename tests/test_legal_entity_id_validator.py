"""Tests for Iranian Legal Entity National ID validator."""

from __future__ import annotations

import re
from pathlib import Path

from research.legal_entity_id_reference import (
    compute_legal_entity_checksum_variant_a,
    verify_legal_entity_id_variant_a,
)

from fa_redact.normalization import normalize_digits
from fa_redact.validators.legal_entity_id import (
    _COEFFICIENTS_VARIANT_A,
    is_valid_iranian_legal_entity_id,
)


def _make_synthetic_legal_id(prefix_10: str) -> str:
    """Deterministic test-only fixture generator from 10-digit prefix."""
    check = compute_legal_entity_checksum_variant_a(prefix_10)
    return f"{prefix_10}{check}"


_SYNTH_PREFIX_1 = "1400000001"
_SYNTH_PREFIX_LEADING_ZERO = "0123456789"


class TestLegalEntityIDValidator:
    """Comprehensive test suite for is_valid_iranian_legal_entity_id."""

    def test_known_synthetic_valid_ascii_candidate(self) -> None:
        """1. Validate a known synthetic valid ASCII candidate."""
        cand = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        assert is_valid_iranian_legal_entity_id(cand) is True

    def test_multiple_synthetic_valid_ascii_candidates(self) -> None:
        """2. Validate multiple synthetic valid ASCII candidates."""
        # Generate 20 distinct synthetic valid IDs from structured prefixes
        for i in range(10, 30):
            prefix = f"{i * 3719284:010d}"
            if len(set(prefix)) == 1:
                continue
            valid_id = _make_synthetic_legal_id(prefix)
            assert is_valid_iranian_legal_entity_id(valid_id) is True

    def test_persian_digit_representation(self) -> None:
        """3. Validate Persian digits (۰-۹) normalized correctly."""
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        persian_valid = "".join(chr(0x06F0 + int(c)) for c in base_id)
        assert is_valid_iranian_legal_entity_id(persian_valid) is True

    def test_arabic_indic_digit_representation(self) -> None:
        """4. Validate Arabic-Indic digits (٠-٩) normalized correctly."""
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        arabic_valid = "".join(chr(0x0660 + int(c)) for c in base_id)
        assert is_valid_iranian_legal_entity_id(arabic_valid) is True

    def test_mixed_digit_scripts(self) -> None:
        """5. Validate mixed digit representations."""
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        mixed_valid = (
            base_id[:4]
            + "".join(chr(0x06F0 + int(c)) for c in base_id[4:7])
            + "".join(chr(0x0660 + int(c)) for c in base_id[7:])
        )
        assert is_valid_iranian_legal_entity_id(mixed_valid) is True

    def test_leading_zero_preserved(self) -> None:
        """6. Validate that leading zeros are preserved semantically."""
        leading_zero_id = _make_synthetic_legal_id(_SYNTH_PREFIX_LEADING_ZERO)
        assert is_valid_iranian_legal_entity_id(leading_zero_id) is True
        persian_leading_zero = "".join(chr(0x06F0 + int(c)) for c in leading_zero_id)
        assert is_valid_iranian_legal_entity_id(persian_leading_zero) is True

    def test_invalid_checksum(self) -> None:
        """7. Validate that incorrect checksum is rejected."""
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        correct_check = int(base_id[-1])
        wrong_check = (correct_check + 1) % 10
        invalid_candidate = f"{base_id[:-1]}{wrong_check}"
        assert is_valid_iranian_legal_entity_id(invalid_candidate) is False

    def test_wrong_checksum_altered_last_digit(self) -> None:
        """8. Validate every wrong last digit is rejected."""
        prefix = _SYNTH_PREFIX_1
        correct_check = compute_legal_entity_checksum_variant_a(prefix)
        for d in range(10):
            candidate = f"{prefix}{d}"
            if d == correct_check:
                assert is_valid_iranian_legal_entity_id(candidate) is True
            else:
                assert is_valid_iranian_legal_entity_id(candidate) is False

    def test_length_10_rejected(self) -> None:
        """9. Reject length 10 strings."""
        assert is_valid_iranian_legal_entity_id(_SYNTH_PREFIX_1) is False

    def test_length_12_rejected(self) -> None:
        """10. Reject length 12 strings."""
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        assert is_valid_iranian_legal_entity_id(f"{base_id}0") is False

    def test_empty_string_rejected(self) -> None:
        """11. Reject empty string."""
        assert is_valid_iranian_legal_entity_id("") is False

    def test_whitespace_prefix_rejected(self) -> None:
        """12. Reject leading whitespace."""
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        assert is_valid_iranian_legal_entity_id(f" {base_id}") is False

    def test_whitespace_suffix_rejected(self) -> None:
        """13. Reject trailing whitespace."""
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        assert is_valid_iranian_legal_entity_id(f"{base_id} ") is False

    def test_internal_whitespace_rejected(self) -> None:
        """14. Reject internal whitespace."""
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        spaced = f"{base_id[:4]} {base_id[4:]}"
        assert is_valid_iranian_legal_entity_id(spaced) is False

    def test_hyphen_rejected(self) -> None:
        """15. Reject hyphenated numbers."""
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        hyphenated = f"{base_id[:4]}-{base_id[4:]}"
        assert is_valid_iranian_legal_entity_id(hyphenated) is False

    def test_slash_rejected(self) -> None:
        """16. Reject slashes."""
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        slashed = f"{base_id[:4]}/{base_id[4:]}"
        assert is_valid_iranian_legal_entity_id(slashed) is False

    def test_letters_rejected(self) -> None:
        """17. Reject letters in candidate."""
        prefix = _SYNTH_PREFIX_1
        assert is_valid_iranian_legal_entity_id(f"{prefix}A") is False
        assert is_valid_iranian_legal_entity_id(f"{prefix}س") is False

    def test_unicode_decimal_digits_outside_persian_arabic_rejected(self) -> None:
        """18. Reject Devanagari or other non-Persian/Arabic Unicode decimal digits."""
        devanagari_cand = (
            "\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f3"
        )
        assert is_valid_iranian_legal_entity_id(devanagari_cand) is False

    def test_all_zeros_rejected(self) -> None:
        """19. Reject all-zeros string."""
        assert is_valid_iranian_legal_entity_id("00000000000") is False

    def test_all_ones_rejected(self) -> None:
        """20. Reject all-ones string."""
        assert is_valid_iranian_legal_entity_id("11111111111") is False

    def test_every_all_identical_digit_pattern_rejected(self) -> None:
        """21. Reject all identical 11-digit sequences 000..000 through 999..999."""
        for d in range(10):
            repeated = str(d) * 11
            assert is_valid_iranian_legal_entity_id(repeated) is False
            persian_rep = chr(0x06F0 + d) * 11
            assert is_valid_iranian_legal_entity_id(persian_rep) is False

    def test_non_string_types_rejected(self) -> None:
        """22-25. Non-string inputs must return False without raising."""
        base_id = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        assert is_valid_iranian_legal_entity_id(int(base_id)) is False  # type: ignore[arg-type]
        assert is_valid_iranian_legal_entity_id(base_id.encode("utf-8")) is False  # type: ignore[arg-type]
        assert is_valid_iranian_legal_entity_id(None) is False  # type: ignore[arg-type]
        assert is_valid_iranian_legal_entity_id(True) is False  # type: ignore[arg-type]
        assert is_valid_iranian_legal_entity_id([base_id]) is False  # type: ignore[arg-type]

    def test_no_zero_padding_performed(self) -> None:
        """26. Short strings are never padded to 11 digits."""
        assert is_valid_iranian_legal_entity_id("387143") is False

    def test_exact_variant_a_coefficients(self) -> None:
        """27. Verify exact Variant A coefficient sequence in validator."""
        expected_coefficients = (29, 27, 23, 19, 17, 29, 27, 23, 19, 17)
        assert _COEFFICIENTS_VARIANT_A == expected_coefficients

    def test_exact_d9_plus_2_adjustment_behavior(self) -> None:
        """28. Verify that d[9] + 2 adjustment operates correctly."""
        prefix_d9_0 = "1234567890"
        check_d9_0 = compute_legal_entity_checksum_variant_a(prefix_d9_0)
        assert is_valid_iranian_legal_entity_id(f"{prefix_d9_0}{check_d9_0}") is True

        prefix_d9_9 = "1234567899"
        check_d9_9 = compute_legal_entity_checksum_variant_a(prefix_d9_9)
        assert is_valid_iranian_legal_entity_id(f"{prefix_d9_9}{check_d9_9}") is True

    def test_remainder_10_maps_to_check_digit_0(self) -> None:
        """29. Verify case where total % 11 == 10 maps check digit to 0."""
        found_rem_10 = False
        for i in range(1, 1000):
            prefix = f"{i * 1234567:010d}"
            if len(set(prefix)) == 1:
                continue
            d = [int(c) for c in prefix]
            add_val = d[9] + 2
            total = sum(
                (d[j] + add_val) * _COEFFICIENTS_VARIANT_A[j] for j in range(10)
            )
            if total % 11 == 10:
                found_rem_10 = True
                valid_id = f"{prefix}0"
                assert is_valid_iranian_legal_entity_id(valid_id) is True
                for wrong in range(1, 10):
                    assert is_valid_iranian_legal_entity_id(f"{prefix}{wrong}") is False
                break
        assert found_rem_10, "Should find at least one prefix with remainder 10"

    def test_deterministic_oracle_agreement_across_synthetic_sample(self) -> None:
        """30. Independent oracle verification comparing with research reference."""
        for n in range(100, 200):
            prefix = f"{n * 9876543:010d}"
            if len(set(prefix)) == 1:
                continue
            expected_check = compute_legal_entity_checksum_variant_a(prefix)
            valid_id = f"{prefix}{expected_check}"
            assert is_valid_iranian_legal_entity_id(valid_id) is True
            assert verify_legal_entity_id_variant_a(valid_id) is True

    def test_single_digit_mutation_invalidates_checksum(self) -> None:
        """31. Single digit mutation across positions invalidates candidate."""
        base_valid = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        for pos in range(11):
            original_digit = int(base_valid[pos])
            for new_digit in range(10):
                if new_digit == original_digit:
                    continue
                mutated = base_valid[:pos] + str(new_digit) + base_valid[pos + 1 :]
                if len(set(mutated)) == 1:
                    assert is_valid_iranian_legal_entity_id(mutated) is False
                else:
                    expected = verify_legal_entity_id_variant_a(mutated)
                    assert is_valid_iranian_legal_entity_id(mutated) == expected

    def test_no_exceptions_on_malformed_inputs(self) -> None:
        """32. Ensure validator never raises exceptions on arbitrary strings/objects."""
        base_valid = _make_synthetic_legal_id(_SYNTH_PREFIX_1)
        fuzz_inputs = [
            "",
            "   ",
            "\n\t\r",
            "123",
            "abcdefghijk",
            "۱۲۳",
            f"{base_valid}\x00",
            "\U0001f600" * 11,
            base_valid * 100,
            ".././..",
        ]
        for item in fuzz_inputs:
            assert is_valid_iranian_legal_entity_id(item) is False

    def test_no_committed_checksum_valid_legal_entity_id_literals_in_static_artifacts(
        self,
    ) -> None:
        """33. Ensure no standalone checksum-valid Legal Entity ID literals
        are committed in static artifacts.
        """
        repo_root = Path(__file__).resolve().parent.parent
        files_to_scan = [
            repo_root / "README.md",
            repo_root / ".github" / "workflows" / "ci.yml",
            repo_root / ".github" / "workflows" / "release.yml",
            repo_root / "CHANGELOG.md",
            repo_root / "PROJECT_STATUS.md",
            repo_root / "ROADMAP.md",
            repo_root / "src" / "fa_redact" / "validators" / "legal_entity_id.py",
            repo_root / "src" / "fa_redact" / "detectors" / "legal_entity_id.py",
            repo_root / "tests" / "test_legal_entity_id_validator.py",
            repo_root / "tests" / "test_legal_entity_id_detector.py",
            repo_root / "research" / "phase27_additional_iranian_identifiers.md",
            repo_root / "research" / "results" / "phase27_identifier_decision.json",
            repo_root / "research" / "legal_entity_id_reference.py",
        ]

        pattern = re.compile(
            r"(?<![0-9\u0660-\u0669\u06f0-\u06f9])([0-9\u0660-\u0669\u06f0-\u06f9]{11})(?![0-9\u0660-\u0669\u06f0-\u06f9])"
        )

        violations: list[str] = []
        for file_path in files_to_scan:
            assert file_path.is_file(), f"Target file must exist: {file_path}"
            content = file_path.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                candidate_str = match.group(1)
                normalized = normalize_digits(candidate_str)
                if len(normalized) == 11 and is_valid_iranian_legal_entity_id(
                    normalized
                ):
                    violations.append(
                        f"{file_path.name}: found checksum-valid literal "
                        f"'{candidate_str}' (normalized: '{normalized}')"
                    )

        assert violations == [], (
            "Committed checksum-valid Legal Entity ID literals detected in "
            f"static artifacts: {violations}"
        )
