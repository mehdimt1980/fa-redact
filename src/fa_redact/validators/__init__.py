"""Validation functions for Iranian identifiers and email addresses."""

from __future__ import annotations

from fa_redact.validators.email import is_valid_email
from fa_redact.validators.iranian_iban import is_valid_iranian_iban
from fa_redact.validators.mobile import is_valid_mobile_number
from fa_redact.validators.national_id import is_valid_national_id

__all__ = [
    "is_valid_email",
    "is_valid_iranian_iban",
    "is_valid_mobile_number",
    "is_valid_national_id",
]
