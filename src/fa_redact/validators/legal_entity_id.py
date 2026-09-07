"""Iranian Legal Entity National ID (شناسه ملی اشخاص حقوقی) validation."""

from __future__ import annotations

from typing import Final

from fa_redact.normalization import normalize_digits

# Variant A coefficient sequence for the first 10 digits
_COEFFICIENTS_VARIANT_A: Final[tuple[int, ...]] = (
    29,
    27,
    23,
    19,
    17,
    29,
    27,
    23,
    19,
    17,
)


def is_valid_iranian_legal_entity_id(value: str) -> bool:
    """Validate the checksum structure of an Iranian Legal Entity National ID.

    Accepts 11-character strings consisting of ASCII digits, Persian digits (۰-۹),
    Arabic-Indic digits (٠-٩), or mixed representations thereof.

    Strict validation policy:
        - Exact length of 11 characters required.
        - No whitespace, separators, hyphens, or non-digit characters allowed.
        - No zero-padding performed; leading zeros are preserved semantically.
        - Rejects all identical/repeated digit patterns ('00000000000'..'99999999999').
        - Validates the standard modulo-11 weighted check digit using the Variant A
          formula (coefficients [29, 27, 23, 19, 17, 29, 27, 23, 19, 17], 10th-digit
          offset factor `d[9] + 2`, modulo 11, remainder 10 -> 0).

    Note:
        The checksum implementation follows the Variant A formula selected in Phase 27
        from reviewed technical implementations and limited empirical verification. No
        primary statutory publication of the arithmetic formula was identified.
        Checksum validity confirms structural mathematical integrity only. It does NOT
        verify whether the legal entity exists, has been officially registered with the
        State Organization for Registration of Deeds and Properties (SSAA), is in active
        legal status, or has authorized standing.

    Args:
        value: Candidate legal entity national ID string.

    Returns:
        True if the candidate has a valid 11-digit format and correct check digit;
        False otherwise.
    """
    if not isinstance(value, str) or len(value) != 11:
        return False

    normalized = normalize_digits(value)
    if not (normalized.isascii() and normalized.isdigit()):
        return False

    # Reject repeated-digit pseudo-values (00000000000, 11111111111, ..., 99999999999)
    if len(set(normalized)) == 1:
        return False

    digits = [int(c) for c in normalized]
    add_val = digits[9] + 2
    total = sum((digits[i] + add_val) * _COEFFICIENTS_VARIANT_A[i] for i in range(10))
    remainder = total % 11
    expected_check_digit = 0 if remainder == 10 else remainder

    return digits[10] == expected_check_digit
