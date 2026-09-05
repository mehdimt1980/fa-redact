"""Iranian National ID (Code Melli) validation."""

from __future__ import annotations

from fa_redact.normalization import normalize_digits


def is_valid_national_id(value: str) -> bool:
    """Validate the checksum structure of an Iranian individual National ID.

    Accepts 10-character strings consisting of ASCII digits, Persian digits (۰-۹),
    Arabic-Indic digits (٠-٩), or mixed representations thereof.

    Strict validation policy:
        - Exact length of 10 characters required.
        - No whitespace, separators, hyphens, or non-digit characters allowed.
        - No 8/9-digit zero-padding performed.
        - Rejects all identical/repeated digit patterns ('0000000000'..'9999999999').
        - Validates the standard modulo-11 weighted check digit.

    Note:
        Checksum validity confirms structural mathematical integrity only. It does NOT
        verify whether the ID has actually been issued or belongs to a real individual.

    Args:
        value: Candidate national ID string.

    Returns:
        True if the candidate has a valid 10-digit format and correct check digit;
        False otherwise.
    """
    if not isinstance(value, str) or len(value) != 10:
        return False

    normalized = normalize_digits(value)
    if not (normalized.isascii() and normalized.isdigit()):
        return False

    # Reject repeated-digit pseudo-values (0000000000, 1111111111, ..., 9999999999)
    if len(set(normalized)) == 1:
        return False

    total = sum(int(normalized[i]) * (10 - i) for i in range(9))
    remainder = total % 11
    expected_check_digit = remainder if remainder < 2 else 11 - remainder

    return int(normalized[9]) == expected_check_digit
