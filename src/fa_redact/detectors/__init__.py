"""Identifier detectors for fa-redact."""

from __future__ import annotations

from fa_redact.detectors.mobile import IranianMobileNumberDetector
from fa_redact.detectors.national_id import IranianNationalIDDetector

__all__ = ["IranianMobileNumberDetector", "IranianNationalIDDetector"]
