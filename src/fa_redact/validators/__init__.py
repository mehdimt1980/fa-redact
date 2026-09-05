"""Validation functions for Iranian identifiers."""

from __future__ import annotations

from fa_redact.validators.mobile import is_valid_mobile_number
from fa_redact.validators.national_id import is_valid_national_id

__all__ = ["is_valid_mobile_number", "is_valid_national_id"]
