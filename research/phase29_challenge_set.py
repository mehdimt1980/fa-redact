"""Deterministic synthetic challenge sets for Phase 29 Persian PII benchmark.

===============================================================================
DISCLAIMER & PRIVACY NOTICE:
ALL SAMPLES GENERATED IN THIS MODULE ARE 100% SYNTHETIC AND ARTIFICIALLY
CONSTRUCTED FOR OFFLINE RESEARCH AND BENCHMARKING. NO REAL PATIENT RECORDS,
HOSPITAL DATA, CUSTOMER RECORDS, OR ACTUAL PERSONAL IDENTIFIERS WERE USED.
ALL IDENTIFIERS ARE ARTIFICIALLY GENERATED VIA CHECKSUM ALGORITHMS AND
CONSTRUCTED FROM SYNTHETIC TEMPLATES.
===============================================================================
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from research.evaluation import EntitySpan

OPENMED_TO_CANONICAL: dict[str, str] = {
    # Direct identifiers
    "GIVENNAME": "PERSON",
    "SURNAME": "PERSON",
    "TELEPHONENUM": "IR_MOBILE",
    "CREDITCARDNUMBER": "BANK_CARD",
    "IDCARDNUM": "IR_NATIONAL_ID",
    "EMAIL": "EMAIL",
    "DATE": "DATE",
    "TIME": "TIME",
    "TITLE": "TITLE",
    "ORGANIZATION": "ORGANIZATION",
    "HOSPITAL": "ORGANIZATION",
    # Address components
    "CITY": "ADDRESS",
    "STATE": "ADDRESS",
    "COUNTRY": "ADDRESS",
    "STREET": "ADDRESS",
    "BUILDINGNUM": "ADDRESS",
    "ZIPCODE": "ADDRESS",
    # Medical identifiers
    "MEDICALRECORDNUM": "MEDICAL_RECORD_NO",
    "USERNAME": "ACCOUNT_ID",
}


def canonicalize_gold_spans(
    text: str,
    raw_spans: Sequence[EntitySpan | dict[str, Any]],
) -> list[EntitySpan]:
    """Deterministically map raw gold spans to canonical taxonomy
    and merge adjacent same-type spans.
    """
    mapped: list[tuple[str, int, int]] = []
    for item in raw_spans:
        if isinstance(item, EntitySpan):
            lbl = OPENMED_TO_CANONICAL.get(item.type, item.type)
            s = item.start
            e = item.end
        else:
            lbl = OPENMED_TO_CANONICAL.get(item["label"], item["label"])
            s = int(item["start"])
            e = int(item["end"])

        if 0 <= s < e <= len(text):
            mapped.append((lbl, s, e))

    mapped.sort(key=lambda x: (x[1], x[2]))

    # Merge adjacent same-label spans (e.g. GIVENNAME + SURNAME -> PERSON)
    merged: list[tuple[str, int, int]] = []
    for sp in mapped:
        if not merged:
            merged.append(sp)
            continue
        last_type, last_start, last_end = merged[-1]
        cur_type, cur_start, cur_end = sp

        if cur_type == last_type and cur_start <= last_end + 1:
            merged[-1] = (last_type, last_start, max(last_end, cur_end))
        elif cur_start >= last_end:
            merged.append(sp)

    return [EntitySpan(start=s, end=e, type=t) for t, s, e in merged]


@dataclass(frozen=True, slots=True)
class ChallengeDocument:
    """An immutable synthetic challenge document with exact gold spans."""

    doc_id: str
    dataset: str
    category: str
    description: str
    text: str
    gold_spans: tuple[EntitySpan, ...]

    def __post_init__(self) -> None:
        """Validate bounds and span integrity."""
        if not self.doc_id.strip():
            raise ValueError("doc_id cannot be empty")
        if not isinstance(self.text, str):
            raise TypeError("text must be str")
        text_len = len(self.text)
        seen: set[tuple[int, int, str]] = set()
        for span in self.gold_spans:
            if not (0 <= span.start < span.end <= text_len):
                raise ValueError(
                    f"Doc {self.doc_id}: invalid span [{span.start}:{span.end}] "
                    f"for text length {text_len}"
                )
            key = (span.start, span.end, span.type)
            if key in seen:
                raise ValueError(f"Doc {self.doc_id}: duplicate span {key}")
            seen.add(key)


def _span_for(
    full_text: str,
    target: str,
    entity_type: str,
    occurrence: int = 1,
) -> EntitySpan:
    """Find the exact (start, end) character offset of target in full_text."""
    pos = -1
    for _ in range(occurrence):
        pos = full_text.find(target, pos + 1)
        if pos == -1:
            raise ValueError(
                f"Target {target!r} (occurrence {occurrence}) not found in "
                f"text: {full_text!r}"
            )
    return EntitySpan(start=pos, end=pos + len(target), type=entity_type)


def _generate_valid_national_id(seed_idx: int) -> str:
    """Deterministically generate a 10-digit modulo-11 valid Iranian National ID."""
    p = f"{(seed_idx * 17 + 101234567) % 900000000 + 100000000:09d}"
    s = sum(int(p[i]) * (10 - i) for i in range(9))
    r = s % 11
    check = r if r < 2 else 11 - r
    return p + str(check)


def _generate_valid_iban(seed_idx: int) -> str:
    """Deterministically generate a 26-char valid Iranian IBAN (IR + 24 digits)."""
    bank_code = f"{(seed_idx * 13) % 90 + 10:02d}"
    base_val = (seed_idx * 7919 + 10000000000000000000) % 90000000000000000000
    account = f"{base_val + 10000000000000000000:020d}"
    bban = bank_code + account
    numeric_val = int(bban + "182700")
    check_digits = f"{98 - (numeric_val % 97):02d}"
    return f"IR{check_digits}{bban}"


def _generate_valid_bank_card(seed_idx: int) -> str:
    """Deterministically generate a 16-digit Luhn-valid Iranian Bank Card."""
    bins = ["603799", "627412", "502229", "621986", "628023", "589210"]
    bin_str = bins[seed_idx % len(bins)]
    middle = f"{(seed_idx * 31 + 100000000) % 900000000 + 100000000:09d}"
    payload = bin_str + middle
    digits = [int(c) for c in payload]
    total = 0
    for idx, d in enumerate(digits):
        if idx % 2 == 0:
            doubled = d * 2
            total += doubled if doubled < 10 else (doubled - 9)
        else:
            total += d
    check = (10 - (total % 10)) % 10
    return payload + str(check)


def _generate_valid_legal_id(seed_idx: int) -> str:
    """Deterministically generate an 11-digit Variant A valid Legal Entity ID."""
    prefix9 = f"{(seed_idx * 23 + 101000000) % 900000000 + 100000000:09d}"
    c10 = (seed_idx * 7) % 9 + 1
    d = [int(c) for c in prefix9] + [c10]
    coefficients = (29, 27, 23, 19, 17, 29, 27, 23, 19, 17)
    add_val = d[9] + 2
    total = sum((d[i] + add_val) * coefficients[i] for i in range(10))
    remainder = total % 11
    check_digit = 0 if remainder == 10 else remainder
    return prefix9 + str(c10) + str(check_digit)


_PERSIAN_DIGIT_MAP = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_ARABIC_INDIC_DIGIT_MAP = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def to_persian_digits(s: str) -> str:
    return s.translate(_PERSIAN_DIGIT_MAP)


def to_arabic_indic_digits(s: str) -> str:
    return s.translate(_ARABIC_INDIC_DIGIT_MAP)


def build_dataset_b() -> list[ChallengeDocument]:
    """Build Dataset B: 150 deterministic out-of-distribution challenge cases."""
    docs: list[ChallengeDocument] = []

    # 1. Negative controls (no PII, general text, medical terms, non-PII numbers)
    negative_templates = [
        (
            "B_NEG_01",
            "امروز وضعیت آب و هوای مناطق کوهستانی پایدار گزارش شده است و کاهش دمای "
            "هوا تا ۵ درجه سانتی‌گراد پیش‌بینی می‌شود.",
        ),
        (
            "B_NEG_02",
            "سرعت مجاز در بزرگراه‌های درون‌شهری حداکثر ۸۰ کیلومتر بر ساعت است و "
            "رانندگان باید فاصله طولی مناسب را رعایت فرمایند.",
        ),
        (
            "B_NEG_03",
            "شاخص کل بورس اوراق بهادار تهران امروز با افزایش ۱۲۵۰۰ واحدی به رقم "
            "۲۱۵۰۰۰۰ واحد رسید.",
        ),
        (
            "B_NEG_04",
            "میزان مصرف برق در ساعات اوج بار مصرف به بیش از ۶۵ هزار مگاوات رسید که "
            "نسبت به سال گذشته رشد داشته است.",
        ),
        (
            "B_NEG_05",
            "داروی استامینوفن ۳۲۵ میلی‌گرم جهت تسکین دردهای خفیف تا متوسط کاربرد دارد "
            "و نباید بیش از دوز توصیه شده مصرف شود.",
        ),
        (
            "B_NEG_06",
            "نتایج آزمایش نشان‌دهنده هموگلوبین 14.5 گرم بر دسی‌لیتر و قند خون "
            "ناشتای 95 میلی‌گرم در دسی‌لیتر است.",
        ),
        (
            "B_NEG_07",
            "کد رهگیری پستی مرسوله شما 203849182390192384928392 است و در مرکز "
            "پردازش مکانیزه قرار دارد.",
        ),
        (
            "B_NEG_08",
            "جلسه مجمع عمومی سالیانه در تاریخ ۱۴۰۲/۰۴/۱۵ در سالن اجتماعات "
            "برگزار خواهد شد.",
        ),
        (
            "B_NEG_09",
            "تعداد کل دانشجویان پذیرفته شده در مقطع کارشناسی ارشد امسال ۱۲۵۰ نفر "
            "بوده است.",
        ),
        (
            "B_NEG_10",
            "شماره استاندارد بین‌المللی کتاب (شابک) این اثر 978-964-12-3456-7 می‌باشد.",
        ),
        (
            "B_NEG_11",
            "هزینه ثبت نام کارگاه آموزشی مبلغ ۵۰۰,۰۰۰ ریال است که از طریق درگاه "
            "پرداخت الکترونیکی واریز می‌گردد.",
        ),
        (
            "B_NEG_12",
            "فشار خون بیمار 120 روی 80 میلی‌متر جیوه و ضربان قلب 72 بار در دقیقه "
            "اندازه‌گیری شد.",
        ),
        (
            "B_NEG_13",
            "سیستم تهویه مطبوع سالن با توان برودتی 24000 BTU در حال فعالیت مداوم است.",
        ),
        (
            "B_NEG_14",
            "ابعاد بسته ارسالی ۳۰ در ۴۰ در ۱۵ سانتی‌متر و وزن خالص آن ۲.۵ "
            "کیلوگرم می‌باشد.",
        ),
        (
            "B_NEG_15",
            "کد خطای سرور 504 Gateway Timeout به دلیل عدم پاسخگویی به موقع سرویس "
            "بالا دستی رخ داده است.",
        ),
    ]

    for doc_id, text in negative_templates:
        docs.append(
            ChallengeDocument(
                doc_id=doc_id,
                dataset="dataset_b",
                category="negative_control",
                description="General text with no PII entities or non-PII numbers",
                text=text,
                gold_spans=(),
            )
        )

    # 2. Iranian National ID challenges
    for i in range(15):
        nid_raw = _generate_valid_national_id(i + 1)
        if i % 3 == 0:
            nid = nid_raw
            text = f"کد ملی متقاضی {nid} در سامانه جامع ثبت گردید."
        elif i % 3 == 1:
            nid = to_persian_digits(nid_raw)
            text = f"شماره ملی: {nid} (احراز هویت شده توسط ثبت احوال)."
        else:
            nid = to_arabic_indic_digits(nid_raw)
            text = f"کد ملی ثبت شده برای ایشان عبارت است از {nid}."

        sp = _span_for(text, nid, "IR_NATIONAL_ID")
        docs.append(
            ChallengeDocument(
                doc_id=f"B_NID_{i + 1:02d}",
                dataset="dataset_b",
                category="national_id",
                description=f"Valid national ID in script variant {i % 3}",
                text=text,
                gold_spans=(sp,),
            )
        )

    # 3. Iranian Mobile Phone challenges
    prefixes = [
        "0912",
        "0935",
        "0990",
        "0921",
        "0901",
        "0919",
        "0930",
        "0936",
        "0911",
        "0913",
        "0914",
        "0915",
        "0916",
        "0917",
        "0918",
    ]
    for i in range(15):
        pref = prefixes[i % len(prefixes)]
        mid = f"{(i * 12345 + 1000000) % 9000000 + 1000000:07d}"
        if i % 3 == 0:
            mob = f"{pref}{mid}"
            text = f"جهت هماهنگی تحویل سفارش با شماره همراه {mob} تماس بگیرید."
        elif i % 3 == 1:
            mob = to_persian_digits(f"{pref}{mid}")
            text = f"تلفن همراه متقاضی: {mob} می‌باشد."
        else:
            mob = f"+98{pref[1:]}{mid}"
            text = f"شماره همراه بین‌المللی ثبت شده {mob} است."

        sp = _span_for(text, mob, "IR_MOBILE")
        docs.append(
            ChallengeDocument(
                doc_id=f"B_MOB_{i + 1:02d}",
                dataset="dataset_b",
                category="mobile_phone",
                description=f"Valid mobile phone variant {i + 1}",
                text=text,
                gold_spans=(sp,),
            )
        )

    # 4. Iranian IBAN (Sheba) challenges
    for i in range(15):
        iban_raw = _generate_valid_iban(i + 1)
        if i % 3 == 0:
            iban = iban_raw
            text = f"شماره شبا مقصد جهت واریز سود سهام: {iban} ثبت گردید."
        elif i % 3 == 1:
            iban = to_persian_digits(iban_raw)
            text = f"شماره شبا بانکی: {iban} (بانک ملی ایران)."
        else:
            iban = iban_raw
            text = f"مبلغ به حساب شبا {iban} انتقال یافت."

        sp = _span_for(text, iban, "IR_IBAN")
        docs.append(
            ChallengeDocument(
                doc_id=f"B_IBAN_{i + 1:02d}",
                dataset="dataset_b",
                category="iban",
                description=f"Valid Iranian IBAN case {i + 1}",
                text=text,
                gold_spans=(sp,),
            )
        )

    # 5. Bank Card Number challenges
    for i in range(15):
        card_raw = _generate_valid_bank_card(i + 1)
        if i % 3 == 0:
            card = card_raw
            text = f"شماره کارت بانکی جهت عودت وجه: {card} اعلام شد."
        elif i % 3 == 1:
            card = to_persian_digits(card_raw)
            text = f"شماره کارت واریزی: {card} می‌باشد."
        else:
            card = f"{card_raw[:4]}-{card_raw[4:8]}-{card_raw[8:12]}-{card_raw[12:]}"
            text = f"کارت بانکی مبدا {card} تایید گردید."

        sp = _span_for(text, card, "BANK_CARD")
        docs.append(
            ChallengeDocument(
                doc_id=f"B_CARD_{i + 1:02d}",
                dataset="dataset_b",
                category="bank_card",
                description=f"Valid bank card case {i + 1}",
                text=text,
                gold_spans=(sp,),
            )
        )

    # 6. Legal Entity ID challenges
    for i in range(15):
        lid_raw = _generate_valid_legal_id(i + 1)
        if i % 3 == 0:
            lid = lid_raw
            text = f"شناسه ملی شرکت طرف قرارداد {lid} در روزنامه رسمی درج شد."
        elif i % 3 == 1:
            lid = to_persian_digits(lid_raw)
            text = f"شناسه ملی اشخاص حقوقی: {lid} است."
        else:
            lid = to_arabic_indic_digits(lid_raw)
            text = f"شناسه ملی شرکت عبارت است از {lid}."

        sp = _span_for(text, lid, "IR_LEGAL_ENTITY_ID")
        docs.append(
            ChallengeDocument(
                doc_id=f"B_LEGAL_{i + 1:02d}",
                dataset="dataset_b",
                category="legal_entity_id",
                description=f"Valid legal entity ID case {i + 1}",
                text=text,
                gold_spans=(sp,),
            )
        )

    # 7. Email challenges
    emails = [
        "info@company-corp.ir",
        "support@techno-pars.com",
        "ali.rezaei@university.ac.ir",
        "contact@health-portal.org",
        "billing@fin-service.net",
        "dr.kazemi@hospital.ir",
        "marketing@online-store.ir",
        "research.lab@institute.ac.ir",
        "office.manager@holding-group.com",
        "service.desk@cloud-provider.ir",
        "hr.dept@telecom-iran.com",
        "secretariat@ngo-charity.org",
        "admission@medical-center.ir",
        "legal.affairs@law-firm.ir",
        "customer.care@insurance-co.ir",
    ]
    for i, em in enumerate(emails):
        text = f"مکاتبات رسمی از طریق پست الکترونیکی {em} پیگیری خواهد شد."
        sp = _span_for(text, em, "EMAIL")
        docs.append(
            ChallengeDocument(
                doc_id=f"B_EMAIL_{i + 1:02d}",
                dataset="dataset_b",
                category="email",
                description=f"Email address case {i + 1}",
                text=text,
                gold_spans=(sp,),
            )
        )

    # 8. Persian Person Name challenges (Separating TITLE and PERSON spans)
    persons = [
        ("دکتر علیرضا کاظمی", "دکتر", "علیرضا کاظمی"),
        ("مهندس مریم حسینی", "مهندس", "مریم حسینی"),
        ("حسین موسوی", None, "حسین موسوی"),
        ("نرگس ابراهیمی", None, "نرگس ابراهیمی"),
        ("احمد رضایی", None, "احمد رضایی"),
        ("خانم فاطمه احمدی", "خانم", "فاطمه احمدی"),
        ("آقای محمدحسین کریمی", "آقای", "محمدحسین کریمی"),
        ("سارا رستمی", None, "سارا رستمی"),
        ("امیر دهقان", None, "امیر دهقان"),
        ("دکتر بهرام صادقی", "دکتر", "بهرام صادقی"),
        ("رویا شجاعی", None, "رویا شجاعی"),
        ("مهدی پورحسینی", None, "مهدی پورحسینی"),
        ("استاد غلامرضا باقری", "استاد", "غلامرضا باقری"),
        ("حاج رضا کریمی", "حاج", "رضا کریمی"),
        ("پروفسور بیژن سهرابی", "پروفسور", "بیژن سهرابی"),
    ]
    for i, (full_expr, title, pure_name) in enumerate(persons):
        text = f"گزارش نهایی توسط {full_expr} تهیه و به مدیریت سازمان ارسال شد."
        sp_list: list[EntitySpan] = []
        if title:
            sp_list.append(_span_for(text, title, "TITLE"))
        sp_list.append(_span_for(text, pure_name, "PERSON"))
        docs.append(
            ChallengeDocument(
                doc_id=f"B_PER_{i + 1:02d}",
                dataset="dataset_b",
                category="person",
                description=f"Persian person name case {i + 1}",
                text=text,
                gold_spans=tuple(sp_list),
            )
        )

    # 9. Location & Address challenges
    addresses = [
        ("تهران، خیابان آزادی، کوچه نیلوفر، پلاک ۱۲، واحد ۴", "ADDRESS"),
        ("اصفهان، میدان امام، خیابان سپه، پلاک ۴۵", "ADDRESS"),
        ("شیراز، بلوار زند، خیابان انوری، مجتمع پزشکی سینا", "ADDRESS"),
        ("مشهد، بلوار سجاد، خیابان بهار، پلاک ۷", "ADDRESS"),
        ("تبریز، خیابان امام خمینی، کوچه شهریار، ساختمان صبا", "ADDRESS"),
        ("کرج، میدان شهدا، خیابان بهشتی، پلاک ۱۱۰", "ADDRESS"),
        ("اهواز، کیانپارس، خیابان پهلوان شرقی، پلاک ۳۲", "ADDRESS"),
        ("رشت، خیابان گلسار، بلوار سمیه، پلاک ۱۸", "ADDRESS"),
        ("قم، بلوار امین، کوچه ۲۴، پلاک ۵", "ADDRESS"),
        ("کرمان، خیابان شریعتی، چهارراه سمیه، ساختمان پزشکان", "ADDRESS"),
        ("تهران", "LOCATION"),
        ("اصفهان", "LOCATION"),
        ("شیراز", "LOCATION"),
        ("مشهد", "LOCATION"),
        ("تبریز", "LOCATION"),
    ]
    for i, (addr_str, lbl) in enumerate(addresses):
        if lbl == "ADDRESS":
            text = f"نشانی پستی محل سکونت: {addr_str} ثبت شده است."
        else:
            text = f"جلسه هماهنگی منطقه‌ای در شهر {addr_str} برگزار گردید."
        sp = _span_for(text, addr_str, lbl)
        docs.append(
            ChallengeDocument(
                doc_id=f"B_LOC_{i + 1:02d}",
                dataset="dataset_b",
                category="location_address",
                description=f"Persian location/address case {i + 1}",
                text=text,
                gold_spans=(sp,),
            )
        )

    # 10. Multi-Entity complex documents
    for i in range(15):
        full_expr, title, pure_name = persons[i % len(persons)]
        nid = _generate_valid_national_id(i + 100)
        mob = f"0912{(i * 9182 + 1000000) % 9000000 + 1000000:07d}"
        em = emails[i % len(emails)]
        card = _generate_valid_bank_card(i + 100)

        text = (
            f"مشخصات قرارداد: کاربر {full_expr} با شماره ملی {nid} و تلفن همراه {mob} "
            f"با ایمیل {em} مبلغ را به شماره کارت {card} پرداخت نمود."
        )
        multi_spans: list[EntitySpan] = []
        if title:
            multi_spans.append(_span_for(text, title, "TITLE"))
        multi_spans.append(_span_for(text, pure_name, "PERSON"))
        multi_spans.append(_span_for(text, nid, "IR_NATIONAL_ID"))
        multi_spans.append(_span_for(text, mob, "IR_MOBILE"))
        multi_spans.append(_span_for(text, em, "EMAIL"))
        multi_spans.append(_span_for(text, card, "BANK_CARD"))

        docs.append(
            ChallengeDocument(
                doc_id=f"B_MULTI_{i + 1:02d}",
                dataset="dataset_b",
                category="multi_entity",
                description=f"Multi-entity document case {i + 1}",
                text=text,
                gold_spans=tuple(multi_spans),
            )
        )

    assert len(docs) == 150, f"Expected 150 Dataset B documents, got {len(docs)}"
    return docs


def build_dataset_c() -> list[ChallengeDocument]:
    """Build Dataset C: 120 deterministic clinical synthetic documents."""
    docs: list[ChallengeDocument] = []

    doc_types = [
        ("outpatient_note", "یادداشت ویزیت درمانگاه"),
        ("discharge_summary", "خلاصه پرونده ترخیص"),
        ("referral_letter", "برگه ارجاع تخصصی"),
        ("appointment_sms", "پیامک نوبت‌دهی درمانگاه"),
        ("lab_report", "گزارش جواب آزمایشگاه"),
        ("operative_schedule", "زمان‌بندی اتاق عمل"),
        ("nursing_handoff", "گزارش تحویل شیفت پرستاری"),
        ("admission_note", "برگه پذیرش بستری"),
    ]

    for type_idx, (dtype, dtitle) in enumerate(doc_types):
        for sub_idx in range(15):
            idx = type_idx * 15 + sub_idx
            doc_id = f"C_{dtype.upper()}_{sub_idx + 1:02d}"

            doctor_names = [
                "علیرضا کاظمی",
                "مریم حسینی",
                "حسین موسوی",
                "نرگس ابراهیمی",
                "احمد رضایی",
            ]
            pure_doc_name = doctor_names[sub_idx % len(doctor_names)]
            doctor_display = f"دکتر {pure_doc_name}"

            patient_names = [
                "علی مرادی",
                "فاطمه احمدی",
                "محمدحسین کریمی",
                "سارا رستمی",
                "امیر دهقان",
            ]
            patient_name = patient_names[sub_idx % len(patient_names)]

            relatives = [
                ("رضا مرادی", "رضا مرادی (پدر)"),
                ("زهرا کریمی", "زهرا کریمی (مادر)"),
                ("نیما دهقان", "نیما دهقان (برادر)"),
                ("مریم احمدی", "مریم احمدی (همسر)"),
                ("حسین رستمی", "حسین رستمی (پسر)"),
            ]
            pure_rel_name, rel_display = relatives[sub_idx % len(relatives)]

            nid = _generate_valid_national_id(idx + 500)
            mob = f"0912{(idx * 6113 + 1000000) % 9000000 + 1000000:07d}"
            card = _generate_valid_bank_card(idx + 500)
            email = f"patient_{idx + 1}@health-portal.ir"
            file_no = f"MED-{(idx * 137 + 10000) % 90000 + 10000}"
            bed_no = f"اتاق {sub_idx + 101} تخت {(sub_idx % 4) + 1}"
            vital_signs = "BP: 120/80 mmHg, PR: 75 bpm, RR: 18/min, T: 37.0 C"
            dosage = "قرص آتورواستاتین ۲۰ میلی‌گرم روزی ۱ عدد بعد از شام"

            spans: tuple[EntitySpan, ...]
            if dtype == "outpatient_note":
                text = (
                    f"مرکز درمانی تخصصی پارس | {dtitle}\n"
                    f"بیمار: {patient_name} با کدملی {nid} و تلفن {mob} "
                    f"توسط {doctor_display} ویزیت شد.\n"
                    f"علت مراجعه: درد مفاصل زانو. "
                    f"توصیه تشخیصی: رادیوگرافی و آزمایش خون.\n"
                    f"دستور دارویی: {dosage}.\n"
                    f"پرداخت هزینه با کارت {card} و شماره پرونده {file_no} ثبت شد."
                )
                sp_org = _span_for(text, "مرکز درمانی تخصصی پارس", "ORGANIZATION")
                sp_pat = _span_for(text, patient_name, "PERSON")
                sp_nid = _span_for(text, nid, "IR_NATIONAL_ID")
                sp_mob = _span_for(text, mob, "IR_MOBILE")
                sp_title = _span_for(text, "دکتر", "TITLE")
                sp_doc = _span_for(text, pure_doc_name, "PERSON")
                sp_card = _span_for(text, card, "BANK_CARD")
                spans = (sp_org, sp_pat, sp_nid, sp_mob, sp_title, sp_doc, sp_card)

            elif dtype == "discharge_summary":
                text = (
                    f"بیمارستان تخصصی سینا - {dtitle}\n"
                    f"بیمار محترم {patient_name} با شماره ملی {nid} و "
                    f"پرونده {file_no} از بخش داخلی ترخیص گردید.\n"
                    f"پزشک معالج: {doctor_display}. "
                    f"علائم حیاتی هنگام ترخیص: {vital_signs}.\n"
                    f"شماره تماس همراه بیمار: {mob}. "
                    f"تسویه حساب با کارت {card} انجام شد."
                )
                sp_org = _span_for(text, "بیمارستان تخصصی سینا", "ORGANIZATION")
                sp_pat = _span_for(text, patient_name, "PERSON")
                sp_nid = _span_for(text, nid, "IR_NATIONAL_ID")
                sp_title = _span_for(text, "دکتر", "TITLE")
                sp_doc = _span_for(text, pure_doc_name, "PERSON")
                sp_mob = _span_for(text, mob, "IR_MOBILE")
                sp_card = _span_for(text, card, "BANK_CARD")
                spans = (sp_org, sp_pat, sp_nid, sp_title, sp_doc, sp_mob, sp_card)

            elif dtype == "referral_letter":
                text = (
                    f"برگه ارجاع پزشکی | کلینیک قلب و عروق امید\n"
                    f"همکار گرامی {doctor_display}، با سلام؛\n"
                    f"بیمار {patient_name} به شماره ملی {nid} و تماس {mob} "
                    f"جهت بررسی آنژیوگرافی عروق کرونر ارجاع می‌گردد.\n"
                    f"همراه بیمار: {rel_display}. ایمیل ارتباطی: {email}."
                )
                sp_org = _span_for(text, "کلینیک قلب و عروق امید", "ORGANIZATION")
                sp_title = _span_for(text, "دکتر", "TITLE")
                sp_doc = _span_for(text, pure_doc_name, "PERSON")
                sp_pat = _span_for(text, patient_name, "PERSON")
                sp_nid = _span_for(text, nid, "IR_NATIONAL_ID")
                sp_mob = _span_for(text, mob, "IR_MOBILE")
                sp_rel = _span_for(text, pure_rel_name, "PERSON")
                sp_em = _span_for(text, email, "EMAIL")
                spans = (
                    sp_org,
                    sp_title,
                    sp_doc,
                    sp_pat,
                    sp_nid,
                    sp_mob,
                    sp_rel,
                    sp_em,
                )

            elif dtype == "appointment_sms":
                text = (
                    f"نوبت ویزیت شما در پلی‌کلینیک خاتم‌الانبیاء ثبت شد.\n"
                    f"بیمار: {patient_name} | کدملی: {nid}\n"
                    f"پزشک: {doctor_display} | تاریخ: سه‌شنبه ساعت ۱۰:۳۰ صبح.\n"
                    f"در صورت نیاز به لغو با {mob} تماس حاصل فرمایید."
                )
                sp_org = _span_for(text, "پلی‌کلینیک خاتم‌الانبیاء", "ORGANIZATION")
                sp_pat = _span_for(text, patient_name, "PERSON")
                sp_nid = _span_for(text, nid, "IR_NATIONAL_ID")
                sp_title = _span_for(text, "دکتر", "TITLE")
                sp_doc = _span_for(text, pure_doc_name, "PERSON")
                sp_mob = _span_for(text, mob, "IR_MOBILE")
                spans = (sp_org, sp_pat, sp_nid, sp_title, sp_doc, sp_mob)

            elif dtype == "lab_report":
                text = (
                    f"آزمایشگاه پاتوبیولوژی دانش - {dtitle}\n"
                    f"نام بیمار: {patient_name} | کد ملی: {nid} | پرونده: {file_no}\n"
                    f"پزشک درخواست‌کننده: {doctor_display}\n"
                    f"نتیجه آزمایش: WBC: 6500, RBC: 4.8, Plt: 220,000.\n"
                    f"ارسال پیامک جواب به شماره {mob}."
                )
                sp_org = _span_for(text, "آزمایشگاه پاتوبیولوژی دانش", "ORGANIZATION")
                sp_pat = _span_for(text, patient_name, "PERSON")
                sp_nid = _span_for(text, nid, "IR_NATIONAL_ID")
                sp_title = _span_for(text, "دکتر", "TITLE")
                sp_doc = _span_for(text, pure_doc_name, "PERSON")
                sp_mob = _span_for(text, mob, "IR_MOBILE")
                spans = (sp_org, sp_pat, sp_nid, sp_title, sp_doc, sp_mob)

            elif dtype == "operative_schedule":
                text = (
                    f"برنامه هفتگی اتاق عمل بیمارستان شریعتی | {dtitle}\n"
                    f"جراح: {doctor_display} | بیمار: {patient_name} | کد ملی: {nid}\n"
                    f"نوع عمل: لاپاروسکوپی | تاریخ: چهارشنبه ساعت ۰۸:۰۰.\n"
                    f"تلفن هماهنگی بیهوشی: {mob}. تسویه هزینه به شماره کارت {card} "
                    f"انجام گردید."
                )
                sp_org = _span_for(text, "بیمارستان شریعتی", "ORGANIZATION")
                sp_title = _span_for(text, "دکتر", "TITLE")
                sp_doc = _span_for(text, pure_doc_name, "PERSON")
                sp_pat = _span_for(text, patient_name, "PERSON")
                sp_nid = _span_for(text, nid, "IR_NATIONAL_ID")
                sp_mob = _span_for(text, mob, "IR_MOBILE")
                sp_card = _span_for(text, card, "BANK_CARD")
                spans = (sp_org, sp_title, sp_doc, sp_pat, sp_nid, sp_mob, sp_card)

            elif dtype == "nursing_handoff":
                text = (
                    f"گزارش تحویل شیفت بخش جراحی | {dtitle}\n"
                    f"بیمار {patient_name} بستری در {bed_no} تحت نظر "
                    f"{doctor_display}.\n"
                    f"شماره پرونده: {file_no}. کدملی: {nid}. وضعیت: کامل (GCS 15).\n"
                    f"علائم حیاتی: {vital_signs}. دستورات دارویی: {dosage}.\n"
                    f"شماره تماس همراه: {mob}."
                )
                sp_pat = _span_for(text, patient_name, "PERSON")
                sp_title = _span_for(text, "دکتر", "TITLE")
                sp_doc = _span_for(text, pure_doc_name, "PERSON")
                sp_nid = _span_for(text, nid, "IR_NATIONAL_ID")
                sp_mob = _span_for(text, mob, "IR_MOBILE")
                spans = (sp_pat, sp_title, sp_doc, sp_nid, sp_mob)

            else:  # admission_note
                text = (
                    f"مرکز آموزشی درمانی رازی - {dtitle}\n"
                    f"پذیرش بیمار {patient_name} با کدملی {nid} و تلفن {mob}.\n"
                    f"پزشک پذیرش‌کننده: {doctor_display}. "
                    f"آدرس محل سکونت: کرج، میدان شهدا، پلاک ۱۲.\n"
                    f"ایمیل ثبت شده: {email}. شماره حساب بیمار: {card}."
                )
                sp_org = _span_for(text, "مرکز آموزشی درمانی رازی", "ORGANIZATION")
                sp_pat = _span_for(text, patient_name, "PERSON")
                sp_nid = _span_for(text, nid, "IR_NATIONAL_ID")
                sp_mob = _span_for(text, mob, "IR_MOBILE")
                sp_title = _span_for(text, "دکتر", "TITLE")
                sp_doc = _span_for(text, pure_doc_name, "PERSON")
                sp_addr = _span_for(text, "کرج، میدان شهدا، پلاک ۱۲", "ADDRESS")
                sp_em = _span_for(text, email, "EMAIL")
                sp_card = _span_for(text, card, "BANK_CARD")
                spans = (
                    sp_org,
                    sp_pat,
                    sp_nid,
                    sp_mob,
                    sp_title,
                    sp_doc,
                    sp_addr,
                    sp_em,
                    sp_card,
                )

            docs.append(
                ChallengeDocument(
                    doc_id=doc_id,
                    dataset="dataset_c",
                    category=dtype,
                    description=f"Clinical synthetic note: {dtitle} #{sub_idx + 1}",
                    text=text,
                    gold_spans=spans,
                )
            )

    assert len(docs) == 120, f"Expected 120 Dataset C documents, got {len(docs)}"
    return docs
