"""Validator for Iranian International Bank Account Numbers (IBAN / Sheba).

An Iranian electronic IBAN consists of the 2-letter uppercase country code 'IR'
followed by 2 check digits and a 22-digit Basic Bank Account Number (BBAN),
totaling exactly 26 characters.

Validation uses the standard IBAN MOD-97 checksum algorithm (ISO 13616 / ISO 7064).
Position-preserving digit normalization allows Persian and Arabic-Indic digits to be
validated.

Note:
    Validation verifies mathematical structure and checksum compliance only.
    It does not query bank registries or verify account existence, ownership,
    or active status.
"""

from __future__ import annotations

from fa_redact.normalization import normalize_digits

_COUNTRY_CODE: str = "IR"
_TOTAL_LENGTH: int = 26
_NUMERIC_DIGIT_COUNT: int = 24


def _mod97_is_valid(normalized_iban: str) -> bool:
    """Calculate MOD-97 checksum for a normalized 26-character Iranian IBAN.

    Rearranges IBAN as: BBAN (22 digits) + Country letters ('IR' -> '1827')
    + Check digits (2 digits).
    Processes the resulting 28-character numeric string via streaming modulo-97.

    Returns:
        True if remainder is 1, False otherwise.
    """
    check_digits = normalized_iban[2:4]
    bban = normalized_iban[4:26]
    # 'I' -> 18, 'R' -> 27
    numeric_repr = f"{bban}1827{check_digits}"

    remainder = 0
    for char in numeric_repr:
        remainder = (remainder * 10 + int(char)) % 97

    return remainder == 1


def is_valid_iranian_iban(value: str) -> bool:
    """Validate whether a string is a valid Iranian IBAN (Sheba).

    Validates that the input conforms strictly to the compact electronic format
    of an Iranian IBAN (IR followed by 24 digits, total length 26 characters)
    with a valid MOD-97 checksum.

    Validation rules:
    - Input must be a string of exactly 26 characters after digit normalization.
    - No automatic whitespace stripping, trimming, or formatting.
    - Must start with uppercase ASCII letters 'IR' (lowercase 'ir' is rejected).
    - Remaining 24 characters must be numeric digits (ASCII, Persian, or Arabic-Indic).
    - Must satisfy the MOD-97 checksum algorithm.

    Args:
        value: The string to validate.

    Returns:
        True if the value is a structurally valid Iranian IBAN, False otherwise.
    """
    if not isinstance(value, str):
        return False

    normalized = normalize_digits(value)

    if len(normalized) != _TOTAL_LENGTH:
        return False

    if not normalized.startswith(_COUNTRY_CODE):
        return False

    numeric_part = normalized[len(_COUNTRY_CODE) :]
    if not all("0" <= c <= "9" for c in numeric_part):
        return False

    return _mod97_is_valid(normalized)
