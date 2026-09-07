"""Deterministic synthetic regression corpus for fa-redact detectors.

===============================================================================
DISCLAIMER & PRIVACY NOTICE:
ALL EXAMPLES IN THIS MODULE ARE 100% SYNTHETIC AND ARTIFICIALLY CONSTRUCTED.
NO REAL PATIENT RECORDS, CLINICAL DOCUMENTS, CUSTOMER PROFILES, OR ACTUAL
PERSONAL IDENTIFIERS WERE USED.
ALL IDENTIFIERS ARE ARTIFICIALLY SYNTHESIZED TO TEST CHECKSUM, PREFIX,
AND SYNTACTIC PATTERN VALIDATORS IN AN OFFLINE, CONTROLLED RESEARCH ENVIRONMENT.
===============================================================================
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fa_redact.detectors.pattern import PatternRule
from research.evaluation import EntitySpan


@dataclass(frozen=True, slots=True)
class SyntheticDetectionCase:
    """An immutable synthetic test case for detector evaluation.

    Attributes:
        id: Unique non-empty identifier for the test case.
        suite: Target detector suite (e.g. 'default', 'email', 'bank_card', 'pattern').
        category: Test category (e.g. 'national_id_positive', 'mobile_script_variant').
        description: Non-empty description of the test scenario.
        text: Synthetic Persian/ASCII test string.
        gold_spans: Immutable tuple of gold EntitySpan instances.
    """

    id: str
    suite: str
    category: str
    description: str
    text: str
    gold_spans: tuple[EntitySpan, ...]

    def __post_init__(self) -> None:
        """Validate case metadata and gold span invariants."""
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("id must be a non-empty string")
        if not isinstance(self.suite, str) or not self.suite.strip():
            raise ValueError("suite must be a non-empty string")
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("category must be a non-empty string")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be a non-empty string")
        if not isinstance(self.text, str):
            raise TypeError(f"text must be str, got {type(self.text).__name__}")

        # Ensure gold_spans is a tuple of EntitySpan and validate bounds
        spans = tuple(self.gold_spans)
        object.__setattr__(self, "gold_spans", spans)

        seen_spans: set[EntitySpan] = set()
        text_len = len(self.text)
        for span in spans:
            if not isinstance(span, EntitySpan):
                raise TypeError(
                    f"gold_spans must contain EntitySpan, got {type(span).__name__}"
                )
            if span.start < 0 or span.end > text_len or span.start >= span.end:
                raise ValueError(
                    f"Case {self.id!r}: invalid span [{span.start}:{span.end}] "
                    f"for text of length {text_len}"
                )
            if span in seen_spans:
                raise ValueError(
                    f"Case {self.id!r}: duplicate gold span detected: "
                    f"[{span.start}:{span.end}] type={span.type!r}"
                )
            seen_spans.add(span)


def _span_for(
    text: str,
    substring: str,
    entity_type: str,
    *,
    occurrence: int = 1,
) -> EntitySpan:
    """Find exact character offsets for a substring occurrence in synthetic text.

    Args:
        text: Full synthetic source string.
        substring: Exact substring to locate.
        entity_type: Target entity type name.
        occurrence: 1-based occurrence index of substring in text (default 1).

    Returns:
        EntitySpan with exact character start/end offsets.

    Raises:
        ValueError: If occurrence < 1 or if the requested occurrence is not found.
    """
    if occurrence < 1:
        raise ValueError(f"occurrence must be >= 1, got {occurrence}")
    if not substring:
        raise ValueError("substring must be non-empty")

    start_idx = 0
    found_idx = -1
    for _ in range(occurrence):
        found_idx = text.find(substring, start_idx)
        if found_idx == -1:
            raise ValueError(
                f"Substring {substring!r} (occurrence {occurrence}) "
                f"not found in text: {text!r}"
            )
        start_idx = found_idx + 1

    return EntitySpan(
        start=found_idx,
        end=found_idx + len(substring),
        type=entity_type,
    )


def _build_case(
    id: str,
    suite: str,
    category: str,
    description: str,
    text: str,
    gold_spans: Sequence[EntitySpan] = (),
) -> SyntheticDetectionCase:
    """Helper to construct a validated SyntheticDetectionCase."""
    return SyntheticDetectionCase(
        id=id,
        suite=suite,
        category=category,
        description=description,
        text=text,
        gold_spans=tuple(gold_spans),
    )


def validate_detection_corpus(
    corpus: Sequence[SyntheticDetectionCase],
) -> tuple[SyntheticDetectionCase, ...]:
    """Validate that a detection corpus has unique IDs and valid cases.

    Args:
        corpus: Sequence of SyntheticDetectionCase instances.

    Returns:
        Immutable tuple of validated SyntheticDetectionCase instances.

    Raises:
        ValueError: If duplicate case IDs exist or if validation fails.
        TypeError: If items in corpus are not SyntheticDetectionCase instances.
    """
    seen_ids: set[str] = set()
    validated_cases: list[SyntheticDetectionCase] = []

    for case in corpus:
        if not isinstance(case, SyntheticDetectionCase):
            raise TypeError(
                f"Expected SyntheticDetectionCase, got {type(case).__name__}"
            )
        if case.id in seen_ids:
            raise ValueError(f"Duplicate corpus case ID detected: {case.id!r}")
        seen_ids.add(case.id)
        validated_cases.append(case)

    return tuple(validated_cases)


# =============================================================================
# SYNTHETIC INSTITUTIONAL PATTERN RULES (EXAMPLES ONLY - NOT UNIVERSAL FORMATS)
# =============================================================================
SYNTHETIC_PATTERN_RULES: tuple[PatternRule, ...] = (
    PatternRule(type="MRN", pattern=r"\bMRN-[0-9]{6}\b"),
    PatternRule(type="PATIENT_ID", pattern=r"\bPAT-[0-9]{6}\b"),
    PatternRule(type="ENCOUNTER_ID", pattern=r"پرونده:\s*([0-9]{5})", group=1),
)


# =============================================================================
# SYNTHETIC DETECTION CORPUS FIXTURES
# =============================================================================

# Suite: default (National ID, Mobile, IBAN)

# 1. National ID - Positive
_NID_POS_1_TEXT = "کد ملی متقاضی 0012345679 در سامانه ثبت گردید."
_NID_POS_2_TEXT = "شماره ملی: 0490784526 جهت احراز هویت دریافت شد."
_NID_POS_3_TEXT = "شناسه ملی ۷۷۳۱۶۸۹۹۵۶ به عنوان شناسه اصلی ثبت شد."
_NID_POS_4_TEXT = "اطلاعات با کد ملی ۰۰۸۰۰۰۰۰۰۲ تایید گردید."
_NID_POS_5_TEXT = "شناسه هویتی ۱۲۳۴۵۶۷۸۹۱ در پرونده درج شده است."
_NID_POS_6_TEXT = "کد ملی عربی ٠٠١٢٣٤٥٦٧٩ و شناسه ٠٤٩٠٧٨٤٥٢٦ ثبت شدند."

# 2. National ID - Negative Controls
_NID_NEG_1_TEXT = "کد ملی با رقم کنترلی اشتباه 0012345678 نباید شناسایی شود."
_NID_NEG_2_TEXT = "ارقام تکراری ۱۱۱۱۱۱۱۱۱۱ و 0000000000 معتبر نیستند."
_NID_NEG_3_TEXT = "کد ناقص ۱۲۳۴۵۶۷۸۹ و کد طولانی ۱۲۳۴۵۶۷۸۹۰۱ شناسه ملی نیستند."
_NID_NEG_4_TEXT = "مبلغ واریزی ۱۲۳۴۵۶ ریال و کد رهگیری ۷۸۹۰۱۲ می‌باشد."

# 3. Mobile Number - Positive
_MCI_POS_1_TEXT = "شماره همراه اول 09121234567 در سیستم ذخیره شد."
_MTN_POS_1_TEXT = "تماس با شماره ایرانسل 09351234567 برقرار شد."
_RTL_POS_1_TEXT = "شماره رایتل 09211234567 جهت ارسال پیامک ثبت گردید."
_MOB_POS_4_TEXT = "همراه 09021234567 و شماره 09901234567 فعال هستند."
_MOB_POS_5_TEXT = "شماره شاتل موبایل 09981123456 در پرونده قید شد."
_MOB_POS_6_TEXT = "شماره با پیش‌شماره 09911234567 آماده دریافت پیام است."

# 4. Mobile Number - Script Variants
_MOB_VAR_1_TEXT = "شماره تماس همراه ۰۹۱۲۱۲۳۴۵۶۷ اعلام گردید."
_MOB_VAR_2_TEXT = "شماره ایرانسل فارسی ۰۹۳۵۱۲۳۴۵۶۷ در سامانه ثبت شد."
_MOB_VAR_3_TEXT = "شماره تماس با ارقام عربی ٠٩١٢١٢٣٤٥٦٧ و ٠٩٢١١٢٣٤٥٦٧ ارسال شد."

# 5. Mobile Number - Negative Controls
_MOB_NEG_1_TEXT = "پیش‌شماره نامعتبر 09501234567 نباید همراه شناسایی شود."
_MOB_NEG_2_TEXT = "شماره کوتاه 0912123456 و طولانی 091212345678 معتبر نیستند."
_MOB_NEG_3_TEXT = "شماره تلفن ثابت 02188776655 نباید تلفن همراه در نظر گرفته شود."
_MOB_NEG_4_TEXT = "کد پیگیری ۹۸۷۶۵۴۳۲۱۰۱ مربوط به سفارش می‌باشد."

# 6. IBAN - Positive
_IBAN_POS_1_TEXT = "شماره شبا IR641234567890123456789012 جهت تسویه حساب اعلام شد."
_IBAN_POS_2_TEXT = "واریز به شبا IR220000000000000000000001 انجام گرفت."
_IBAN_POS_3_TEXT = "شماره شبا با ارقام فارسی IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲ ثبت شد."
_IBAN_POS_4_TEXT = "شبا فارسی دوم IR۲۲۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۱ تایید گردید."
_IBAN_POS_5_TEXT = "شماره شبا عربی IR٦٤١٢٣٤٥٦٧٨٩٠١٢٣٤٥٦٧٨٩٠١٢ ثبت سیستم شد."

# 7. IBAN - Negative Controls
_IBAN_NEG_1_TEXT = "شماره شبای نامعتبر IR001234567890123456789012 نباید تایید شود."
_IBAN_NEG_2_TEXT = "حساب خارجی DE89370400440532013000 نباید شبای ایرانی شناخته شود."
_IBAN_NEG_3_TEXT = "شبا با طول نادرست IR64123456789012345678901 نامعتبر است."
_IBAN_NEG_4_TEXT = "شماره شبا با کاراکتر حرفی IR64123456789012345678901A رد شد."

# 8. Mixed Default Documents
_MIXED_DEF_1_TEXT = (
    "کد ملی 0012345679 و همراه 09121234567 و شبا IR641234567890123456789012 ثبت گردید."
)
_MIXED_DEF_2_TEXT = (
    "شناسه ملی ۰۰۱۲۳۴۵۶۷۹، تماس ۰۹۳۵۱۲۳۴۵۶۷ و شبا IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲ دریافت شد."
)
_MIXED_DEF_3_TEXT = (
    "شماره تماس 09121234567 ثبت شد. در صورت لزوم با 09121234567 تماس حاصل فرمایید."
)
_MIXED_DEF_4_TEXT = "کد ملی: 0490784526، همراه: 09211234567 در پرونده موجود است."
_MIXED_DEF_5_TEXT = (
    "متقاضی اول با کد 0012345679 و متقاضی دوم با شناسه ۷۷۳۱۶۸۹۹۵۶ ثبت نام کردند."
)

# Suite: email

# 9. Email - Positive
_EMAIL_POS_1_TEXT = "جهت ارتباط با ایمیل info@example.com مکاتبه نمایید."
_EMAIL_POS_2_TEXT = "آدرس پشتیبانی support.team@sub.domain.org می‌باشد."
_EMAIL_POS_3_TEXT = "تماس با user.name+tag@company.co.ir امکان‌پذیر است."
_EMAIL_POS_4_TEXT = 'ایمیل رسمی "alice@example.com" و (bob@example.org) هستند.'
_EMAIL_POS_5_TEXT = "ارسال گزارش به [help@clinic.ir] و contact@hospital.ir انجام شد."

# 10. Email - Negative Controls
_EMAIL_NEG_1_TEXT = "آدرس نامعتبر user.example.com فاقد علامت ات‌ساین است."
_EMAIL_NEG_2_TEXT = "ایمیل با دونقطه متوالی user..name@example.com نامعتبر است."
_EMAIL_NEG_3_TEXT = "آدرس ناقص user@domain بدون پسوند دامنه رد می‌شود."
_EMAIL_NEG_4_TEXT = "آدرس با حروف فارسی کاربر@example.com شناسایی نمی‌شود."

# Suite: bank_card

# 11. Bank Card - Positive
_CARD_POS_1_TEXT = "شماره کارت 1234567890123452 جهت انتقال وجه ثبت شد."
_CARD_POS_2_TEXT = "کارت بانکی 5022291234567897 با موفقیت تراکنش داد."
_CARD_POS_3_TEXT = "شماره کارت فارسی ۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۲ در سیستم قید شد."
_CARD_POS_4_TEXT = "کارت عربی ١٢٣٤٥٦٧٨٩٠١٢٣٤٥٢ و [5022291234567897] ثبت شدند."

# 12. Bank Card - Negative Controls
_CARD_NEG_1_TEXT = "کارت با رقم کنترلی اشتباه 1234567890123450 باید رد شود."
_CARD_NEG_2_TEXT = "ارقام تکراری 1111111111111111 کارت معتبر بانکی نیستند."
_CARD_NEG_3_TEXT = "شماره با طول نادرست 123456789012345 کارت ۱۶ رقمی نیست."

# Suite: pattern

# 13. Pattern - Positive
_PAT_POS_1_TEXT = "شماره پرونده بالینی MRN-123456 در سیستم ثبت گردید."
_PAT_POS_2_TEXT = "شناسه بیمار PAT-987654 جهت پذیرش استفاده شد."
_PAT_POS_3_TEXT = "شماره پرونده: 54321 در بخش بایگانی ثبت شد."
_PAT_POS_4_TEXT = "بیمار با شناسه PAT-112233 و پرونده MRN-654321 ترخیص شد."

# 14. Pattern - Normalized Digits
_PAT_NORM_1_TEXT = "شماره پرونده: ۵۴۳۲۱ با ارقام فارسی ثبت شد."
_PAT_NORM_2_TEXT = "شناسه پرونده: ٩٨٧٦٥ با ارقام عربی پذیرش گردید."

# 15. Pattern - Negative Controls
_PAT_NEG_1_TEXT = "کد حسابداری ACC-123456 نباید با الگوی بیمارستانی تطابق یابد."
_PAT_NEG_2_TEXT = "شماره کوتاه MRN-12345 و طولانی PAT-1234567 معتبر نیستند."
_PAT_NEG_3_TEXT = "شماره نامه: 54321 به دلیل عدم تطابق پیشوند متنی نباید استخراج شود."


_RAW_CORPUS_CASES: list[SyntheticDetectionCase] = [
    # -------------------------------------------------------------------------
    # SUITE: default -> IR_NATIONAL_ID (Positive)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_01_nid_ascii_standard",
        suite="default",
        category="national_id_positive",
        description="Standard 10-digit ASCII Iranian National ID in Persian sentence.",
        text=_NID_POS_1_TEXT,
        gold_spans=[_span_for(_NID_POS_1_TEXT, "0012345679", "IR_NATIONAL_ID")],
    ),
    _build_case(
        id="syn_det_02_nid_ascii_prefixed",
        suite="default",
        category="national_id_positive",
        description="ASCII National ID following a colon prefix.",
        text=_NID_POS_2_TEXT,
        gold_spans=[_span_for(_NID_POS_2_TEXT, "0490784526", "IR_NATIONAL_ID")],
    ),
    _build_case(
        id="syn_det_03_nid_persian_digits",
        suite="default",
        category="national_id_positive",
        description="Valid National ID represented in Persian Unicode digits.",
        text=_NID_POS_3_TEXT,
        gold_spans=[_span_for(_NID_POS_3_TEXT, "۷۷۳۱۶۸۹۹۵۶", "IR_NATIONAL_ID")],
    ),
    _build_case(
        id="syn_det_04_nid_persian_leading_zeros",
        suite="default",
        category="national_id_positive",
        description="Persian digit National ID with leading zeros.",
        text=_NID_POS_4_TEXT,
        gold_spans=[_span_for(_NID_POS_4_TEXT, "۰۰۸۰۰۰۰۰۰۲", "IR_NATIONAL_ID")],
    ),
    _build_case(
        id="syn_det_05_nid_persian_sequential",
        suite="default",
        category="national_id_positive",
        description="Persian digit National ID with ascending sequence.",
        text=_NID_POS_5_TEXT,
        gold_spans=[_span_for(_NID_POS_5_TEXT, "۱۲۳۴۵۶۷۸۹۱", "IR_NATIONAL_ID")],
    ),
    _build_case(
        id="syn_det_06_nid_arabic_indic_digits",
        suite="default",
        category="national_id_positive",
        description="Multiple valid National IDs written with Arabic-Indic digits.",
        text=_NID_POS_6_TEXT,
        gold_spans=[
            _span_for(_NID_POS_6_TEXT, "٠٠١٢٣٤٥٦٧٩", "IR_NATIONAL_ID", occurrence=1),
            _span_for(_NID_POS_6_TEXT, "٠٤٩٠٧٨٤٥٢٦", "IR_NATIONAL_ID", occurrence=1),
        ],
    ),
    # -------------------------------------------------------------------------
    # SUITE: default -> IR_NATIONAL_ID (Negative)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_07_nid_checksum_invalid",
        suite="default",
        category="national_id_negative",
        description="Negative control: invalid modulo-11 check digit.",
        text=_NID_NEG_1_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_08_nid_repeated_digits",
        suite="default",
        category="national_id_negative",
        description="Negative control: 10-digit repeated identical numbers.",
        text=_NID_NEG_2_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_09_nid_invalid_length",
        suite="default",
        category="national_id_negative",
        description="Negative control: 9-digit and 11-digit numbers.",
        text=_NID_NEG_3_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_10_nid_ordinary_numbers",
        suite="default",
        category="national_id_negative",
        description="Negative control: ordinary 6-digit Persian numbers in prose.",
        text=_NID_NEG_4_TEXT,
        gold_spans=[],
    ),
    # -------------------------------------------------------------------------
    # SUITE: default -> IR_MOBILE (Positive)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_11_mob_mci_0912",
        suite="default",
        category="mobile_positive",
        description="MCI 0912 domestic mobile number.",
        text=_MCI_POS_1_TEXT,
        gold_spans=[_span_for(_MCI_POS_1_TEXT, "09121234567", "IR_MOBILE")],
    ),
    _build_case(
        id="syn_det_12_mob_mtn_0935",
        suite="default",
        category="mobile_positive",
        description="MTN Irancell 0935 domestic mobile number.",
        text=_MTN_POS_1_TEXT,
        gold_spans=[_span_for(_MTN_POS_1_TEXT, "09351234567", "IR_MOBILE")],
    ),
    _build_case(
        id="syn_det_13_mob_rightel_0921",
        suite="default",
        category="mobile_positive",
        description="RighTel 0921 domestic mobile number.",
        text=_RTL_POS_1_TEXT,
        gold_spans=[_span_for(_RTL_POS_1_TEXT, "09211234567", "IR_MOBILE")],
    ),
    _build_case(
        id="syn_det_14_mob_multiple_prefixes",
        suite="default",
        category="mobile_positive",
        description="Multiple mobile numbers from 0902 and 0990 prefix families.",
        text=_MOB_POS_4_TEXT,
        gold_spans=[
            _span_for(_MOB_POS_4_TEXT, "09021234567", "IR_MOBILE", occurrence=1),
            _span_for(_MOB_POS_4_TEXT, "09901234567", "IR_MOBILE", occurrence=1),
        ],
    ),
    _build_case(
        id="syn_det_15_mob_shatel_0998",
        suite="default",
        category="mobile_positive",
        description="Shatel Mobile 0998 MVNO prefix family.",
        text=_MOB_POS_5_TEXT,
        gold_spans=[_span_for(_MOB_POS_5_TEXT, "09981123456", "IR_MOBILE")],
    ),
    _build_case(
        id="syn_det_16_mob_mci_0991",
        suite="default",
        category="mobile_positive",
        description="MCI 0991 mobile prefix family.",
        text=_MOB_POS_6_TEXT,
        gold_spans=[_span_for(_MOB_POS_6_TEXT, "09911234567", "IR_MOBILE")],
    ),
    # -------------------------------------------------------------------------
    # SUITE: default -> IR_MOBILE (Script Variants)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_17_mob_persian_digits_mci",
        suite="default",
        category="mobile_script_variant",
        description="Persian digit representation of 0912 mobile number.",
        text=_MOB_VAR_1_TEXT,
        gold_spans=[_span_for(_MOB_VAR_1_TEXT, "۰۹۱۲۱۲۳۴۵۶۷", "IR_MOBILE")],
    ),
    _build_case(
        id="syn_det_18_mob_persian_digits_mtn",
        suite="default",
        category="mobile_script_variant",
        description="Persian digit representation of 0935 mobile number.",
        text=_MOB_VAR_2_TEXT,
        gold_spans=[_span_for(_MOB_VAR_2_TEXT, "۰۹۳۵۱۲۳۴۵۶۷", "IR_MOBILE")],
    ),
    _build_case(
        id="syn_det_19_mob_arabic_indic_digits",
        suite="default",
        category="mobile_script_variant",
        description="Arabic-Indic digit representation of mobile numbers.",
        text=_MOB_VAR_3_TEXT,
        gold_spans=[
            _span_for(_MOB_VAR_3_TEXT, "٠٩١٢١٢٣٤٥٦٧", "IR_MOBILE", occurrence=1),
            _span_for(_MOB_VAR_3_TEXT, "٠٩٢١١٢٣٤٥٦٧", "IR_MOBILE", occurrence=1),
        ],
    ),
    # -------------------------------------------------------------------------
    # SUITE: default -> IR_MOBILE (Negative)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_20_mob_unsupported_prefix",
        suite="default",
        category="mobile_negative",
        description="Negative control: unallocated CRA prefix 0950.",
        text=_MOB_NEG_1_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_21_mob_malformed_length",
        suite="default",
        category="mobile_negative",
        description="Negative control: 10-digit and 12-digit mobile numbers.",
        text=_MOB_NEG_2_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_22_mob_landline_number",
        suite="default",
        category="mobile_negative",
        description="Negative control: Tehran landline number with 021 area code.",
        text=_MOB_NEG_3_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_23_mob_generic_11_digits",
        suite="default",
        category="mobile_negative",
        description="Negative control: 11-digit non-09 tracking number.",
        text=_MOB_NEG_4_TEXT,
        gold_spans=[],
    ),
    # -------------------------------------------------------------------------
    # SUITE: default -> IR_IBAN (Positive)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_24_iban_ascii_standard",
        suite="default",
        category="iban_positive",
        description="Valid 26-character ASCII Iranian IBAN (Sheba).",
        text=_IBAN_POS_1_TEXT,
        gold_spans=[
            _span_for(_IBAN_POS_1_TEXT, "IR641234567890123456789012", "IR_IBAN")
        ],
    ),
    _build_case(
        id="syn_det_25_iban_ascii_second",
        suite="default",
        category="iban_positive",
        description="Valid ASCII Iranian IBAN with leading zero bank account format.",
        text=_IBAN_POS_2_TEXT,
        gold_spans=[
            _span_for(_IBAN_POS_2_TEXT, "IR220000000000000000000001", "IR_IBAN")
        ],
    ),
    _build_case(
        id="syn_det_26_iban_persian_digits_1",
        suite="default",
        category="iban_positive",
        description="Valid Iranian IBAN written with Persian Unicode digits.",
        text=_IBAN_POS_3_TEXT,
        gold_spans=[
            _span_for(_IBAN_POS_3_TEXT, "IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲", "IR_IBAN")
        ],
    ),
    _build_case(
        id="syn_det_27_iban_persian_digits_2",
        suite="default",
        category="iban_positive",
        description="Second valid Persian digit Iranian IBAN vector.",
        text=_IBAN_POS_4_TEXT,
        gold_spans=[
            _span_for(_IBAN_POS_4_TEXT, "IR۲۲۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۰۱", "IR_IBAN")
        ],
    ),
    _build_case(
        id="syn_det_28_iban_arabic_indic_digits",
        suite="default",
        category="iban_positive",
        description="Valid Iranian IBAN with Arabic-Indic digit glyphs.",
        text=_IBAN_POS_5_TEXT,
        gold_spans=[
            _span_for(_IBAN_POS_5_TEXT, "IR٦٤١٢٣٤٥٦٧٨٩٠١٢٣٤٥٦٧٨٩٠١٢", "IR_IBAN")
        ],
    ),
    # -------------------------------------------------------------------------
    # SUITE: default -> IR_IBAN (Negative)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_29_iban_checksum_invalid",
        suite="default",
        category="iban_negative",
        description="Negative control: 26-char IR IBAN failing MOD-97 checksum.",
        text=_IBAN_NEG_1_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_30_iban_foreign_country_code",
        suite="default",
        category="iban_negative",
        description="Negative control: German IBAN ignored by Iranian detector.",
        text=_IBAN_NEG_2_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_31_iban_invalid_length",
        suite="default",
        category="iban_negative",
        description="Negative control: 25-character truncated IBAN sequence.",
        text=_IBAN_NEG_3_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_32_iban_alphanumeric_account",
        suite="default",
        category="iban_negative",
        description="Negative control: IBAN containing letter in BBAN portion.",
        text=_IBAN_NEG_4_TEXT,
        gold_spans=[],
    ),
    # -------------------------------------------------------------------------
    # SUITE: default -> Mixed Multi-Identifier Documents
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_33_mixed_nid_mob_iban_ascii",
        suite="default",
        category="mixed_default",
        description="Document containing National ID, Mobile, and IBAN in ASCII.",
        text=_MIXED_DEF_1_TEXT,
        gold_spans=[
            _span_for(_MIXED_DEF_1_TEXT, "0012345679", "IR_NATIONAL_ID"),
            _span_for(_MIXED_DEF_1_TEXT, "09121234567", "IR_MOBILE"),
            _span_for(_MIXED_DEF_1_TEXT, "IR641234567890123456789012", "IR_IBAN"),
        ],
    ),
    _build_case(
        id="syn_det_34_mixed_nid_mob_iban_persian",
        suite="default",
        category="mixed_default",
        description="Document with National ID, Mobile, and IBAN in Persian script.",
        text=_MIXED_DEF_2_TEXT,
        gold_spans=[
            _span_for(_MIXED_DEF_2_TEXT, "۰۰۱۲۳۴۵۶۷۹", "IR_NATIONAL_ID"),
            _span_for(_MIXED_DEF_2_TEXT, "۰۹۳۵۱۲۳۴۵۶۷", "IR_MOBILE"),
            _span_for(_MIXED_DEF_2_TEXT, "IR۶۴۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰۱۲", "IR_IBAN"),
        ],
    ),
    _build_case(
        id="syn_det_35_mixed_repeated_mobile",
        suite="default",
        category="mixed_default",
        description="Document with repeated mobile number in separate sentences.",
        text=_MIXED_DEF_3_TEXT,
        gold_spans=[
            _span_for(_MIXED_DEF_3_TEXT, "09121234567", "IR_MOBILE", occurrence=1),
            _span_for(_MIXED_DEF_3_TEXT, "09121234567", "IR_MOBILE", occurrence=2),
        ],
    ),
    _build_case(
        id="syn_det_36_mixed_adjacent_identifiers",
        suite="default",
        category="mixed_default",
        description="Adjacent National ID and Mobile number in prose.",
        text=_MIXED_DEF_4_TEXT,
        gold_spans=[
            _span_for(_MIXED_DEF_4_TEXT, "0490784526", "IR_NATIONAL_ID"),
            _span_for(_MIXED_DEF_4_TEXT, "09211234567", "IR_MOBILE"),
        ],
    ),
    _build_case(
        id="syn_det_37_mixed_multiple_national_ids",
        suite="default",
        category="mixed_default",
        description="Multiple National IDs in ASCII and Persian scripts.",
        text=_MIXED_DEF_5_TEXT,
        gold_spans=[
            _span_for(_MIXED_DEF_5_TEXT, "0012345679", "IR_NATIONAL_ID"),
            _span_for(_MIXED_DEF_5_TEXT, "۷۷۳۱۶۸۹۹۵۶", "IR_NATIONAL_ID"),
        ],
    ),
    # -------------------------------------------------------------------------
    # SUITE: email -> EMAIL (Positive)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_38_email_simple_ascii",
        suite="email",
        category="email_positive",
        description="Standard simple ASCII mailbox email address.",
        text=_EMAIL_POS_1_TEXT,
        gold_spans=[_span_for(_EMAIL_POS_1_TEXT, "info@example.com", "EMAIL")],
    ),
    _build_case(
        id="syn_det_39_email_subdomain",
        suite="email",
        category="email_positive",
        description="Dot-separated local part and multi-level subdomain email address.",
        text=_EMAIL_POS_2_TEXT,
        gold_spans=[
            _span_for(_EMAIL_POS_2_TEXT, "support.team@sub.domain.org", "EMAIL")
        ],
    ),
    _build_case(
        id="syn_det_40_email_plus_tag_cctld",
        suite="email",
        category="email_positive",
        description="Plus-tagged email address with .co.ir ccTLD.",
        text=_EMAIL_POS_3_TEXT,
        gold_spans=[
            _span_for(_EMAIL_POS_3_TEXT, "user.name+tag@company.co.ir", "EMAIL")
        ],
    ),
    _build_case(
        id="syn_det_41_email_enclosed_quotes_parens",
        suite="email",
        category="email_positive",
        description="Email addresses enclosed in double quotes and parentheses.",
        text=_EMAIL_POS_4_TEXT,
        gold_spans=[
            _span_for(_EMAIL_POS_4_TEXT, "alice@example.com", "EMAIL", occurrence=1),
            _span_for(_EMAIL_POS_4_TEXT, "bob@example.org", "EMAIL", occurrence=1),
        ],
    ),
    _build_case(
        id="syn_det_42_email_brackets_multiple",
        suite="email",
        category="email_positive",
        description="Email enclosed in square brackets alongside standard email.",
        text=_EMAIL_POS_5_TEXT,
        gold_spans=[
            _span_for(_EMAIL_POS_5_TEXT, "help@clinic.ir", "EMAIL", occurrence=1),
            _span_for(_EMAIL_POS_5_TEXT, "contact@hospital.ir", "EMAIL", occurrence=1),
        ],
    ),
    # -------------------------------------------------------------------------
    # SUITE: email -> EMAIL (Negative)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_43_email_missing_at",
        suite="email",
        category="email_negative",
        description="Negative control: domain-like string missing @ symbol.",
        text=_EMAIL_NEG_1_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_44_email_consecutive_dots",
        suite="email",
        category="email_negative",
        description="Negative control: local part with consecutive dots.",
        text=_EMAIL_NEG_2_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_45_email_missing_tld",
        suite="email",
        category="email_negative",
        description="Negative control: email without top-level domain.",
        text=_EMAIL_NEG_3_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_46_email_persian_chars",
        suite="email",
        category="email_negative",
        description="Negative control: Persian non-ASCII username rejected.",
        text=_EMAIL_NEG_4_TEXT,
        gold_spans=[],
    ),
    # -------------------------------------------------------------------------
    # SUITE: bank_card -> BANK_CARD (Positive)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_47_card_ascii_standard",
        suite="bank_card",
        category="bank_card_positive",
        description="Valid 16-digit ASCII payment card satisfying Luhn checksum.",
        text=_CARD_POS_1_TEXT,
        gold_spans=[_span_for(_CARD_POS_1_TEXT, "1234567890123452", "BANK_CARD")],
    ),
    _build_case(
        id="syn_det_48_card_ascii_second",
        suite="bank_card",
        category="bank_card_positive",
        description="Second valid ASCII payment card test vector.",
        text=_CARD_POS_2_TEXT,
        gold_spans=[_span_for(_CARD_POS_2_TEXT, "5022291234567897", "BANK_CARD")],
    ),
    _build_case(
        id="syn_det_49_card_persian_digits",
        suite="bank_card",
        category="bank_card_positive",
        description="Valid payment card number written with Persian Unicode digits.",
        text=_CARD_POS_3_TEXT,
        gold_spans=[_span_for(_CARD_POS_3_TEXT, "۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۲", "BANK_CARD")],
    ),
    _build_case(
        id="syn_det_50_card_arabic_indic_brackets",
        suite="bank_card",
        category="bank_card_positive",
        description="Arabic-Indic digit card and bracketed ASCII card in one text.",
        text=_CARD_POS_4_TEXT,
        gold_spans=[
            _span_for(_CARD_POS_4_TEXT, "١٢٣٤٥٦٧٨٩٠١٢٣٤٥٢", "BANK_CARD", occurrence=1),
            _span_for(_CARD_POS_4_TEXT, "5022291234567897", "BANK_CARD", occurrence=1),
        ],
    ),
    # -------------------------------------------------------------------------
    # SUITE: bank_card -> BANK_CARD (Negative)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_51_card_luhn_invalid",
        suite="bank_card",
        category="bank_card_negative",
        description="Negative control: 16-digit number failing Luhn MOD-10 checksum.",
        text=_CARD_NEG_1_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_52_card_repeated_digits",
        suite="bank_card",
        category="bank_card_negative",
        description="Negative control: 16 identical digits rejected by validator.",
        text=_CARD_NEG_2_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_53_card_invalid_length",
        suite="bank_card",
        category="bank_card_negative",
        description="Negative control: 15-digit number failing 16-digit constraint.",
        text=_CARD_NEG_3_TEXT,
        gold_spans=[],
    ),
    # -------------------------------------------------------------------------
    # SUITE: pattern -> INSTITUTIONAL PATTERN (Positive)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_54_pattern_mrn_ascii",
        suite="pattern",
        category="pattern_positive",
        description="Configured institutional MRN pattern (MRN-123456).",
        text=_PAT_POS_1_TEXT,
        gold_spans=[_span_for(_PAT_POS_1_TEXT, "MRN-123456", "MRN")],
    ),
    _build_case(
        id="syn_det_55_pattern_pat_ascii",
        suite="pattern",
        category="pattern_positive",
        description="Configured institutional Patient ID pattern (PAT-987654).",
        text=_PAT_POS_2_TEXT,
        gold_spans=[_span_for(_PAT_POS_2_TEXT, "PAT-987654", "PATIENT_ID")],
    ),
    _build_case(
        id="syn_det_56_pattern_contextual_group",
        suite="pattern",
        category="pattern_positive",
        description="Contextual capture group pattern extracting 5-digit number.",
        text=_PAT_POS_3_TEXT,
        gold_spans=[_span_for(_PAT_POS_3_TEXT, "54321", "ENCOUNTER_ID")],
    ),
    _build_case(
        id="syn_det_57_pattern_multiple_rules",
        suite="pattern",
        category="pattern_positive",
        description="Document matching multiple distinct pattern rules (PAT and MRN).",
        text=_PAT_POS_4_TEXT,
        gold_spans=[
            _span_for(_PAT_POS_4_TEXT, "PAT-112233", "PATIENT_ID"),
            _span_for(_PAT_POS_4_TEXT, "MRN-654321", "MRN"),
        ],
    ),
    # -------------------------------------------------------------------------
    # SUITE: pattern -> Normalized Digit Matching
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_58_pattern_normalized_persian_digits",
        suite="pattern",
        category="pattern_normalized",
        description="Contextual capture group matching Persian digits via norm text.",
        text=_PAT_NORM_1_TEXT,
        gold_spans=[_span_for(_PAT_NORM_1_TEXT, "۵۴۳۲۱", "ENCOUNTER_ID")],
    ),
    _build_case(
        id="syn_det_59_pattern_normalized_arabic_indic_digits",
        suite="pattern",
        category="pattern_normalized",
        description="Contextual capture group matching Arabic digits via norm text.",
        text=_PAT_NORM_2_TEXT,
        gold_spans=[_span_for(_PAT_NORM_2_TEXT, "٩٨٧٦٥", "ENCOUNTER_ID")],
    ),
    # -------------------------------------------------------------------------
    # SUITE: pattern -> INSTITUTIONAL PATTERN (Negative)
    # -------------------------------------------------------------------------
    _build_case(
        id="syn_det_60_pattern_unmatched_prefix",
        suite="pattern",
        category="pattern_negative",
        description="Negative control: non-configured prefix ACC-123456.",
        text=_PAT_NEG_1_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_61_pattern_malformed_length",
        suite="pattern",
        category="pattern_negative",
        description="Negative control: 5-digit MRN-12345 and 7-digit PAT-1234567.",
        text=_PAT_NEG_2_TEXT,
        gold_spans=[],
    ),
    _build_case(
        id="syn_det_62_pattern_unmatched_context",
        suite="pattern",
        category="pattern_negative",
        description="Negative control: 5-digit number without required context.",
        text=_PAT_NEG_3_TEXT,
        gold_spans=[],
    ),
]

SYNTHETIC_DETECTION_CORPUS: tuple[SyntheticDetectionCase, ...] = (
    validate_detection_corpus(_RAW_CORPUS_CASES)
)

__all__: list[str] = [
    "SYNTHETIC_DETECTION_CORPUS",
    "SYNTHETIC_PATTERN_RULES",
    "SyntheticDetectionCase",
    "validate_detection_corpus",
]
