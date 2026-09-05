# Security and Privacy Policy

`fa-redact` is dedicated to enabling privacy-preserving processing of Persian text. We take security and data privacy reports seriously and welcome responsible disclosure.

---

## Reporting a Security or Privacy Vulnerability

If you discover a security vulnerability, a flaw in privacy safeguards, or a risk of sensitive data leakage in `fa-redact`:

1. **Do NOT open a public GitHub issue** with sensitive vulnerability details, exploit demonstrations, or any real Personally Identifiable Information (PII).
2. **Use GitHub Private Vulnerability Reporting**: Navigate to the repository's **Security** tab, click **Advisories**, and choose **Report a vulnerability** to submit a private report to maintainers.
3. If private vulnerability reporting is unavailable, please communicate privately through official GitHub repository mechanisms. Do not post sensitive exploit details or real PII publicly.

When reporting, please include:
- A clear description of the vulnerability or privacy defect.
- Steps to reproduce using **purely synthetic or algorithmic test data**. Never include real patient records or personal identifiers.
- Potential impact on privacy, detection accuracy, or pseudonymization integrity.

We will review reports promptly and collaborate on a remediation plan.

---

## Privacy-Safe Reporting Rule

> [!CAUTION]
> **Never include real patient data, personal PII, production credentials, or secrets in bug reports or vulnerability disclosures.**
>
> Always use synthetic placeholders, algorithmic test vectors, or anonymized dummy text.

---

## Early-Stage Software Notice & Compliance Scope

- **Early-Stage Development**: `fa-redact` is experimental software under active development.
- **No Inherent Regulatory or Legal Compliance**: Use of `fa-redact` does not inherently guarantee compliance with data privacy regulations (such as HIPAA, GDPR, or local healthcare privacy statutes). Organizations and developers are responsible for independently verifying that their complete data architectures satisfy applicable legal and privacy standards.
- **Verification Scope**: Detectors and validators confirm structural patterns (such as modulo-11 checksums or official CRA numbering plan prefixes); they do not interface with government registries or authenticate identity issuance.
