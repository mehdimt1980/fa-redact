"""Validation for 16-digit payment card numbers (Primary Account Number / PAN).

Validates 16-digit payment card numbers using the standard Luhn checksum algorithm
(ISO/IEC 7812). Position-preserving digit normalization allows Persian and Arabic-Indic
digits to be validated.

Note:
    Validation verifies mathematical structure and Luhn checksum compliance only.
    It does not query bank/issuer registries, identify card brands, or verify card
    activation, ownership, or account existence.
"""

from __future__ import annotations

from fa_redact.normalization import normalize_digits

_REQUIRED_LENGTH: int = 16


def _luhn_is_valid(normalized_card: str) -> bool:
    """Calculate the standard Luhn checksum for a 16-digit normalized numeric string.

    Iterates from the rightmost digit (offset 0), doubling every second digit
    (odd offsets from right), subtracting 9 if the doubled product exceeds 9,
    and verifying the total sum is congruent to 0 modulo 10.

    Args:
        normalized_card: A 16-character ASCII numeric string.

    Returns:
        True if the Luhn checksum is valid, False otherwise.
    """
    digits = [int(c) for c in normalized_card]
    total = 0

    for offset, digit in enumerate(reversed(digits)):
        if offset % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit

    return total % 10 == 0


def is_valid_bank_card_number(value: str) -> bool:
    """Validate whether a string is a valid 16-digit payment card number (PAN).

    Validates that the input conforms strictly to the compact electronic format
    of a 16-digit payment card with a valid Luhn checksum.

    Validation rules:
    - Input must be a string of exactly 16 characters after digit normalization.
    - No automatic whitespace stripping, trimming, or formatting (spaces and hyphens
      are rejected).
    - All 16 characters must be numeric digits (ASCII, Persian, or Arabic-Indic).
    - Rejects all-identical sequences (e.g., '0000000000000000', '1111111111111111')
      as a defensive false-positive filter.
    - Must satisfy the standard Luhn checksum algorithm.

    Args:
        value: Candidate bank card number string.

    Returns:
        True if the candidate is a structurally valid 16-digit card number,
        False otherwise.
    """
    if not isinstance(value, str):
        return False

    normalized = normalize_digits(value)

    if len(normalized) != _REQUIRED_LENGTH:
        return False

    if not (normalized.isascii() and normalized.isdigit()):
        return False

    # Defensive false-positive filter: reject all-identical digit sequences
    if len(set(normalized)) == 1:
        return False

    return _luhn_is_valid(normalized)
