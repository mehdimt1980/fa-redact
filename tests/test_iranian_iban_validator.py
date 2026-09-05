"""Unit tests for Iranian IBAN (Sheba) validator (is_valid_iranian_iban).

Tests verify strict electronic format rules, position-preserving digit normalization,
and streaming MOD-97 checksum validation using synthetic algorithmic test vectors.
"""

from __future__ import annotations

import pytest

from fa_redact.validators.iranian_iban import is_valid_iranian_iban

# Synthetic checksum-valid Iranian IBAN test vector
_VALID_SYNTHETIC_IBAN_ASCII = "IR641234567890123456789012"
_VALID_SYNTHETIC_IBAN_PERSIAN = "IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲"
_VALID_SYNTHETIC_IBAN_ARABIC_INDIC = "IR٦٤١٢٣٤٥٦٧٨٩٠١٢٣٤٥٦٧٨٩٠١٢"
_VALID_SYNTHETIC_IBAN_MIXED = "IR۶4۱۲34۵6۷8۹0۱۲34۵6۷8۹012"


class TestIranianIBANValidatorValid:
    """Tests for valid synthetic Iranian IBAN vectors across supported digit scripts."""

    def test_valid_synthetic_ascii_iban(self) -> None:
        """Verify algorithmic synthetic ASCII vector passes checksum and structure."""
        assert is_valid_iranian_iban(_VALID_SYNTHETIC_IBAN_ASCII) is True

    def test_valid_synthetic_persian_digits_iban(self) -> None:
        """Verify equivalent Persian-digit representation passes validation."""
        assert is_valid_iranian_iban(_VALID_SYNTHETIC_IBAN_PERSIAN) is True

    def test_valid_synthetic_arabic_indic_digits_iban(self) -> None:
        """Verify equivalent Arabic-Indic digit representation passes validation."""
        assert is_valid_iranian_iban(_VALID_SYNTHETIC_IBAN_ARABIC_INDIC) is True

    def test_valid_synthetic_mixed_digits_iban(self) -> None:
        """Verify mixed Persian, Arabic-Indic, and ASCII digits pass validation."""
        assert is_valid_iranian_iban(_VALID_SYNTHETIC_IBAN_MIXED) is True

    def test_additional_synthetic_valid_vector(self) -> None:
        """Verify a second programmatically generated checksum-valid vector.

        BBAN: 21 zeros + 1 (22 digits total)
        Numeric repr: 0000000000000000000001182700 -> mod 97 = 76
        Check digits = 98 - 76 = 22
        IBAN: IR220000000000000000000001 (total length 26)
        """
        second_valid = "IR220000000000000000000001"
        assert is_valid_iranian_iban(second_valid) is True


class TestIranianIBANValidatorChecksumMutations:
    """Tests proving that checksum mutations fail validation."""

    @pytest.mark.parametrize(
        "mutation",
        [
            "IR641234567890123456789013",  # Last digit mutated from 2 to 3
            "IR641234567890123456789011",  # Last digit mutated from 2 to 1
            "IR641234567890123456789002",  # Second to last digit mutated
            "IR651234567890123456789012",  # Check digit mutated from 64 to 65
            "IR631234567890123456789012",  # Check digit mutated from 64 to 63
            "IR001234567890123456789012",  # Check digits mutated to 00
            "IR991234567890123456789012",  # Check digits mutated to 99
            "IR640000000000000000000000",  # Zeroed BBAN with original check digits
            "IR649999999999999999999999",  # Nined BBAN with original check digits
        ],
    )
    def test_checksum_mutations_rejected(self, mutation: str) -> None:
        """Verify that single and multi-digit mutations fail MOD-97 checksum."""
        assert is_valid_iranian_iban(mutation) is False

    def test_systematic_single_digit_mutations(self) -> None:
        """Systematically mutate each of the 24 numeric digits and verify failure."""
        prefix = "IR"
        digits = "641234567890123456789012"
        assert len(digits) == 24

        for i, char in enumerate(digits):
            original_digit = int(char)
            # Replace digit with (original + 1) % 10
            mutated_digit = (original_digit + 1) % 10
            mutated_digits = digits[:i] + str(mutated_digit) + digits[i + 1 :]
            mutated_iban = prefix + mutated_digits
            assert is_valid_iranian_iban(mutated_iban) is False, (
                f"Mutation at index {i} ({mutated_iban}) unexpectedly passed"
            )


class TestIranianIBANValidatorCountryCode:
    """Tests verifying strict Iranian 'IR' uppercase country code requirement."""

    @pytest.mark.parametrize(
        "invalid_country_code",
        [
            "DE641234567890123456789012",  # Germany
            "GB641234567890123456789012",  # Great Britain
            "FR641234567890123456789012",  # France
            "XX641234567890123456789012",  # Invalid country
            "US641234567890123456789012",  # United States
        ],
    )
    def test_foreign_country_codes_rejected(self, invalid_country_code: str) -> None:
        """Foreign country codes are rejected even if structurally formatted."""
        assert is_valid_iranian_iban(invalid_country_code) is False

    @pytest.mark.parametrize(
        "case_variation",
        [
            "ir641234567890123456789012",  # Lowercase ir
            "Ir641234567890123456789012",  # Titlecase Ir
            "iR641234567890123456789012",  # Inverted case iR
            "ir۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲",  # Lowercase ir with Persian digits
        ],
    )
    def test_lowercase_or_mixed_case_country_codes_rejected(
        self, case_variation: str
    ) -> None:
        """Only exact uppercase ASCII 'IR' is accepted; no case-folding."""
        assert is_valid_iranian_iban(case_variation) is False


class TestIranianIBANValidatorFormattingAndLength:
    """Tests verifying strict electronic formatting, length, and non-digit rejection."""

    @pytest.mark.parametrize(
        "invalid_length",
        [
            "",  # Empty
            "IR",  # 2 chars
            "IR64",  # 4 chars
            "IR64123456789012345678901",  # 25 chars (1 too short)
            "IR6412345678901234567890123",  # 27 chars (1 too long)
            "IR641234567890123456789012345678",  # 32 chars
        ],
    )
    def test_invalid_length_rejected(self, invalid_length: str) -> None:
        """Strings differing from exactly 26 characters are rejected."""
        assert is_valid_iranian_iban(invalid_length) is False

    @pytest.mark.parametrize(
        "formatted_iban",
        [
            " IR641234567890123456789012",  # Leading space
            "IR641234567890123456789012 ",  # Trailing space
            "IR64 1234 5678 9012 3456 7890 12",  # Print format spaces
            "IR64-1234-5678-9012-3456-7890-12",  # Hyphenated
            "IR64\t1234567890123456789012",  # Tab character
            "IR64\n1234567890123456789012",  # Newline character
            "IR64\u200c1234567890123456789012",  # Zero-width non-joiner (ZWNJ)
        ],
    )
    def test_non_compact_formatting_rejected(self, formatted_iban: str) -> None:
        """Validator does not strip whitespace, hyphens, or separators."""
        assert is_valid_iranian_iban(formatted_iban) is False

    @pytest.mark.parametrize(
        "non_digit_value",
        [
            "IR64123456789012345678901A",  # Letter A
            "IR64123456789012345678901z",  # Letter z
            "IR64123456789012345678901_",  # Underscore
            "IR64123456789012345678901.",  # Period
            "IR64123456789012345678901#",  # Hash
            "IR६४1234567890123456789012",  # Devanagari numerals
            "IR①②1234567890123456789012",  # Circled numbers
            "IRIV1234567890123456789012",  # Roman numerals
        ],
    )
    def test_non_digits_and_unsupported_numerals_rejected(
        self, non_digit_value: str
    ) -> None:
        """Only ASCII, Persian, and Arabic-Indic digit scripts are accepted."""
        assert is_valid_iranian_iban(non_digit_value) is False


class TestIranianIBANValidatorTypes:
    """Tests verifying non-string types return False without raising exceptions."""

    @pytest.mark.parametrize(
        "non_string",
        [
            None,
            123,
            641234567890123456789012,
            [],
            {},
            b"IR641234567890123456789012",
            object(),
            True,
            False,
        ],
    )
    def test_non_string_inputs_return_false(self, non_string: object) -> None:
        """Non-string inputs safely return False."""
        assert is_valid_iranian_iban(non_string) is False  # type: ignore[arg-type]
