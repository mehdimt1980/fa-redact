"""fa-redact: Privacy-first Persian/Iranian PII redaction and pseudonymization toolkit.

This package is currently in early development.
"""

from fa_redact.batch import (
    detect_many,
    redact_many,
    report_many,
)
from fa_redact.clinical import (
    ClinicalRedactionProfile,
    ClinicalTextTemplate,
    clinical_profile,
)
from fa_redact.conflicts import (
    ConflictPolicy,
    resolve_detection_conflicts,
)
from fa_redact.detectors import (
    BankCardDetector,
    EmailDetector,
    IranianIBANDetector,
    IranianLegalEntityIDDetector,
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
    ONNXPersianNERDetector,
    PatternDetector,
    PatternRule,
    PersianNERDetector,
)
from fa_redact.models import Detection
from fa_redact.normalization import (
    normalize_digits,
    normalize_letters,
    normalize_text,
)
from fa_redact.pipeline import detect
from fa_redact.protocols import Detector
from fa_redact.pseudonymization import PseudonymizationSession
from fa_redact.redaction import redact
from fa_redact.reporting import (
    DetectionReport,
    detection_report,
    report_detections,
)
from fa_redact.serialization import (
    detection_to_dict,
    detections_to_list,
    dumps_detections,
    dumps_report,
    dumps_reports,
    report_to_dict,
    reports_to_dict,
)
from fa_redact.structured import (
    detect_fields,
    redact_fields,
    report_fields,
)
from fa_redact.validators import (
    is_valid_bank_card_number,
    is_valid_email,
    is_valid_iranian_iban,
    is_valid_iranian_legal_entity_id,
    is_valid_mobile_number,
    is_valid_national_id,
)

__version__: str = "0.3.0"
__all__: list[str] = [
    "__version__",
    "BankCardDetector",
    "ClinicalRedactionProfile",
    "ClinicalTextTemplate",
    "ConflictPolicy",
    "Detection",
    "DetectionReport",
    "Detector",
    "EmailDetector",
    "IranianIBANDetector",
    "IranianLegalEntityIDDetector",
    "IranianMobileNumberDetector",
    "IranianNationalIDDetector",
    "ONNXPersianNERDetector",
    "PatternDetector",
    "PatternRule",
    "PersianNERDetector",
    "PseudonymizationSession",
    "clinical_profile",
    "detect",
    "detect_fields",
    "detect_many",
    "detection_report",
    "detection_to_dict",
    "detections_to_list",
    "dumps_detections",
    "dumps_report",
    "dumps_reports",
    "is_valid_bank_card_number",
    "is_valid_email",
    "is_valid_iranian_iban",
    "is_valid_iranian_legal_entity_id",
    "is_valid_mobile_number",
    "is_valid_national_id",
    "normalize_digits",
    "normalize_letters",
    "normalize_text",
    "redact",
    "redact_fields",
    "redact_many",
    "report_detections",
    "report_fields",
    "report_many",
    "report_to_dict",
    "reports_to_dict",
    "resolve_detection_conflicts",
]
