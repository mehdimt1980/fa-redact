"""Position-preserving Persian and Arabic-Indic text normalization.

This module provides deterministic, 1-to-1 Unicode code point transformations
designed to normalize digits and common Arabic letter variants without altering
character positions or string length.

Architectural Invariant:
    For every string `s`, the following holds:
        len(normalize_digits(s)) == len(s)
        len(normalize_letters(s)) == len(s)
        len(normalize_text(s)) == len(s)

This invariant ensures that character offsets (start/end indices) computed on
normalized text map 1-to-1 to the original input text.
"""

from __future__ import annotations

# Mapping Persian (Extended Arabic-Indic) digits and Arabic-Indic digits to ASCII digits
_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ASCII_DIGITS = "0123456789"

_DIGIT_TRANSLATION_TABLE: dict[int, int] = str.maketrans(
    _PERSIAN_DIGITS + _ARABIC_INDIC_DIGITS,
    _ASCII_DIGITS + _ASCII_DIGITS,
)

# Mapping Arabic letter variants to Persian standard code points
# ي (U+064A) -> ی (U+06CC)
# ك (U+0643) -> ک (U+06A9)
_ARABIC_LETTERS = "يك"
_PERSIAN_LETTERS = "یک"

_LETTER_TRANSLATION_TABLE: dict[int, int] = str.maketrans(
    _ARABIC_LETTERS,
    _PERSIAN_LETTERS,
)

# Combined translation table for all supported 1-to-1 normalizations
_ALL_TRANSLATION_TABLE: dict[int, int] = {
    **_DIGIT_TRANSLATION_TABLE,
    **_LETTER_TRANSLATION_TABLE,
}


def normalize_digits(text: str) -> str:
    """Normalize Persian and Arabic-Indic digits to ASCII digits.

    Transforms:
        ۰-۹ (U+06F0..U+06F9) -> 0-9 (U+0030..U+0039)
        ٠-٩ (U+0660..U+0669) -> 0-9 (U+0030..U+0039)

    Guarantees:
        len(normalize_digits(text)) == len(text)

    Args:
        text: Input string.

    Returns:
        String with all Persian and Arabic-Indic digits replaced by ASCII digits.
    """
    return text.translate(_DIGIT_TRANSLATION_TABLE)


def normalize_letters(text: str) -> str:
    """Normalize common Arabic letter variants to Persian code points.

    Transforms only:
        ي (U+064A ARABIC LETTER YEH) -> ی (U+06CC ARABIC LETTER FARSI YEH)
        ك (U+0643 ARABIC LETTER KAF) -> ک (U+06A9 ARABIC LETTER KEHEH)

    Other Arabic characters (such as ى, ة, ۀ, ؤ, إ, أ) remain unchanged.

    Guarantees:
        len(normalize_letters(text)) == len(text)

    Args:
        text: Input string.

    Returns:
        String with supported Arabic letter variants replaced by Persian equivalents.
    """
    return text.translate(_LETTER_TRANSLATION_TABLE)


def normalize_text(text: str) -> str:
    """Apply position-preserving normalization (digits and supported letters).

    Combines digit normalization (Persian and Arabic-Indic -> ASCII) and
    letter normalization (ي -> ی, ك -> ک).

    Guarantees:
        len(normalize_text(text)) == len(text)

    Args:
        text: Input string.

    Returns:
        Normalized string with identical length and preserved character offsets.
    """
    return text.translate(_ALL_TRANSLATION_TABLE)
