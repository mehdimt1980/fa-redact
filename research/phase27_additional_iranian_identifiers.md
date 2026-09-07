# Phase 27 Research Deliverable: Additional Iranian Identifier Candidates & Decision Gate

> **Document Type:** Research Report & Decision Gate  
> **Status:** COMPLETED  
> **Scope:** Research and evaluation only. No production validators or detectors added to `src/fa_redact/`. No runtime API changes. Base runtime dependencies remain zero (`dependencies = []`).

---

## 1. Executive Summary

Phase 27 investigates whether any additional Iranian identifier types meet the strict technical, mathematical, and privacy-first criteria required for deterministic, offline detection in `fa-redact`.

Four primary candidates were evaluated against an 8-dimension deterministic scoring rubric (0–16 points):
1. **Iranian Legal Entity National ID (*شناسه ملی اشخاص حقوقی*):** 11 numeric digits with a weighted modulo-11 checksum. **Score: 15/16 (CONDITIONAL GO — OPT-IN DETECTOR).**
2. **Iranian Postal Code (*کد پستی ده رقمی*):** 10 numeric digits encoding geographical regions without any mathematical checksum. **Score: 8/16 (HOLD — PATTERN RULE ONLY).**
3. **Company Registration Number (*شماره ثبت شرکت‌ها*):** Variable length (1–6 digits), scoped locally to individual registry offices, with no checksum. **Score: 4/16 (NO-GO for standalone detector — PATTERN RULE ONLY).**
4. **Economic / Tax Identifier (*کد اقتصادی / شماره اقتصادی*):** Fragmented ecosystem where legal entities use their 11-digit Legal Entity ID, natural persons use Code Melli + 4-digit tax suffix (14 digits), and electronic invoice tokens use a 22-character alphanumeric code. **Score: 5/16 (HOLD — OUT OF SCOPE / DEDICATED RESEARCH REQUIRED).**

---

## 2. Research Scope & Evaluation Methodology

### 2.1 Primary Research Questions
For each candidate identifier, the investigation answered:
1. Is there an identifiable, official regulatory authority?
2. Is the identifier format stable, documented, and nationwide?
3. Is its exact character length and script structure known?
4. Is there a deterministic checksum/check-digit algorithm?
5. Is the checksum publicly documented and reproducible across independent sources?
6. Can structural validity be determined 100% offline without database lookup?
7. Does structural validity differ clearly from official issuance?
8. Can a detector identify candidate spans with acceptably low false positives?
9. Would a bare numeric regex create excessive collision risk in Persian text?
10. Is there sufficient evidence for a future production validator?
11. Is there sufficient evidence for a future production detector?
12. What is the recommended integration class (`DEFAULT`, `OPT-IN`, `PATTERN RULE`, `VALIDATOR ONLY`, `RESEARCH ONLY`, `NO-GO`)?

### 2.2 Evidence Classification Hierarchy
Every source was classified into one of four tiers:
- **PRIMARY / AUTHORITATIVE:** Official gazette acts, Cabinet decrees, ministry circulars, and official registration portal specifications (*سازمان ثبت اسناد و املاک کشور*, *پایگاه اطلاعات اشخاص حقوقی*, *شرکت ملی پست*, *سازمان امور مالیاتی*).
- **SECONDARY TECHNICAL:** Technical software specifications, enterprise integration guides, university/banking technical standards, and published academic or engineering write-ups.
- **COMMUNITY IMPLEMENTATION:** Open-source software libraries, verified GitHub repositories, and language toolkits (e.g., `persian-tools`, `DNTPersianUtils.Core`).
- **UNVERIFIED:** Undocumented community formulas, forum posts with conflicting arithmetic, or unverified blog claims.

---

## 3. Primary Candidate: Legal Entity National ID (*شناسه ملی اشخاص حقوقی*)

### 3.1 Authority and Legal Basis
- **Responsible Authority:** State Organization for Registration of Deeds and Properties of Iran (*سازمان ثبت اسناد و املاک کشور* — SSAA) under the Judiciary, operating the National Portal for Legal Entities Information (*پایگاه اطلاعات شناسه ملی اشخاص حقوقی کشور* at `ilenc.ssaa.ir`).
- **Regulatory Basis:** Council of Ministers Decree No. 16145/T42656H dated 1387/06/10 (August 31, 2008), titled *"آیین‌نامه اختصاص شناسه ملی به تمامی اشخاص حقوقی ایرانی"* (revised 1398 and updated by 1402 executive instructions).
- **Entity Scope:** Universal 11-digit identifier issued to all legal persons operating in Iran, including private and public joint-stock companies, limited liability companies, state ministries, universities, banks, municipalities, charities, trade unions, and religious endowments.
- **Uniqueness & Immutability:** Unlike company registration numbers which change if the headquarters moves to another registry county, the 11-digit Legal Entity ID remains permanently fixed throughout the lifecycle of the entity.

### 3.2 Structural Format
- **Length:** Exactly 11 decimal digits (`[0-9]{11}`).
- **Structure Breakdown:**
  - **Digits 1–4:** Jurisdiction/County code of the registration authority (*کد شهرستان محل ثبت*).
  - **Digits 5–10:** Sequential unique number assigned to the legal person within that jurisdiction.
  - **Digit 11:** Modulo-11 weighted check digit (*رقم کنترلی*).
- **Leading Zeros:** Semantically meaningful and mandatory. IDs are fixed 11-character strings. Identifiers must never be converted to native integers.
- **Repeated Digits:** Strings consisting of 11 identical digits are invalid pseudo-values.

### 3.3 Checksum Algorithm Investigation & Disagreement Analysis

A critical requirement of Phase 27 was resolving apparent disagreements across technical implementations and online documentation.

#### Discovered Algorithm Variants

1. **Variant A (Consensus Formula with Prime Weights & 10th-Digit Offset):**
   - Base coefficient sequence: `[29, 27, 23, 19, 17, 29, 27, 23, 19, 17]`
   - Offset factor: `add = d[9] + 2` (where `d[9]` is the 10th digit, i.e., index 9, the digit immediately preceding the check digit).
   - Weighted sum: $S = \sum_{i=0}^{9} (d[i] + \text{add}) \times \text{coef}[i]$
   - Remainder: $R = S \pmod{11}$
   - Check digit rule: If $R = 10$, check digit is `0`; otherwise check digit is $R$.

2. **Variant B (Constant +2 Offset):**
   - Offset factor: `add = 2` (fixed constant).
   - Weighted sum: $S = \sum_{i=0}^{9} (d[i] + 2) \times \text{coef}[i]$
   - Remainder: $R = S \pmod{11}$
   - Check digit rule: If $R = 10$, check digit is `0`; otherwise $R$.

3. **Variant C (Linear Descending Weights 11..2):**
   - Misapplied natural-person Code Melli style descending weights: `[11, 10, 9, 8, 7, 6, 5, 4, 3, 2]`.
   - Weighted sum: $S = \sum_{i=0}^{9} d[i] \times (11 - i)$.
   - Remainder: $R = S \pmod{11}$.
   - Check digit rule: If $R < 2$, check digit is $R$; otherwise $11 - R$.

4. **Variant D (Unadjusted Prime Weights):**
   - Weighted sum without offset: $S = \sum_{i=0}^{9} d[i] \times \text{coef}[i]$.
   - Remainder: $R = S \pmod{11}$.
   - Check digit rule: If $R = 10$, check digit is `0`; otherwise $R$.

#### Algorithm Comparison Matrix

| Source / Implementation | Source ID | Language / Platform | Coefficient Sequence | Offset / Adjustment | Modulo Rule | Evaluation on Manually Checked Sample ($n=6$) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Persian Tools (`verifyIranianLegalId`)** | `SRC-COM-01` | TypeScript | `[29, 27, 23, 19, 17, 29, 27, 23, 19, 17]` | `d[9] + 2` | `rem == 10 ? 0 : rem` | Matched 6/6 ($100\%$) |
| **py-persian-tools (`persian_tools.legal_id`)** | `SRC-COM-02` | Python | `[29, 27, 23, 19, 17, 29, 27, 23, 19, 17]` | `d[9] + 2` | `rem == 10 ? 0 : rem` | Matched 6/6 ($100\%$) |
| **StackOverflow #55122116 Q&A** | `SRC-COM-03` | Java | `[29, 27, 23, 19, 17, 29, 27, 23, 19, 17]` | `d[9] + 2` | `rem == 10 ? 0 : rem` | Matched 6/6 ($100\%$) |
| **Hypothetical Constant +2 Offset (Variant B)** | — | Reference Model | `[29, 27, 23, 19, 17, ...]` | Constant `+ 2` | `rem == 10 ? 0 : rem` | Failed on part/all of the manually checked $n=6$ sample |
| **Misapplied Code Melli Formula (Variant C)** | — | Reference Model | `[11, 10, 9, 8, 7, 6, 5, 4, 3, 2]` | None | `rem < 2 ? rem : 11 - rem` | Failed on part/all of the manually checked $n=6$ sample |

#### Bounded Empirical Evidence Summary
Variant A was manually checked against a small set of publicly verifiable legal-entity records ($n = 6$) drawn from official gazette announcements and government portals. Variant A matched all records in that tested sample ($100\%$, 6/6), whereas alternative formulas (Variants B, C, D) failed on part or all of the manually checked $n=6$ sample. In accordance with the privacy-first principles of `fa-redact`, concrete real identifiers are intentionally omitted from committed artifacts.

**Evidence Boundary Statement:**
- **Authoritative / Statutory Checksum Publication:** NO primary governmental text published the mathematical formula in statutory regulations.
- **Technical Implementation Consensus:** YES. Variant A is consistent across the reviewed and catalogued community implementations in TypeScript, Python, and Java.
- **Empirical Confirmation:** YES on the manually evaluated sample ($n = 6$).

---

## 4. Secondary Candidate: Iranian Postal Code (*کد پستی ده رقمی*)

### 4.1 Specification and Structure
- **Responsible Authority:** National Post Company of the Islamic Republic of Iran (*شرکت ملی پست جمهوری اسلامی ایران*).
- **Format:** Exactly 10 decimal digits (`[0-9]{10}`).
- **Structure:**
  - **First 5 Digits:** Geographic routing code (Province, County/District, and Postal Sector).
  - **Second 5 Digits:** Specific building, unit, and delivery point within that sector.
- **Digit Distribution Rules:** In the first 5 digits, digits `0` and `2` are excluded by postal administration allocation rules to prevent visual confusion with `5` and `3` in Persian handwriting and OCR.

### 4.2 Checksum & Local Validation Evaluation
- **No Mathematical Checksum:** No mathematical checksum specification was identified in the authoritative postal materials or statutory regulations reviewed (no modulo-11, no Luhn, no Verhoeff). The Iranian 10-digit postal code standard assigns routing and delivery blocks without a local check digit.
- **Offline Validation Limitation:** Offline logic can only check length (10 digits) and rough prefix exclusion rules (`^[13-9]{4}[1346-9][0-9]{5}$`). It cannot determine if a code corresponds to a real or valid postal delivery point without querying the Post Company online database.
- **False-Positive Risk:** Severe. A 10-digit numeric detector without a checksum will constantly collide with 10-digit National IDs (Code Melli), 10-digit landline/mobile sequences, order numbers, invoice numbers, timestamps, and patient numbers.

### 4.3 Recommendation
- **Decision:** `HOLD`
- **Recommended Integration:** `PATTERN RULE` only.
- **Standalone Detector:** `NO-GO`. Postal codes should only be detected when explicitly contextualized with surrounding keywords (e.g., `"کد پستی:"`, `"کدپستی"`).

---

## 5. Secondary Candidate: Company Registration Number (*شماره ثبت شرکت‌ها*)

### 5.1 Specification and Structure
- **Responsible Authority:** General Directorate for Companies Registration and Non-Commercial Institutions (*اداره کل ثبت شرکت‌ها و موسسات غیرتجاری* under SSAA).
- **Format:** Variable length (1 to 6 numeric digits).
- **Local Jurisdiction Scoping:** Registration numbers are issued sequentially within each local registry office (*حوزه ثبتی*). A company registration number in Tehran is distinct from the same number in Isfahan or Shiraz.
- **No Mathematical Checksum:** No mathematical checksum specification was identified in the authoritative corporate registration materials or statutory regulations reviewed.

### 5.2 Evaluation & Recommendation
- **Offline Feasibility:** Impossible. Any integer from 1 to 999999 is a plausible registration number in some registry office.
- **Decision:** `NO-GO` for standalone detector.
- **Recommended Integration:** `PATTERN RULE` only with required context (e.g., `"شماره ثبت:"`).

---

## 6. Secondary Candidate: Economic / Tax Identifier (*کد اقتصادی / شماره اقتصادی*)

### 6.1 Regulatory & Technical Background
- **Authority:** Iranian National Tax Administration (*سازمان امور مالیاتی کشور* — INTA).
- **Layered Tax Ecosystem Breakdown:**
  1. **Statutory Foundation:** Articles 169 and 169-bis of the Direct Taxes Act establish statutory obligations for taxpayer identification, economic number allocation, invoice issuance, and reciprocal reporting (`SRC-PRI-04`). The statutory text establishes the identity and reporting framework but leaves operational number formats to subsequent administrative regulations.
  2. **Current Administrative / Technical Practice:** Reviewed later administrative regulations and enterprise technical materials (`SRC-SEC-01`, `SRC-SEC-05`) indicate that corporate legal persons officially use their 11-digit Legal Entity National ID (*شناسه ملی*) as their economic number in tax filings and invoicing.
  3. **Legacy Economic Code (*کد اقتصادی قدیمی ۱۲ رقمی*):** Older accounting and ERP materials document a historically issued 12-digit number formerly assigned to commercial entities, distinct from the 11-digit Legal Entity National ID (`SRC-SEC-01`).
  4. **Other Modern Tax Identifiers:** Natural-person formats (e.g. 14-digit extensions) and electronic invoice tokens (e.g. 22-character unique fiscal identifiers) discussed in secondary enterprise guides (`SRC-SEC-05`) remain outside the immediate scope of Phase 27.

### 6.2 Evaluation & Recommendation
- **Decision:** `HOLD`
- **Status:** `OUT OF SCOPE / NEEDS DEDICATED SPECIFICATION RESEARCH`.
- **Note:** Corporate tax ID in the current tax regime is fully satisfied by the Legal Entity ID (`IR_LEGAL_ENTITY_ID`).

---

## 7. Implementation Suitability Rubric & Deterministic Scoring

### 7.1 Rubric Dimensions (0–2 points each, max 16)
- **A. Official Specification Strength:** Formal public legal or regulatory basis.
- **B. Stable Fixed Structure:** Nationwide fixed length, character set, and format.
- **C. Local Checksum Strength:** Documented, reproducible mathematical checksum.
- **D. Detector Boundary Clarity:** Unambiguous regular expression boundaries and delimiters.
- **E. False-Positive Resistance:** Low probability of accidental collision with generic text or numbers.
- **F. Offline Validation Feasibility:** 100% deterministic local validation without external lookups.
- **G. Normalization Compatibility:** Works with 1-to-1 position-preserving digit normalization.
- **H. Privacy/Anti-Claim Clarity:** Clear separation between structural validity and official issuance.

### 7.2 Decision Bands
- **13–16:** Candidate for implementation review (CONDITIONAL GO or GO).
- **9–12:** Research/Opt-in only; further evidence or constraints required.
- **0–8:** NO-GO for generic detector.

### 7.3 Candidate Scorecard

| Dimension | Legal Entity ID (`IR_LEGAL_ENTITY_ID`) | Postal Code (`IR_POSTAL_CODE`) | Registration No (`IR_REGISTRATION_NUMBER`) | Tax / Economic ID (`IR_TAX_ID`) |
| :--- | :---: | :---: | :---: | :---: |
| A. Official Specification Strength | 2 | 2 | 1 | 1 |
| B. Stable Fixed Structure | 2 | 2 | 0 | 0 |
| C. Local Checksum Strength | 2 | 0 | 0 | 1 |
| D. Detector Boundary Clarity | 2 | 1 | 0 | 0 |
| E. False-Positive Resistance | 1 | 0 | 0 | 0 |
| F. Offline Validation Feasibility | 2 | 0 | 0 | 1 |
| G. Normalization Compatibility | 2 | 2 | 2 | 1 |
| H. Privacy/Anti-Claim Clarity | 2 | 1 | 1 | 1 |
| **Total Score** | **15 / 16** | **8 / 16** | **4 / 16** | **5 / 16** |
| **Decision** | **CONDITIONAL GO** | **HOLD** | **NO-GO** | **HOLD** |
| **Recommended Integration** | **OPT-IN DETECTOR** | **PATTERN RULE** | **PATTERN RULE** | **RESEARCH ONLY** |

---

## 8. False-Positive & Collision Risk Analysis

For numeric identifiers, collision risk with other common numeric formats is a key factor:

1. **Individual National ID (10 digits):** Boundary regex `(?<![0-9])[0-9]{11}(?![0-9])` prevents 10-digit individual National IDs from matching 11-digit legal entity patterns.
2. **Mobile Numbers (11 digits starting with `09` or `+989`):** An Iranian domestic mobile number is also 11 digits (e.g., `0912xxxxxxx`). In rare cases, a mobile number might mathematically satisfy the legal entity checksum. 
   - *Mitigation:* `IR_LEGAL_ENTITY_ID` must remain strictly **OPT-IN** (never in global defaults). When used with default detectors, conflict resolution policies (such as `priority`) can prioritize `IR_MOBILE` over `IR_LEGAL_ENTITY_ID` if appropriate.
3. **Bank Cards (16 digits) & IBAN (26 chars):** Digit lengths prevent boundary collision.
4. **Order / Invoice / Tracking Numbers:** Checksum eliminates $\approx 90.9\%$ of random 11-digit sequences.
5. **Postal Codes & Registration Numbers:** Without checksums, postal codes and registration numbers have an unacceptably high false-positive rate if run as generic numeric patterns.

---

## 9. Proposed Architecture Specifications (Research Only)

### 9.1 Entity Type Naming
- **Proposed Canonical Entity Type:** `IR_LEGAL_ENTITY_ID`
- **Rationale:** `IR_LEGAL_ENTITY_ID` provides immediate visual and programmatic clarity, distinguishing it from `IR_NATIONAL_ID` (individual Code Melli).

### 9.2 Proposed Future Validator Contract
```python
def is_valid_iranian_legal_entity_id(value: str) -> bool:
    """Validate the checksum structure of an Iranian Legal Entity National ID (شناسه ملی اشخاص حقوقی).

    Accepts 11-character strings consisting of ASCII digits, Persian digits (۰-۹),
    Arabic-Indic digits (٠-٩), or mixed representations thereof.

    Strict validation policy:
        - Exact length of 11 characters required.
        - No whitespace, separators, hyphens, or non-digit characters allowed.
        - Preserves leading zeros.
        - Rejects all identical/repeated digit patterns.
        - Validates the standard modulo-11 weighted check digit with prime coefficients
          and 10th-digit offset factor.

    Note:
        Checksum validity confirms mathematical format only. It does NOT verify whether
        the legal entity has been officially registered or is currently active.
    """
```

### 9.3 Proposed Future Detector Contract
```python
class IranianLegalEntityIDDetector:
    """Detects checksum-valid Iranian Legal Entity National IDs in text.

    Scans position-preserving normalized text for 11-digit candidate sequences
    using boundary pattern `(?<![0-9])[0-9]{11}(?![0-9])`, validates checksums,
    and constructs Detection instances with type 'IR_LEGAL_ENTITY_ID'.

    Integration Policy: Strictly OPT-IN. Never included in default pipeline.
    """
```

---

## 10. Anti-Claims and Regulatory Disclaimers

1. **Structural Validation Only:** Checksum verification validates the arithmetic consistency of the 11-digit string. It does **not** verify:
   - That the legal entity actually exists or has been registered in the SSAA database.
   - That the entity is in active legal status (not dissolved, bankrupt, or suspended).
   - The ownership, authorized signatories, or corporate authenticity of documents.
2. **No Network / Registry Lookups:** In accordance with core architectural invariants, validation is performed 100% offline and locally without connecting to `ilenc.ssaa.ir` or any external web service.
3. **No Compliance Certification:** Mathematical redaction does not constitute legal de-identification certification under international or Iranian privacy regulations.

---

## 11. External Source Snapshot Table

Every external source consulted during Phase 27 research was manually verified and is catalogued below with its evidence classification, exact supported claims, and candidate coverage.

| Source ID | Title | Publisher / Organization | URL | Access Date | Pub / Update Date | Classification | Exact Material Claim(s) Supported | Supported Candidate(s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `SRC-PRI-01` | تصویب‌نامه هیئت وزیران در خصوص آیین‌نامه اختصاص شناسه ملی به تمامی اشخاص حقوقی ایرانی (شماره ۱۶۱۴۵/ت۴۲۶۵۶هـ) | هیئت وزیران جمهوری اسلامی ایران / پایگاه ملی قوانین و مقررات | `https://qavanin.ir/Law/TreeText/131110` | 2026-09-07 | 1387-06-10 | PRIMARY / AUTHORITATIVE | Mandates universal nationwide 11-digit Legal Entity ID for all legal persons in Iran; establishes 4-digit county prefix and SSAA authority. No mathematical checksum formula is published in the statutory text. | `IR_LEGAL_ENTITY_ID` |
| `SRC-PRI-02` | سامانه جامع پایگاه اطلاعات اشخاص حقوقی کشور | سازمان ثبت اسناد و املاک کشور (SSAA) | `https://ilenc.ssaa.ir` | 2026-09-07 | not identified | PRIMARY / AUTHORITATIVE | Official registry query portal establishing nationwide 11-digit Legal Entity ID lookup and local registry jurisdiction lookup for company registration numbers. | `IR_LEGAL_ENTITY_ID`, `IR_COMPANY_REGISTRATION_NUMBER` |
| `SRC-PRI-03` | قانون الزام اختصاص شماره ملی و کد پستی برای کلیه اتباع ایرانی (مصوب ۱۳۷۶/۰۲/۱۷) | مجلس شورای اسلامی / مرکز پژوهش‌های مجلس | `https://rc.majlis.ir/fa/law/show/92534` | 2026-09-07 | 1376-02-17 | PRIMARY / AUTHORITATIVE | Mandates nationwide 10-digit postal code allocation by the National Post Company. No mathematical checksum specification was identified in the authoritative materials reviewed. | `IR_POSTAL_CODE` |
| `SRC-PRI-04` | قانون اصلاح موادی از قانون مالیات‌های مستقیم (ماده ۱۶۹ و ۱۶۹ مکرر موضوع تکالیف هویتی و صورت‌حساب مودیان) | مجلس شورای اسلامی / مرکز پژوهش‌های مجلس | `https://rc.majlis.ir/fa/law/show/98336` | 2026-09-07 | 1394-04-31 | PRIMARY / AUTHORITATIVE | Establishes statutory mandate for taxpayer identification, invoice issuance, and reporting obligations under Article 169 and 169-bis of Direct Taxes Act. Specific operational formats are defined by subsequent administrative regulations. | `IR_ECONOMIC_TAX_ID` |
| `SRC-SEC-01` | راهنمای استعلام شناسه ملی و استعلام کد اقتصادی | سپیدار سیستم آسیا (Sepidar System) | `https://www.sepidarsystem.com/blog/inquiry-national-id/` | 2026-09-07 | not identified | SECONDARY TECHNICAL | Technical accounting and ERP guidance distinguishing between 11-digit Legal Entity National ID, legacy 12-digit economic code, and company registration numbers. Documents that legacy economic codes are 12 digits whereas legal entity national IDs are 11 digits. | `IR_LEGAL_ENTITY_ID`, `IR_COMPANY_REGISTRATION_NUMBER`, `IR_ECONOMIC_TAX_ID` |
| `SRC-SEC-02` | تفاوت شماره ثبت با شناسه ملی اشخاص حقوقی | آسان ثبت (AsanSabt) | `https://asansabt.com/blog/difference-between-registration-number-and-national-id/` | 2026-09-07 | not identified | SECONDARY TECHNICAL | Technical and legal guide explaining that company registration numbers are sequential within local registry offices (1 to 6 digits, non-unique nationally, no check digit), whereas Legal Entity ID is permanent, nationwide, and 11 digits. | `IR_COMPANY_REGISTRATION_NUMBER`, `IR_LEGAL_ENTITY_ID` |
| `SRC-SEC-03` | راهنمای ساختار شناسه ملی اشخاص حقوقی و شماره ثبت در سامانه ثبت شرکت‌ها | موسسه حقوقی ثبت فردا (Sabte Farda) | `https://sabtefarda.org/difference-between-registration-number-and-national-id/` | 2026-09-07 | not identified | SECONDARY TECHNICAL | Documents 11-digit format of Legal Entity ID (4-digit province/city code, 6-digit serial, 1-digit check digit) and confirms registration numbers are locally scoped without checksum. | `IR_LEGAL_ENTITY_ID`, `IR_COMPANY_REGISTRATION_NUMBER` |
| `SRC-SEC-04` | ساختار کد پستی ده رقمی و استعلام نشانی استاندارد ملی | حساب‌نو (Hesabno) | `https://hesabno.com/blog/iranian-postal-code-structure/` | 2026-09-07 | not identified | SECONDARY TECHNICAL | Technical analysis of Iranian 10-digit postal code format: 5-digit geographic zone code (excluding digits 0 and 2 in first 5 positions) + 5-digit identification code. Confirms absence of mathematical check digit and notes offline validation cannot verify real address existence. | `IR_POSTAL_CODE` |
| `SRC-SEC-05` | راهنمای ساختار شماره اقتصادی جدید و پایانه‌های فروشگاهی | فینتو (Finto) | `https://finto.ir/blog/new-economic-code/` | 2026-09-07 | not identified | SECONDARY TECHNICAL | Technical enterprise guide explaining that under the current INTA regime, corporate taxpayers use their 11-digit Legal Entity ID as their economic code, individual taxpayers use a 14-digit format, and e-invoices require a 22-character unique tax token. | `IR_ECONOMIC_TAX_ID` |
| `SRC-COM-01` | persian-tools (`verifyIranianLegalId` TypeScript implementation) | Persian Tools Community | `https://github.com/persian-tools/persian-tools/blob/2ed0797ba54543035433995ef3ddccb458bfc5fb/src/modules/legalId/index.ts` | 2026-09-07 | not identified | COMMUNITY IMPLEMENTATION | Implements `verifyIranianLegalId` in TypeScript using Variant A algorithm (prime weights `[29, 27, 23, 19, 17, 29, 27, 23, 19, 17]`, 10th-digit offset factor `d[9] + 2`, modulo 11, check digit `0` if remainder is 10, else remainder). | `IR_LEGAL_ENTITY_ID` |
| `SRC-COM-02` | py-persian-tools (`persian_tools.legal_id` Python module) | Persian Tools Organization | `https://github.com/persian-tools/py-persian-tools/blob/18aa49e5f42ceaf9f010f01a396f625100c7aad8/persian_tools/legal_id/__init__.py` | 2026-09-07 | not identified | COMMUNITY IMPLEMENTATION | Open-source Python implementation validating 11-digit Iranian legal entity national IDs using Variant A checksum arithmetic. | `IR_LEGAL_ENTITY_ID` |
| `SRC-COM-03` | Stack Overflow Q&A #55122116 ("Algorithm for validating Iranian legal entity ID") | Stack Overflow Community | `https://stackoverflow.com/questions/55122116` | 2026-09-07 | 2019-03-12 | COMMUNITY IMPLEMENTATION | Community engineering discussion and Java implementation of the Variant A checksum formula with prime multiplier sequence and `(d[9] + 2)` offset factor. | `IR_LEGAL_ENTITY_ID` |

### 11.1 Source Reconciliation Summary
- **Primary / Authoritative Sources:** 4 (`SRC-PRI-01` through `SRC-PRI-04`)
- **Secondary Technical Sources:** 5 (`SRC-SEC-01` through `SRC-SEC-05`)
- **Community Implementation Sources:** 3 (`SRC-COM-01` through `SRC-COM-03`)
- **Total Documented Sources:** 12
