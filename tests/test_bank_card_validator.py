"""Unit tests for 16-digit payment card (PAN) validator.

Tests verify strict 16-digit electronic format rules, position-preserving digit
normalization, standard Luhn checksum validation, and defensive filtering.
"""

from __future__ import annotations

import pytest

from fa_redact.validators.bank_card import is_valid_bank_card_number

# Synthetic checksum-valid 16-digit card test vectors
_VALID_SYNTHETIC_ASCII = "1234567890123452"
_VALID_SYNTHETIC_PERSIAN = "۱۲۳۴۵۶٧٨٩٠۱۲۳۴۵۲"
_VALID_SYNTHETIC_ARABIC_INDIC = "١٢٣٤٥٦٧٨٩٠١٢٣٤٥٢"
_VALID_SYNTHETIC_MIXED = "۱۲34۵۶78۹۰12۳۴52"


def _generate_luhn_check_digit(prefix_15: str) -> str:
    """Helper to generate the Luhn check digit for a 15-digit prefix."""
    digits = [int(c) for c in prefix_15]
    total = 0
    # From right to left (where check digit will be at index 15 / offset 0 from right):
    # Prefix digits will be at offsets 1, 2, 3... from right.
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:  # offset 1 from right of full number
            d *= 2
            if d > 9:
                d -= 9
        total += d
    check_digit = (10 - (total % 10)) % 10
    return str(check_digit)


class TestBankCardValidatorValid:
    """Tests for valid synthetic 16-digit card vectors across supported scripts."""

    def test_valid_synthetic_ascii_card(self) -> None:
        """Verify algorithmic synthetic ASCII vector passes checksum and structure."""
        assert is_valid_bank_card_number(_VALID_SYNTHETIC_ASCII) is True

    def test_valid_synthetic_persian_digits_card(self) -> None:
        """Verify equivalent Persian-digit representation passes validation."""
        assert is_valid_bank_card_number(_VALID_SYNTHETIC_PERSIAN) is True

    def test_valid_synthetic_arabic_indic_digits_card(self) -> None:
        """Verify equivalent Arabic-Indic digit representation passes validation."""
        assert is_valid_bank_card_number(_VALID_SYNTHETIC_ARABIC_INDIC) is True

    def test_valid_synthetic_mixed_digits_card(self) -> None:
        """Verify mixed Persian, Arabic-Indic, and ASCII digits pass validation."""
        assert is_valid_bank_card_number(_VALID_SYNTHETIC_MIXED) is True

    @pytest.mark.parametrize(
        "prefix_15",
        [
            "603799123456789",
            "589210123456789",
            "502229123456789",
            "621986123456789",
            "400012345678901",
            "510510510510510",
        ],
    )
    def test_programmatically_generated_valid_vectors(self, prefix_15: str) -> None:
        """Verify independently calculated synthetic Luhn-valid numbers pass."""
        check_digit = _generate_luhn_check_digit(prefix_15)
        full_card = prefix_15 + check_digit
        assert len(full_card) == 16
        assert is_valid_bank_card_number(full_card) is True


class TestBankCardValidatorChecksumMutations:
    """Tests proving that checksum mutations fail validation."""

    @pytest.mark.parametrize(
        "mutation",
        [
            "1234567890123453",  # Last digit mutated from 2 to 3
            "1234567890123451",  # Last digit mutated from 2 to 1
            "1234567890123402",  # Second to last digit mutated
            "1234567890123052",  # Third to last digit mutated
            "2234567890123452",  # First digit mutated from 1 to 2
            "1234567890123450",  # Check digit mutated to 0
            "1234567890123459",  # Check digit mutated to 9
        ],
    )
    def test_checksum_mutations_rejected(self, mutation: str) -> None:
        """Verify single-digit mutations fail Luhn checksum."""
        assert is_valid_bank_card_number(mutation) is False

    def test_systematic_single_digit_mutations(self) -> None:
        """Systematically mutate each of the 16 numeric digits and verify failure."""
        card = "1234567890123452"
        assert len(card) == 16

        for i, char in enumerate(card):
            original_digit = int(char)
            # Replace digit with (original + 1) % 10
            mutated_digit = (original_digit + 1) % 10
            mutated_card = card[:i] + str(mutated_digit) + card[i + 1 :]
            assert is_valid_bank_card_number(mutated_card) is False, (
                f"Mutation at index {i} ({mutated_card}) unexpectedly passed"
            )


class TestBankCardValidatorTrivialSequences:
    """Tests verifying defensive false-positive rejection of all-identical sequences."""

    @pytest.mark.parametrize(
        "trivial_sequence",
        [
            "0000000000000000",
            "1111111111111111",
            "2222222222222222",
            "3333333333333333",
            "4444444444444444",
            "5555555555555555",
            "6666666666666666",
            "7777777777777777",
            "8888888888888888",
            "9999999999999999",
            "۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰",
            "۱۱۱۱۱۱۱۱۱۱۱۱۱۱۱۱",
            "٠٠٠٠٠٠٠٠٠٠٠٠٠٠٠٠",
        ],
    )
    def test_all_identical_digits_rejected(self, trivial_sequence: str) -> None:
        """All-identical sequences are rejected regardless of Luhn status."""
        assert is_valid_bank_card_number(trivial_sequence) is False


class TestBankCardValidatorFormattingAndLength:
    """Tests verifying strict formatting, exact length, and non-digit rejection."""

    @pytest.mark.parametrize(
        "invalid_length",
        [
            "",  # Empty
            "1234",  # 4 digits
            "123456789012345",  # 15 digits (1 too short)
            "12345678901234520",  # 17 digits (1 too long)
            "1234567890123456789",  # 19 digits
        ],
    )
    def test_invalid_length_rejected(self, invalid_length: str) -> None:
        """Strings differing from exactly 16 characters are rejected."""
        assert is_valid_bank_card_number(invalid_length) is False

    @pytest.mark.parametrize(
        "formatted_card",
        [
            " 1234567890123452",  # Leading space
            "1234567890123452 ",  # Trailing space
            "1234 5678 9012 3452",  # 4-4-4-4 format spaces
            "1234-5678-9012-3452",  # Hyphenated
            "1234\t567890123452",  # Tab character
            "1234\n567890123452",  # Newline character
            "1234\u200c567890123452",  # Zero-width non-joiner (ZWNJ)
        ],
    )
    def test_non_compact_formatting_rejected(self, formatted_card: str) -> None:
        """Validator does not strip whitespace, hyphens, or separators."""
        assert is_valid_bank_card_number(formatted_card) is False

    @pytest.mark.parametrize(
        "non_digit_value",
        [
            "123456789012345A",  # Letter A
            "123456789012345z",  # Letter z
            "123456789012345_",  # Underscore
            "123456789012345.",  # Period
            "123456789012345#",  # Hash
            "۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵A",  # Persian with letter
            "१२३۴۵۶۷۸۹۰۱۲۳۴۵۲",  # Devanagari numerals
            "①②③④⑤⑥⑦⑧⑨0123452",  # Circled numbers
            "IV34567890123452",  # Roman numerals
        ],
    )
    def test_non_digits_and_unsupported_numerals_rejected(
        self, non_digit_value: str
    ) -> None:
        """Only ASCII, Persian, and Arabic-Indic digit scripts are accepted."""
        assert is_valid_bank_card_number(non_digit_value) is False


class TestBankCardValidatorTypes:
    """Tests verifying non-string types return False without raising exceptions."""

    @pytest.mark.parametrize(
        "non_string",
        [
            None,
            1234567890123452,
            123,
            [],
            {},
            b"1234567890123452",
            object(),
            True,
            False,
        ],
    )
    def test_non_string_inputs_return_false(self, non_string: object) -> None:
        """Non-string inputs safely return False."""
        assert is_valid_bank_card_number(non_string) is False  # type: ignore[arg-type]
