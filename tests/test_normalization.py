"""Tests for position-preserving Persian text normalization (Phase 2)."""

from fa_redact import normalize_digits, normalize_letters, normalize_text


def test_persian_digits() -> None:
    """Verify Persian digits (۰-۹) map to ASCII digits (0-9)."""
    original = "۰۱۲۳۴۵۶۷۸۹"
    expected = "0123456789"
    assert normalize_digits(original) == expected
    assert normalize_text(original) == expected


def test_arabic_indic_digits() -> None:
    """Verify Arabic-Indic digits (٠-٩) map to ASCII digits (0-9)."""
    original = "٠١٢٣٤٥٦٧٨٩"
    expected = "0123456789"
    assert normalize_digits(original) == expected
    assert normalize_text(original) == expected


def test_mixed_digits() -> None:
    """Verify strings containing mixed Persian, Arabic-Indic, and ASCII digits."""
    original = "Patient-۱۲٣45"
    expected = "Patient-12345"
    assert normalize_digits(original) == expected
    assert normalize_text(original) == expected


def test_arabic_letter_variants() -> None:
    """Verify isolated and embedded Arabic letter normalization (ي -> ی, ك -> ک)."""
    # Isolated
    assert normalize_letters("ي") == "ی"
    assert normalize_letters("ك") == "ک"
    assert normalize_text("يك") == "یک"

    # Embedded in Persian words
    assert normalize_letters("پزشك") == "پزشک"
    assert normalize_letters("دكتر") == "دکتر"
    assert normalize_letters("بانك") == "بانک"
    assert normalize_letters("پيام") == "پیام"
    assert normalize_letters("علي") == "علی"
    assert normalize_letters("بيمارستان") == "بیمارستان"

    # Digits function should NOT alter letters
    assert normalize_digits("پزشك") == "پزشك"


def test_combined_normalization() -> None:
    """Verify combined letters and digits normalization in a sentence."""
    original = "كد ملي بیمار ۰۰۱٢٣٤٥٦٧٨ است"
    expected = "کد ملی بیمار 0012345678 است"
    assert normalize_text(original) == expected


def test_already_normalized_text() -> None:
    """Verify ASCII digits and standard Persian letters remain unchanged."""
    text = "کد ملی بیمار 0012345678 و نتیجه آزمایش طبیعی است."
    assert normalize_digits(text) == text
    assert normalize_letters(text) == text
    assert normalize_text(text) == text


def test_unrelated_content_preservation() -> None:
    """Verify English, symbols, whitespace, URLs, and emails are preserved."""
    test_cases = [
        "Hello World!",
        "user@hospital.example.ir",
        "https://clinical-portal.ir/records/123?auth=true",
        "BP: 120/80 mmHg, SpO2: 98%, Temp: 37.0 C",
        "Tabs:\t\tNewlines:\n\nSpaces:   End.",
        "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?",
    ]
    for text in test_cases:
        assert normalize_digits(text) == text
        assert normalize_letters(text) == text
        assert normalize_text(text) == text


def test_zwnj_preservation() -> None:
    """Verify Zero Width Non-Joiner (U+200C) is strictly preserved at exact indices."""
    zwnj = "\u200c"
    test_cases = [
        f"می{zwnj}شود",
        f"بی{zwnj}حسی",
        f"خانه{zwnj}اش",
        f"بیمه{zwnj}شده با شماره ۱۲۳",
    ]
    for original in test_cases:
        normalized = normalize_text(original)
        assert zwnj in normalized
        assert len(normalized) == len(original)
        # Verify ZWNJ position matches exactly
        for i, char in enumerate(original):
            if char == zwnj:
                assert normalized[i] == zwnj


def test_unsupported_arabic_characters_untouched() -> None:
    """Verify out-of-scope Arabic code points are NOT silently modified."""
    unsupported = "ىةۀؤإأ"
    assert normalize_letters(unsupported) == unsupported
    assert normalize_text(unsupported) == unsupported

    # Within words
    words = ["موسیٰ", "فاطمة", "مسئله", "مؤثر", "إدارة", "أحمد"]
    for word in words:
        assert normalize_letters(word) == word
        assert normalize_text(word) == word


def test_empty_string() -> None:
    """Verify empty string returns empty string."""
    assert normalize_digits("") == ""
    assert normalize_letters("") == ""
    assert normalize_text("") == ""


def test_length_and_position_preservation_invariant() -> None:
    """Verify len(normalized) == len(original) and offsets remain identical."""
    samples = [
        "۰۱۲۳۴۵۶۷۸۹",
        "٠١٢٣٤٥٦٧٨٩",
        "Patient-۱۲٣45",
        "كد ملي بیمار ۰۰۱٢٣٤٥٦٧٨ است",
        "گزارش بالینی:\nبیمار با تب ۳۸.۵ درجه مراجعه كرده است.",
        "داروی تجویزی: Amoxicillin 500mg هر ۸ ساعت یک‌بار.",
        "خط ۱: كد ۱۲۳\nخط ۲: كد ٤٥٦\nخط ۳: كد 789\n",
    ]

    for text in samples:
        for fn in (normalize_digits, normalize_letters, normalize_text):
            normalized = fn(text)
            assert len(normalized) == len(text), (
                f"Length mismatch with {fn.__name__} for '{text}'"
            )

            # Check code point by code point
            for i, (orig, norm) in enumerate(zip(text, normalized, strict=True)):
                if orig not in "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩يك":
                    assert norm == orig, (
                        f"Unexpected modification at {i}: {orig!r} -> {norm!r}"
                    )


def test_healthcare_synthetic_example() -> None:
    """Verify realistic synthetic clinical text normalization."""
    original = "بیمار با شناسه ۱۲۳٤٥ و HbA1c=7.2 در بخش ICU بستری است."
    expected = "بیمار با شناسه 12345 و HbA1c=7.2 در بخش ICU بستری است."

    normalized = normalize_text(original)
    assert normalized == expected
    assert len(normalized) == len(original)
    assert "HbA1c=7.2" in normalized
    assert "ICU" in normalized
