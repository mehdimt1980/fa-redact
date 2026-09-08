"""fa-redact internal baseline adapters for Phase 29 research.

This module is strictly isolated to research/ and does not modify production code.
"""

from __future__ import annotations

import os
from typing import Any

from fa_redact import detect
from fa_redact.detectors import (
    BankCardDetector,
    EmailDetector,
    IranianIBANDetector,
    IranianLegalEntityIDDetector,
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
)
from fa_redact.protocols import Detector
from research.evaluation import EntitySpan


class FaRedactDeterministicAdapter:
    """fa-redact deterministic core detectors."""

    adapter_id = "fa_redact_deterministic"
    display_name = "fa-redact Deterministic Core"
    is_available = True

    def __init__(self) -> None:
        self._detectors: list[Detector] = [
            IranianNationalIDDetector(),
            IranianMobileNumberDetector(),
            IranianIBANDetector(),
            IranianLegalEntityIDDetector(),
            EmailDetector(),
            BankCardDetector(),
        ]

    def detect_spans(self, text: str) -> list[EntitySpan]:
        detections = detect(text, detectors=self._detectors)
        return [EntitySpan.from_detection(d) for d in detections]


class FaRedactCurrentNERAdapter:
    """fa-redact opt-in PersianNERDetector (PEYMA baseline)."""

    adapter_id = "fa_redact_current_ner"
    display_name = "fa-redact PersianNERDetector (PEYMA)"

    def __init__(
        self,
        model_repo: str = "HooshvareLab/bert-fa-base-uncased-ner-peyma",
        revision: str = "8b7b63371aa8f1fdad62c0f82d462a22b91b37ab",
        local_dir: str | None = None,
    ) -> None:
        self._detector: Any = None
        self.is_available = False
        self._load_error: str | None = None

        try:
            from huggingface_hub import snapshot_download

            from fa_redact.detectors.persian_ner import PersianNERDetector

            if local_dir is None:
                hf_home = os.environ.get("HF_HOME")
                if hf_home:
                    local_dir = os.path.join(
                        hf_home,
                        "models--HooshvareLab--bert-fa-base-uncased-ner-peyma",
                    )

            if local_dir and os.path.exists(local_dir):
                model_dir = snapshot_download(
                    repo_id=model_repo,
                    revision=revision,
                    local_dir=local_dir,
                    local_files_only=True,
                )
            else:
                model_dir = snapshot_download(repo_id=model_repo, revision=revision)

            self._detector = PersianNERDetector(model_path=model_dir)
            self.is_available = True
        except Exception as e:
            self._detector = None
            self.is_available = False
            self._load_error = f"{type(e).__name__}: {e}"

    def detect_spans(self, text: str) -> list[EntitySpan]:
        if not self.is_available or self._detector is None or not text:
            return []
        from fa_redact.normalization import normalize_text

        norm = normalize_text(text)
        detections = self._detector.detect(text, norm)
        return [EntitySpan.from_detection(d) for d in detections]


class FaRedactCurrentHybridAdapter:
    """fa-redact hybrid baseline: deterministic core + opt-in PersianNERDetector."""

    adapter_id = "fa_redact_current_hybrid"
    display_name = "fa-redact Current Hybrid (Deterministic + PEYMA NER)"

    def __init__(self) -> None:
        self._det_adapter = FaRedactDeterministicAdapter()
        self._ner_adapter = FaRedactCurrentNERAdapter()
        self.is_available = (
            self._det_adapter.is_available and self._ner_adapter.is_available
        )
        self._load_error: str | None = (
            self._ner_adapter._load_error
            if not self._ner_adapter.is_available
            else None
        )

    def detect_spans(self, text: str) -> list[EntitySpan]:
        spans: list[EntitySpan] = []
        spans.extend(self._det_adapter.detect_spans(text))
        if self._ner_adapter.is_available:
            try:
                spans.extend(self._ner_adapter.detect_spans(text))
            except Exception:
                # In hybrid mode, deterministic detections survive if NER fails
                pass
        # Deduplicate identical spans
        seen: set[tuple[int, int, str]] = set()
        deduped: list[EntitySpan] = []
        for sp in spans:
            key = (sp.start, sp.end, sp.type)
            if key not in seen:
                seen.add(key)
                deduped.append(sp)
        return deduped
