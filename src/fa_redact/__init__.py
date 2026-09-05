"""fa-redact: Privacy-first Persian/Iranian PII redaction and pseudonymization toolkit.

This package is currently in early development (Phase 1).
"""

from fa_redact.models import Detection
from fa_redact.normalization import (
    normalize_digits,
    normalize_letters,
    normalize_text,
)

__version__: str = "0.1.0"
__all__: list[str] = [
    "__version__",
    "Detection",
    "normalize_digits",
    "normalize_letters",
    "normalize_text",
]
