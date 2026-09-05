"""Conservative ASCII Internet Email address validation."""

from __future__ import annotations

import re

# Allowed ASCII atom characters for dot-atom local parts (RFC 5322 section 3.2.3)
_LOCAL_ATOM_CHARS: frozenset[str] = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'*+-/=?^_`{|}~"
)

# ASCII letters and digits for domain labels
_DOMAIN_LABEL_CHARS: frozenset[str] = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
)

_ASCII_LETTERS: frozenset[str] = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
)

_PUNYCODE_TLD_PATTERN: re.Pattern[str] = re.compile(r"^xn--[A-Za-z0-9-]{1,59}$")

_MAX_TOTAL_LENGTH: int = 254
_MAX_LOCAL_PART_LENGTH: int = 64
_MAX_DOMAIN_LENGTH: int = 253
_MAX_LABEL_LENGTH: int = 63
_MIN_TLD_LENGTH: int = 2


def is_valid_email(value: str) -> bool:
    """Validate whether a string is a valid conservative ASCII Internet email address.

    Validates that the input conforms strictly to a conservative ASCII dot-atom
    local part and DNS-style domain name structure.

    Validation rules:
    - Input must be a non-empty string of at most 254 characters.
    - No automatic whitespace stripping, trimming, lowercasing, or normalization.
    - Contains exactly one '@' character separating local-part and domain.
    - Local-part: 1 to 64 ASCII characters; dot-atom syntax using allowed atom
      characters (A-Z, a-z, 0-9, and !#$%&'*+-/=?^_`{|}~); dots are permitted
      only as atom separators (no leading, trailing, or consecutive dots).
    - Domain: 1 to 253 ASCII characters consisting of dot-separated labels.
    - Domain must contain at least one dot (single-label domains such as
      'localhost' are rejected).
    - Each domain label: 1 to 63 characters containing ASCII letters, digits, or
      hyphens; cannot start or end with a hyphen; underscores are rejected.
    - Final domain label (TLD): 2 to 63 alphabetic ASCII characters, or valid
      ASCII punycode (starting with 'xn--').
    - Quoted local-parts, domain literals (IP addresses), comments, and
      Unicode/EAI addresses are explicitly rejected.

    Args:
        value: The string to validate.

    Returns:
        True if the value is a valid ASCII Internet email address, False otherwise.
    """
    if not isinstance(value, str) or not value:
        return False

    if len(value) > _MAX_TOTAL_LENGTH:
        return False

    if value.count("@") != 1:
        return False

    local_part, domain = value.split("@")

    # Local-part validation
    if not (1 <= len(local_part) <= _MAX_LOCAL_PART_LENGTH):
        return False

    atoms = local_part.split(".")
    for atom in atoms:
        if not atom:
            return False
        for char in atom:
            if char not in _LOCAL_ATOM_CHARS:
                return False

    # Domain validation
    if not (1 <= len(domain) <= _MAX_DOMAIN_LENGTH):
        return False

    if "." not in domain:
        return False

    labels = domain.split(".")
    for label in labels:
        if not (1 <= len(label) <= _MAX_LABEL_LENGTH):
            return False
        if label.startswith("-") or label.endswith("-"):
            return False
        for char in label:
            if char not in _DOMAIN_LABEL_CHARS:
                return False

    # TLD (final label) validation
    tld = labels[-1]
    if _PUNYCODE_TLD_PATTERN.match(tld):
        return True

    if len(tld) < _MIN_TLD_LENGTH or len(tld) > _MAX_LABEL_LENGTH:
        return False

    for char in tld:
        if char not in _ASCII_LETTERS:
            return False

    return True
