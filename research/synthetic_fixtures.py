"""Synthetic challenge fixtures for Persian Named Entity Recognition (NER).

===============================================================================
DISCLAIMER & PRIVACY NOTICE:
ALL EXAMPLES IN THIS MODULE ARE 100% SYNTHETIC AND ARTIFICIALLY CONSTRUCTED.
NO REAL PATIENT DATA, CLINICAL RECORDS, OR PERSONAL IDENTIFIERS WERE USED.
THIS FIXTURE SET IS DESIGNED SOLELY FOR ARCHITECTURAL TESTING AND EVALUATION
HARNESS VERIFICATION, NOT AS A REAL-WORLD CLINICAL ACCURACY BENCHMARK.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass

from research.evaluation import EntitySpan


@dataclass(frozen=True, slots=True)
class SyntheticFixture:
    """A synthetic test sentence with labeled gold entity spans.

    Attributes:
        id: Unique identifier for the challenge fixture.
        category: Challenge category (e.g. 'compound_surname', 'common_noun_ambiguity').
        description: Description of the specific linguistic challenge being tested.
        text: Synthetic Persian text string.
        gold_spans: List of gold EntitySpan instances.
    """

    id: str
    category: str
    description: str
    text: str
    gold_spans: list[EntitySpan]

    def verify_spans(self) -> None:
        """Verify that all span offsets correctly index the text string."""
        for span in self.gold_spans:
            if span.start < 0 or span.end > len(self.text) or span.start >= span.end:
                raise ValueError(
                    f"Fixture {self.id}: invalid span [{span.start}:{span.end}] "
                    f"for text length {len(self.text)}"
                )


def _build_fixture(
    id: str,
    category: str,
    description: str,
    text: str,
    spans: list[tuple[int, int, str]],
) -> SyntheticFixture:
    """Helper to construct and validate a SyntheticFixture."""
    entity_spans = [EntitySpan(start=s[0], end=s[1], type=s[2]) for s in spans]
    fixture = SyntheticFixture(
        id=id,
        category=category,
        description=description,
        text=text,
        gold_spans=entity_spans,
    )
    fixture.verify_spans()
    return fixture


# Synthetic test cases covering Persian NER linguistic edge cases
SYNTHETIC_CHALLENGE_FIXTURES: list[SyntheticFixture] = [
    # 1. Standard First + Last Names
    _build_fixture(
        id="syn_01_standard_name",
        category="standard_name",
        description="Standard single first and last name in a declarative sentence.",
        text="سارا رضایی به عنوان سرپرست جدید تیم انتخاب گردید.",
        spans=[(0, 10, "PERSON")],  # "سارا رضایی"
    ),
    # 2. Compound Multi-Token Surname
    _build_fixture(
        id="syn_02_compound_surname",
        category="compound_surname",
        description="Compound surname containing prefix and suffix tokens.",
        text="گزارش توسط سید علی طباطبایی نژاد تهیه و ارسال گردید.",
        spans=[(11, 35, "PERSON")],  # "سید علی طباطبایی نژاد"
    ),
    # 3. Honorific / Title Prefix
    _build_fixture(
        id="syn_03_title_prefixed",
        category="honorific_prefix",
        description="Title 'دکتر' followed by first and last name.",
        text="ویزیت بیمار توسط دکتر مریم کاظمی انجام گرفت.",
        spans=[(17, 33, "PERSON")],  # "دکتر مریم کاظمی"
    ),
    _build_fixture(
        id="syn_04_multiple_titles",
        category="honorific_prefix",
        description="Multiple formal honorifics before personal name.",
        text="خانم مهندس فاطمه صادقی پروژه را تحویل دادند.",
        spans=[(0, 24, "PERSON")],  # "خانم مهندس فاطمه صادقی"
    ),
    # 4. Common Word / Personal Name Homographs
    _build_fixture(
        id="syn_05_ambiguous_common_nouns",
        category="common_noun_ambiguity",
        description="Names identical to common nouns (امید=hope, بهار=spring).",
        text="امید و بهار در فصل بهار با پیروز دیدار کردند.",
        spans=[(0, 4, "PERSON"), (7, 11, "PERSON"), (28, 33, "PERSON")],
    ),
    _build_fixture(
        id="syn_06_adjective_homograph",
        category="common_noun_ambiguity",
        description="Personal name 'روشن' (bright) and 'شریف' (noble) in sentence.",
        text="دکتر روشن یک فرد شریف و با تجربه است.",
        spans=[(0, 9, "PERSON")],  # "دکتر روشن"
    ),
    # 5. Zero-Width Non-Joiner (ZWNJ) in Names
    _build_fixture(
        id="syn_07_zwnj_name",
        category="zwnj_variant",
        description="Names containing ZWNJ (U+200C) within first name and surname.",
        text="علیرضا میرزایی‌فر نامه را امضا کرد.",
        spans=[(0, 19, "PERSON")],  # "علیرضا میرزایی‌فر"
    ),
    # 6. Arabic Character Variants in Names (e.g. ي / ك)
    _build_fixture(
        id="syn_08_arabic_char_variants",
        category="arabic_char_variants",
        description="Name written with Arabic yeh (ي) and kaf (ك).",
        text="جلسه با حضور على كريمى برگزار شد.",
        spans=[(13, 23, "PERSON")],  # "على كريمى"
    ),
    # 7. Punctuation Boundaries (Quotes, Brackets, Parentheses)
    _build_fixture(
        id="syn_09_punctuation_boundary",
        category="punctuation_boundary",
        description="Name enclosed in Persian quotes and parentheses.",
        text="طبق گفته «نیما یوشیج» (شاعر معاصر)، هنر ماندگار است.",
        spans=[(10, 22, "PERSON")],  # "نیما یوشیج"
    ),
    # 8. Name Adjacent to Direct Identifiers
    _build_fixture(
        id="syn_10_adjacent_identifier",
        category="adjacent_identifier",
        description="Name adjacent to National ID and mobile numbers.",
        text="کد ملی احمد رضوی ۰۰۷۵۱۲۳۴۵۶ و شماره تماس ۰۹۱۲۳۴۵۶۷۸۹ ثبت شد.",
        spans=[(7, 16, "PERSON")],  # "احمد رضوی"
    ),
    # 9. Repeated Names in Document
    _build_fixture(
        id="syn_11_repeated_name",
        category="repeated_name",
        description="Same person mentioned multiple times in short text.",
        text="دکتر حسینی وارد شد. سپس دکتر حسینی نسخه را بررسی نمود.",
        spans=[(0, 11, "PERSON"), (25, 36, "PERSON")],  # "دکتر حسینی"
    ),
    # 10. Medical / Clinical Setting
    _build_fixture(
        id="syn_12_clinical_context",
        category="clinical_context",
        description="Medical consultation note with patient and attending doctor.",
        text=(
            "بیمار خانم زهرا ابراهیمی توسط دکتر بهرامی "
            "ویزیت شد و آزمایش خون تجویز گردید."
        ),
        spans=[
            (6, 24, "PERSON"),
            (30, 41, "PERSON"),
        ],  # "خانم زهرا ابراهیمی", "دکتر بهرامی"
    ),
    # 11. Negative Control (Hospital / Clinic Name, No Person Name)
    _build_fixture(
        id="syn_13_negative_control_institution",
        category="negative_control",
        description="Hospital named after a person (بیمارستان شهید بهشتی) -> negative.",
        text=(
            "بیمارستان شهید بهشتی و دانشگاه علوم پزشکی تهران "
            "تفاهم‌نامه همکاری امضا کردند."
        ),
        spans=[],  # No standalone PERSON entity
    ),
    # 12. Negative Control (Medical terminology and medication)
    _build_fixture(
        id="syn_14_negative_control_clinical_terms",
        category="negative_control",
        description="Clinical terms, anatomy, and pharmacology without personal names.",
        text="داروی آتورواستاتین برای کنترل چربی خون بیمار تجویز و پرونده بایگانی شد.",
        spans=[],  # No PERSON entity
    ),
]
