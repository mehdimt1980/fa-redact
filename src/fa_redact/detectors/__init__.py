"""Identifier detectors for fa-redact."""

from __future__ import annotations

from fa_redact.detectors.bank_card import BankCardDetector
from fa_redact.detectors.email import EmailDetector
from fa_redact.detectors.iranian_iban import IranianIBANDetector
from fa_redact.detectors.mobile import IranianMobileNumberDetector
from fa_redact.detectors.national_id import IranianNationalIDDetector
from fa_redact.detectors.pattern import PatternDetector, PatternRule

__all__ = [
    "BankCardDetector",
    "EmailDetector",
    "IranianIBANDetector",
    "IranianMobileNumberDetector",
    "IranianNationalIDDetector",
    "PatternDetector",
    "PatternRule",
]
