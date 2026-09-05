"""Iranian Mobile Number validation based on the 2026 CRA numbering plan."""

from __future__ import annotations

from fa_redact.normalization import normalize_digits

# Official Mobile services NDC prefixes from the 2026 CRA/ITU-T Numbering Plan snapshot.
# Ranges such as 94... (fixed/non-geographical) and 9950... (public trunk) are excluded.
_MOBILE_NDC_PREFIXES: tuple[str, ...] = (
    "900",
    "901",
    "902",
    "903",
    "904",
    "905",
    "91",
    "920",
    "921",
    "922",
    "923",
    "93",
    "990",
    "991",
    "992",
    "993",
    "994",
    "99510",
    "99550",
    "996",
    "9981",
    "9982",
    "99830",
    "99831",
    "99832",
    "99888",
    "99900",
    "99901",
    "99902",
    "99903",
    "9991",
    "99921",
    "99930",
    "99931",
    "99932",
    "99933",
    "99934",
    "9995",
    "99969",
    "99977",
    "9998",
    "9999",
)


def _extract_nsn(normalized: str) -> str | None:
    """Extract the 10-digit NSN from compact phone strings.

    Args:
        normalized: Digit-normalized input string.

    Returns:
        10-digit NSN string starting with '9', or None if the format is invalid.
    """
    if normalized.startswith("+989") and len(normalized) == 13:
        nsn = normalized[3:]
        if nsn.isascii() and nsn.isdigit():
            return nsn
    elif normalized.startswith("00989") and len(normalized) == 14:
        nsn = normalized[4:]
        if nsn.isascii() and nsn.isdigit():
            return nsn
    elif (
        normalized.startswith("09")
        and not normalized.startswith("00")
        and len(normalized) == 11
    ):
        nsn = normalized[1:]
        if nsn.isascii() and nsn.isdigit():
            return nsn

    return None


def is_valid_mobile_number(value: str) -> bool:
    """Validate whether a string is a valid Iranian mobile phone number.

    Accepts compact representations using ASCII digits, Persian digits (۰-۹),
    Arabic-Indic digits (٠-٩), or mixed sets:
        - Domestic: '09xxxxxxxxx' (11 digits)
        - International plus: '+989xxxxxxxxx' (13 characters)
        - International dial prefix: '00989xxxxxxxxx' (14 characters)

    Validation rules:
        - Requires an exact compact representation (no spaces, hyphens, or separators).
        - Extracts the 10-digit National Significant Number (NSN).
        - Validates the NSN against the official 2026 CRA Mobile services NDC prefixes.
        - Rejects fixed non-geographical numbers (e.g. 094...), public trunk ranges,
          and unlisted prefix allocations.

    Note:
        Prefix validation verifies structural allocation according to the bundled
        2026 CRA National Numbering Plan snapshot. It does not verify subscriber
        ownership, active SIM status, or carrier identity.

    Args:
        value: Candidate mobile number string.

    Returns:
        True if the candidate represents a valid mobile number format; False otherwise.
    """
    if not isinstance(value, str):
        return False

    normalized = normalize_digits(value)
    nsn = _extract_nsn(normalized)
    if nsn is None:
        return False

    return any(nsn.startswith(prefix) for prefix in _MOBILE_NDC_PREFIXES)
