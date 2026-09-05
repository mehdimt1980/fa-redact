"""fa-redact: Privacy-first Persian/Iranian PII redaction and pseudonymization toolkit.

This package is currently in early development.
"""

from fa_redact.detectors import (
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
)
from fa_redact.models import Detection
from fa_redact.normalization import (
    normalize_digits,
    normalize_letters,
    normalize_text,
)
from fa_redact.validators import is_valid_mobile_number, is_valid_national_id

__version__: str = "0.1.0"
__all__: list[str] = [
    "__version__",
    "Detection",
    "IranianMobileNumberDetector",
    "IranianNationalIDDetector",
    "is_valid_mobile_number",
    "is_valid_national_id",
    "normalize_digits",
    "normalize_letters",
    "normalize_text",
]
