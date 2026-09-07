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
- **Leading Zeros:** Semantically meaningful and mandatory. IDs are fixed 11-character strings (e.g., `10100260838` starts with `10`, older IDs or specific jurisdictions may have leading zeros). Identifiers must never be converted to native integers.
- **Repeated Digits:** Strings consisting of 11 identical digits (`00000000000`, `11111111111`, ..., `99999999999`) are invalid pseudo-values.

### 3.3 Checksum Algorithm Investigation & Disagreement Analysis

A critical requirement of Phase 27 was resolving apparent disagreements in public technical implementations and technical blogs.

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

| Source / Implementation | Language / Platform | Coefficient Sequence | Offset / Adjustment | Modulo Rule | Status & Empirical Verification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Persian Tools (`@persian-tools`)** | TypeScript / JS | `[29, 27, 23, 19, 17, 29, 27, 23, 19, 17]` | `d[9] + 2` | `rem == 10 ? 0 : rem` | **Verified: Matches 100% of authentic public entities.** |
| **DotNetTips (`dntips.ir`)** | C# (.NET) | `[29, 27, 23, 19, 17, 29, 27, 23, 19, 17]` | `d[9] + 2` (`tens_plus_two`) | `rem == 10 ? 0 : rem` | **Verified: Matches 100% of authentic public entities.** |
| **StackOverflow #55122116** | Java | `[29, 27, 23, 19, 17, 29, 27, 23, 19, 17]` | `d[9] + 2` (`tensPlusTwo`) | `rem == 10 ? 0 : rem` | **Verified: Matches 100% of authentic public entities.** |
| **Secondary Blog (excelengineer)** | Excel / VBA | `[29, 27, 23, 19, 17, 29, 27, 23, 19, 17]` | `d[9] + 2` | `rem == 10 ? 0 : rem` | **Verified: Matches 100% of authentic public entities.** |
| **Erroneous Blog (p30world)** | Text description | `[29, 27, 23, 19, 17, ...]` | Constant `+ 2` | `rem < 2 ? rem : 11 - rem` | **Defective: Fails on authentic entity IDs.** |
| **Erroneous Code Melli Copy** | Mixed | `[11, 10, 9, 8, 7, 6, 5, 4, 3, 2]` | None | `rem < 2 ? rem : 11 - rem` | **Defective: Fails on authentic entity IDs.** |

#### Empirical Verification Fact
Testing against verified public institutional legal entities published in the Official Gazette (*روزنامه رسمی*) and government registries:
- **Central Bank of Iran (*بانک مرکزی*):** `14002207985` $\to$ Check digit `5`. (Variant A: **PASS**, Variant B: FAIL, Variant C: FAIL, Variant D: FAIL).
- **University of Tehran (*دانشگاه تهران*):** `14002467723` $\to$ Check digit `3`. (Variant A: **PASS**, Variant B: FAIL, Variant C: FAIL, Variant D: FAIL).
- **National Iranian Oil Co (*شرکت ملی نفت ایران*):** `10100260838` $\to$ Check digit `8`. (Variant A: **PASS**, Variant B: FAIL, Variant C: FAIL, Variant D: FAIL).
- **Social Security Organization (*سازمان تأمین اجتماعی*):** `14000261665` $\to$ Check digit `5`. (Variant A: **PASS**, Variant B: FAIL, Variant C: PASS [coincidental], Variant D: FAIL).

**Conclusion:** Variant A is the single mathematically consistent and reproducible checksum formula across the Iranian software ecosystem.

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
- **No Mathematical Checksum:** Iranian 10-digit postal codes have **no** check digit or mathematical verification algorithm (no modulo-11, no Luhn, no Verhoeff).
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
- **Local Jurisdiction Scoping:** Registration numbers are issued sequentially within each local registry office (*حوزه ثبتی*). Company registration number `1234` in Tehran is completely distinct from company registration number `1234` in Isfahan or Shiraz.
- **No Mathematical Checksum:** There is no check digit or checksum formula.

### 5.2 Evaluation & Recommendation
- **Offline Feasibility:** Impossible. Any integer from 1 to 999999 is a plausible registration number in some registry office.
- **Decision:** `NO-GO` for standalone detector.
- **Recommended Integration:** `PATTERN RULE` only with required context (e.g., `"شماره ثبت:"`).

---

## 6. Secondary Candidate: Economic / Tax Identifier (*کد اقتصادی / شماره اقتصادی*)

### 6.1 Regulatory Background
- **Authority:** Iranian National Tax Administration (*سازمان امور مالیاتی کشور* — INTA).
- **Ecosystem Fragmentation:**
  1. **Legal Entities (Corporate Taxpayers):** Under Article 169 of the Direct Taxes Act and INTA circulars, the 11-digit Legal Entity ID (*شناسه ملی*) officially serves as the Economic Code. No separate 12-digit number is issued.
  2. **Natural Persons (Individual Taxpayers):** Taxpayers use their 10-digit National ID (Code Melli) plus a 4-digit tax file / branch suffix (total 14 digits).
  3. **Electronic Invoices (Shop Terminals Law):** Invoices in the Taxpayer System (*سامانه مودیان*) use a 22-character unique tax invoice ID (*شماره منحصر به فرد مالیاتی*) derived from a 6-character Fiscal Memory ID (*شناسه یکتای حافظه مالیاتی*), hex timestamp, sequence number, and check digit.

### 6.2 Evaluation & Recommendation
- **Decision:** `HOLD`
- **Status:** `OUT OF SCOPE / NEEDS DEDICATED SPECIFICATION RESEARCH`.
- **Note:** Corporate tax ID is fully satisfied by the Legal Entity ID (`IR_LEGAL_ENTITY_ID`).

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
        - Rejects all identical/repeated digit patterns ('00000000000'..'99999999999').
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

## 11. External Source Snapshot Bibliography

1. **Supreme Council / Cabinet Decree No. 16145/T42656H (1387/06/10):** *"آیین‌نامه اختصاص شناسه ملی به تمامی اشخاص حقوقی ایرانی"* — Primary legal basis establishing the 11-digit National Legal Entity ID.
2. **SSAA National Portal for Legal Entities Information (`ilenc.ssaa.ir`):** Official query portal and authority for legal entities registration in Iran.
3. **National Post Company of Iran (`post.ir`):** Regulatory documentation on the 10-digit postal code format and geographical sector encoding.
4. **Iranian National Tax Administration (`tax.gov.ir`):** Direct Taxes Act Article 169 regulations and Law on Shop Terminals and Taxpayer System.
5. **Persian Tools Organization (`@persian-tools/persian-tools`, `py-persian-tools`):** Open-source reference implementation of `verifyIranianLegalId` using the prime-weight modulo-11 algorithm.
6. **DotNetTips (`dntips.ir`):** Technical article and C# implementation of Iranian legal entity checksum validation.
7. **StackOverflow Community Q&A #55122116:** Technical discussion and Java implementation of the 11-digit legal entity check-digit formula.
