"""Unit and integration tests for PersianNERDetector."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import fa_redact
from fa_redact import (
    Detection,
    PersianNERDetector,
    PseudonymizationSession,
    detect,
    redact,
    resolve_detection_conflicts,
)


class DummyConfig:
    """Mock model configuration."""

    def __init__(
        self,
        id2label: dict[Any, str] | None = None,
        max_position_embeddings: int | None = 512,
    ) -> None:
        if id2label is None:
            self.id2label = {
                0: "O",
                1: "B_PER",
                2: "I_PER",
                3: "B_ORG",
                4: "I_ORG",
            }
        else:
            self.id2label = id2label
        self.max_position_embeddings = max_position_embeddings


class DummyOutput:
    """Mock model output."""

    def __init__(self, logits: Any) -> None:
        self.logits = logits


class DummyModel:
    """Mock PyTorch token classification model."""

    def __init__(
        self,
        config: DummyConfig | None = None,
        pred_indices: list[int] | None = None,
    ) -> None:
        self.config = config or DummyConfig()
        self.pred_indices = pred_indices or []
        self.eval_called = False
        self.call_kwargs: list[dict[str, Any]] = []

    def eval(self) -> DummyModel:
        self.eval_called = True
        return self

    def __call__(self, **kwargs: Any) -> DummyOutput:
        self.call_kwargs.append(kwargs)
        # Verify offset_mapping is never passed to model forward call
        assert "offset_mapping" not in kwargs, (
            "offset_mapping must not be passed to model"
        )

        # Create dummy logits that argmax to pred_indices
        if self.pred_indices:
            num_classes = max(len(self.config.id2label), max(self.pred_indices) + 1)
            batch_logits = []
            for idx in self.pred_indices:
                row = [-100.0] * num_classes
                row[idx] = 100.0
                batch_logits.append(row)
            logits_data: Any = [batch_logits]
        else:
            # Default single O
            logits_data = [[[0.0] * len(self.config.id2label)]]

        return DummyOutput(logits=logits_data)


class DummyFastTokenizer:
    """Mock Hugging Face fast tokenizer."""

    def __init__(
        self,
        token_offsets: list[tuple[int, int]] | None = None,
        is_fast: bool = True,
        model_max_length: int = 512,
    ) -> None:
        self.token_offsets = token_offsets
        self.is_fast = is_fast
        self.model_max_length = model_max_length

    def __call__(
        self,
        text: str,
        *,
        return_offsets_mapping: bool = True,
        add_special_tokens: bool = True,
    ) -> dict[str, Any]:
        if self.token_offsets is not None:
            offsets = list(self.token_offsets)
        else:
            # Simple whitespace-based mock offsets
            offsets = [(0, 0)]  # [CLS]
            pos = 0
            words = text.split(" ")
            for w in words:
                if not w:
                    continue
                start = text.find(w, pos)
                end = start + len(w)
                offsets.append((start, end))
                pos = end
            offsets.append((0, 0))  # [SEP]

        n = len(offsets)
        return {
            "input_ids": [101] + [1000 + i for i in range(max(0, n - 2))] + [102],
            "attention_mask": [1] * n,
            "token_type_ids": [0] * n,
            "offset_mapping": offsets,
        }


# =========================================================================
# 1-3. Import & Backend Availability Tests
# =========================================================================


def test_import_fa_redact_without_ml_backend() -> None:
    """Verify fa_redact top-level imports safely without instantiating ML."""
    assert hasattr(fa_redact, "PersianNERDetector")
    assert PersianNERDetector is not None


def test_import_persian_ner_detector_lazy() -> None:
    """Verify importing PersianNERDetector does not require instant model loading."""
    from fa_redact.detectors.persian_ner import PersianNERDetector as NERCls

    assert NERCls is not None


def test_missing_extra_dependency_error(tmp_path: Path) -> None:
    """Verify clear error directing user to pip install fa-redact[ner] when missing."""
    model_dir = tmp_path / "fake_model"
    model_dir.mkdir()

    with patch.dict(sys.modules, {"torch": None, "transformers": None}):
        with pytest.raises(ImportError) as exc_info:
            PersianNERDetector(model_dir)

        err_msg = str(exc_info.value)
        assert 'pip install "fa-redact[ner]"' in err_msg


# =========================================================================
# 4-9. Path & Loading Options Tests
# =========================================================================


def test_nonexistent_local_model_path() -> None:
    """Verify nonexistent path fails loudly with FileNotFoundError."""
    nonexistent = Path("nonexistent_model_dir_12345")
    with pytest.raises(FileNotFoundError):
        PersianNERDetector(nonexistent)


def test_non_directory_model_path(tmp_path: Path) -> None:
    """Verify file path (non-directory) fails loudly with NotADirectoryError."""
    model_file = tmp_path / "model.bin"
    model_file.write_text("dummy")
    with pytest.raises(NotADirectoryError):
        PersianNERDetector(model_file)


def test_remote_repo_identifier_fails_loudly() -> None:
    """Verify Hugging Face remote repo ID is rejected as nonexistent local directory."""
    with pytest.raises(FileNotFoundError):
        PersianNERDetector("HooshvareLab/bert-fa-base-uncased-ner-peyma")


def test_local_only_loading_and_trust_remote_code_false(tmp_path: Path) -> None:
    """Verify local_files_only=True and trust_remote_code=False are enforced."""
    model_dir = tmp_path / "mock_model"
    model_dir.mkdir()

    mock_tokenizer = DummyFastTokenizer()
    mock_model = DummyModel()

    mock_transformers = MagicMock()
    mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tokenizer
    mock_transformers.AutoModelForTokenClassification.from_pretrained.return_value = (
        mock_model
    )

    with patch.dict(
        sys.modules,
        {
            "torch": MagicMock(),
            "transformers": mock_transformers,
        },
    ):
        PersianNERDetector(model_dir)

        mock_transformers.AutoTokenizer.from_pretrained.assert_called_once_with(
            str(model_dir.resolve()),
            local_files_only=True,
            trust_remote_code=False,
        )
        mock_transformers.AutoModelForTokenClassification.from_pretrained.assert_called_once_with(
            str(model_dir.resolve()),
            local_files_only=True,
            trust_remote_code=False,
        )


def test_fast_tokenizer_required(tmp_path: Path) -> None:
    """Verify is_fast=False tokenizer is rejected."""
    model_dir = tmp_path / "mock_model"
    model_dir.mkdir()

    slow_tokenizer = DummyFastTokenizer(is_fast=False)
    mock_model = DummyModel()

    mock_transformers = MagicMock()
    mock_transformers.AutoTokenizer.from_pretrained.return_value = slow_tokenizer
    mock_transformers.AutoModelForTokenClassification.from_pretrained.return_value = (
        mock_model
    )

    with patch.dict(
        sys.modules,
        {
            "torch": MagicMock(),
            "transformers": mock_transformers,
        },
    ):
        with pytest.raises(ValueError, match="fast tokenizer"):
            PersianNERDetector(model_dir)


def test_model_eval_invoked(tmp_path: Path) -> None:
    """Verify model.eval() is called during detector initialization."""
    model_dir = tmp_path / "mock_model"
    model_dir.mkdir()

    mock_tokenizer = DummyFastTokenizer()
    mock_model = DummyModel()

    mock_transformers = MagicMock()
    mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tokenizer
    mock_transformers.AutoModelForTokenClassification.from_pretrained.return_value = (
        mock_model
    )

    with patch.dict(
        sys.modules,
        {
            "torch": MagicMock(),
            "transformers": mock_transformers,
        },
    ):
        PersianNERDetector(model_dir)
        assert mock_model.eval_called is True


# =========================================================================
# 10-12, 31-32. Label Map & Capacity Validation Tests
# =========================================================================


def test_missing_b_per_label_rejected(tmp_path: Path) -> None:
    """Verify model without B-PER label is rejected loudly."""
    config = DummyConfig(id2label={0: "O", 1: "I_PER", 2: "B_ORG"})
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)

    with pytest.raises(ValueError, match="missing required B-PER"):
        PersianNERDetector._create_for_test(tokenizer, model)


def test_missing_i_per_label_rejected(tmp_path: Path) -> None:
    """Verify model without I-PER label is rejected loudly."""
    config = DummyConfig(id2label={0: "O", 1: "B_PER", 2: "B_ORG"})
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)

    with pytest.raises(ValueError, match="missing required I-PER"):
        PersianNERDetector._create_for_test(tokenizer, model)


def test_string_numeric_id2label_keys_supported() -> None:
    """Verify string numeric keys in id2label (e.g. from JSON config) work."""
    config = DummyConfig(id2label={"0": "O", "1": "B-PERSON", "2": "I-PERSON"})
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)

    detector = PersianNERDetector._create_for_test(tokenizer, model)
    assert 1 in detector._b_per_ids
    assert 2 in detector._i_per_ids


def test_invalid_max_length() -> None:
    """Verify non-positive or non-integer max_length values are rejected."""
    config = DummyConfig()
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)

    invalid_vals: list[Any] = [0, -10, "512", True, False, 3.14]
    for invalid_val in invalid_vals:
        with pytest.raises(ValueError, match="max_length"):
            PersianNERDetector._create_for_test(
                tokenizer, model, max_length=invalid_val
            )


def test_max_length_exceeding_model_capacity_rejected() -> None:
    """Verify max_length > model max_position_embeddings is rejected."""
    config = DummyConfig(max_position_embeddings=256)
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)

    with pytest.raises(ValueError, match="exceeds model positional capacity"):
        PersianNERDetector._create_for_test(tokenizer, model, max_length=512)


# =========================================================================
# 13-14. Basic Contract & Input Validation Tests
# =========================================================================


def test_empty_input_returns_empty_list() -> None:
    """Verify empty string returns empty list immediately without calling model."""
    config = DummyConfig()
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    assert detector.detect("", "") == []
    assert len(model.call_kwargs) == 0


def test_length_mismatch_rejected() -> None:
    """Verify unequal original_text and normalized_text lengths are rejected."""
    config = DummyConfig()
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    with pytest.raises(ValueError, match="length"):
        detector.detect("ali", "alii")


def test_non_string_inputs_rejected() -> None:
    """Verify non-string inputs raise TypeError."""
    config = DummyConfig()
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    with pytest.raises(TypeError):
        detector.detect(123, "123")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        detector.detect("123", None)  # type: ignore[arg-type]


# =========================================================================
# 15-20. Exact Span Reconstruction Tests
# =========================================================================


def test_single_token_person_span() -> None:
    """Verify single-token B-PER entity emits exact Detection."""
    text = "علی آمد"
    # Offsets: [CLS]=(0,0), "علی"=(0,3), "آمد"=(4,7), [SEP]=(0,0)
    offsets = [(0, 0), (0, 3), (4, 7), (0, 0)]
    # Labels: [CLS]=O, "علی"=B_PER (1), "آمد"=O (0), [SEP]=O
    pred_indices = [0, 1, 0, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    d = detections[0]
    assert d.type == "PERSON"
    assert d.start == 0
    assert d.end == 3
    assert d.value == "علی"
    assert d.normalized_value == "علی"


def test_multi_token_person_span() -> None:
    """Verify multi-token B-PER I-PER sequence produces one merged span."""
    text = "دکتر علی محمدی بیمار را معاینه کرد"
    # Offsets:
    # [CLS]=(0,0), "دکتر"=(0,4), "علی"=(5,8), "محمدی"=(9,14), "بیمار"=(15,20), ...
    offsets = [
        (0, 0),
        (0, 4),
        (5, 8),
        (9, 14),
        (15, 20),
        (21, 23),
        (24, 30),
        (31, 34),
        (0, 0),
    ]
    # "علی"=B_PER (1), "محمدی"=I_PER (2)
    pred_indices = [0, 0, 1, 2, 0, 0, 0, 0, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    d = detections[0]
    assert d.type == "PERSON"
    assert d.start == 5
    assert d.end == 14
    assert d.value == "علی محمدی"
    assert d.normalized_value == "علی محمدی"


def test_multi_subword_person_span() -> None:
    """Verify subword pieces (B-PER, I-PER, I-PER) merge into one exact span."""
    text = "احمد علیزاده"
    # Subwords for "علیزاده": "علی"=(5,8), "##زاد"=(8,11), "##ه"=(11,12)
    offsets = [(0, 0), (0, 4), (5, 8), (8, 11), (11, 12), (0, 0)]
    # "احمد"=B_PER (1), "علی"=I_PER (2), "##زاد"=I_PER (2), "##ه"=I_PER (2)
    pred_indices = [0, 1, 2, 2, 2, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    d = detections[0]
    assert d.type == "PERSON"
    assert d.start == 0
    assert d.end == 12
    assert d.value == "احمد علیزاده"
    assert d.normalized_value == "احمد علیزاده"


def test_consecutive_b_per_entities_remain_distinct() -> None:
    """Verify two consecutive B-PER labels produce two separate Detection entities."""
    text = "علی رضا"
    offsets = [(0, 0), (0, 3), (4, 7), (0, 0)]
    # Both B_PER (1)
    pred_indices = [0, 1, 1, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    detections = detector.detect(text, text)
    assert len(detections) == 2
    assert detections[0].value == "علی"
    assert detections[0].start == 0
    assert detections[0].end == 3
    assert detections[1].value == "رضا"
    assert detections[1].start == 4
    assert detections[1].end == 7


def test_leading_i_per_conservative_recovery() -> None:
    """Verify leading I-PER token without active entity starts a new entity."""
    text = "محمدی آمد"
    offsets = [(0, 0), (0, 5), (6, 9), (0, 0)]
    # Leading I_PER (2)
    pred_indices = [0, 2, 0, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    assert detections[0].value == "محمدی"
    assert detections[0].start == 0
    assert detections[0].end == 5


def test_punctuation_adjacent_person() -> None:
    """Verify exact offsets when PERSON is adjacent to punctuation."""
    text = "(سارا) و [مریم]!"
    offsets = [
        (0, 0),
        (0, 1),
        (1, 5),
        (5, 6),
        (7, 8),
        (9, 10),
        (10, 14),
        (14, 16),
        (0, 0),
    ]
    # "سارا"=B_PER (index 2), "مریم"=B_PER (index 6)
    pred_indices = [0, 0, 1, 0, 0, 0, 1, 0, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    detections = detector.detect(text, text)
    assert len(detections) == 2
    assert detections[0].value == "سارا"
    assert detections[0].start == 1
    assert detections[0].end == 5
    assert detections[1].value == "مریم"
    assert detections[1].start == 10
    assert detections[1].end == 14


# =========================================================================
# 21-27. Offset Audit & Text Representation Tests
# =========================================================================


def test_special_tokens_ignored() -> None:
    """Verify special tokens with (0, 0) offsets are ignored."""
    text = "رضا"
    offsets = [(0, 0), (0, 3), (0, 0)]
    # If [CLS] had B_PER by mistake, special token offset (0,0) must still be skipped
    pred_indices = [1, 1, 1]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    assert detections[0].start == 0
    assert detections[0].end == 3
    assert detections[0].value == "رضا"


def test_out_of_bounds_offset_rejected() -> None:
    """Verify out-of-bounds offset raises ValueError."""
    text = "رضا"
    offsets = [(0, 0), (0, 50), (0, 0)]  # End 50 > len(text) 3
    pred_indices = [0, 1, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    with pytest.raises(ValueError, match="out-of-bounds"):
        detector.detect(text, text)


def test_non_monotonic_offset_rejected() -> None:
    """Verify non-monotonic offset raises ValueError."""
    text = "رضا احمدی"
    # Offset 2 starts before offset 1 ends: (5, 9) then (2, 4)
    offsets = [(0, 0), (5, 9), (2, 4), (0, 0)]
    pred_indices = [0, 1, 1, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    with pytest.raises(ValueError, match="non-monotonic"):
        detector.detect(text, text)


def test_arabic_yeh_kaf_alignment_preservation() -> None:
    """Verify Arabic yeh/kaf are preserved in value while normalized is canonical."""
    # original has Arabic kaf '\u0643' and Arabic yeh '\u064a'
    original_text = (
        "نام: \u0643\u0627\u0638\u0645\u064a"  # "کاظمی" with Arabic kaf & yeh
    )
    # normalized has Persian kaf '\u06a9' and Persian yeh '\u06cc'
    normalized_text = "نام: \u06a9\u0627\u0638\u0645\u06cc"

    offsets = [(0, 0), (0, 4), (5, 10), (0, 0)]
    pred_indices = [0, 0, 1, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    detections = detector.detect(original_text, normalized_text)
    assert len(detections) == 1
    d = detections[0]
    assert d.value == "\u0643\u0627\u0638\u0645\u064a"
    assert d.normalized_value == "\u06a9\u0627\u0638\u0645\u06cc"
    assert d.start == 5
    assert d.end == 10


def test_zwnj_offset_preservation() -> None:
    """Verify ZWNJ within compound surname is preserved in exact offsets."""
    text = "آقای سید\u200cمحسن حسینی"
    # "سید\u200cمحسن" (5..13) and "حسینی" (14..19)
    offsets = [(0, 0), (0, 4), (5, 13), (14, 19), (0, 0)]
    pred_indices = [0, 0, 1, 2, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    d = detections[0]
    assert d.value == "سید\u200cمحسن حسینی"
    assert d.start == 5
    assert d.end == 19


def test_deterministic_detection_ordering() -> None:
    """Verify detections are returned deterministically sorted by (start, end, type)."""
    text = "سارا و مریم"
    offsets = [(0, 0), (0, 4), (5, 6), (7, 11), (0, 0)]
    pred_indices = [0, 1, 0, 1, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = PersianNERDetector._create_for_test(tokenizer, model)

    detections = detector.detect(text, text)
    assert len(detections) == 2
    assert detections[0].start < detections[1].start


# =========================================================================
# 29-30. Long Text Fail-Loud Policy Tests
# =========================================================================


def test_overlength_input_rejected_without_truncation() -> None:
    """Verify input exceeding max_length fails loudly without truncation."""
    text = "علی " * 300
    # Over 300 tokens, with max_length=128
    tokenizer = DummyFastTokenizer()
    model = DummyModel()
    detector = PersianNERDetector._create_for_test(tokenizer, model, max_length=128)

    with pytest.raises(ValueError) as exc_info:
        detector.detect(text, text)

    err_msg = str(exc_info.value)
    assert "exceeds PersianNERDetector max_length" in err_msg
    # Ensure privacy-safe error: no source text leaked in error message
    assert "علی" not in err_msg


# =========================================================================
# 36. Pipeline / Redaction / Pseudonymization Integration Tests
# =========================================================================


def test_detect_pipeline_explicit_ner_integration() -> None:
    """Verify detect(text, detectors=[ner]) runs NER and returns PERSON."""
    text = "بیمار علی محمدی مراجعه کرد"
    offsets = [(0, 0), (0, 5), (6, 9), (10, 15), (16, 22), (23, 26), (0, 0)]
    pred_indices = [0, 0, 1, 2, 0, 0, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    ner = PersianNERDetector._create_for_test(tokenizer, model)

    # 1. detect with explicit NER detector
    detections = detect(text, detectors=[ner])
    assert len(detections) == 1
    assert detections[0].type == "PERSON"
    assert detections[0].value == "علی محمدی"

    # 2. detect without explicit detectors uses defaults (no PERSON)
    default_detections = detect(text)
    assert len(default_detections) == 0

    # 3. detect with empty list returns []
    empty_detections = detect(text, detectors=[])
    assert empty_detections == []


def test_redact_pipeline_person_placeholder() -> None:
    """Verify redact(text, detectors=[ner]) replaces PERSON with [PERSON_1]."""
    text = "بیمار علی محمدی مراجعه کرد و علی محمدی بستری شد."
    # 2 occurrences of "علی محمدی"
    offsets = [
        (0, 0),
        (0, 5),  # "بیمار"
        (6, 9),  # "علی"
        (10, 15),  # "محمدی"
        (16, 22),  # "مراجعه"
        (23, 26),  # "کرد"
        (27, 28),  # "و"
        (29, 32),  # "علی"
        (33, 38),  # "محمدی"
        (39, 44),  # "بستری"
        (45, 48),  # "شد."
        (0, 0),
    ]
    pred_indices = [0, 0, 1, 2, 0, 0, 0, 1, 2, 0, 0, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    ner = PersianNERDetector._create_for_test(tokenizer, model)

    redacted = redact(text, detectors=[ner])
    assert redacted == "بیمار [PERSON_1] مراجعه کرد و [PERSON_1] بستری شد."


def test_pseudonymization_session_with_ner() -> None:
    """Verify PseudonymizationSession works with explicit PersianNERDetector."""
    text1 = "بیمار سارا رضایی بستری شد."
    text2 = "وضعیت سارا رضایی پایدار است."

    # Mock tokenizer & model for both turns
    offsets1 = [(0, 0), (0, 5), (6, 10), (11, 16), (17, 22), (23, 26), (0, 0)]
    offsets2 = [(0, 0), (0, 5), (6, 10), (11, 16), (17, 23), (24, 28), (0, 0)]

    tokenizer = MagicMock(is_fast=True)

    def tok_side_effect(t: str, **kwargs: Any) -> dict[str, Any]:
        offsets = offsets1 if "بستری" in t else offsets2
        return {
            "input_ids": [101] * len(offsets),
            "attention_mask": [1] * len(offsets),
            "offset_mapping": offsets,
        }

    tokenizer.side_effect = tok_side_effect

    model = DummyModel(pred_indices=[0, 0, 1, 2, 0, 0, 0])
    ner = PersianNERDetector._create_for_test(tokenizer, model)

    session = PseudonymizationSession()
    res1 = session.pseudonymize(text1, detectors=[ner])
    assert res1 == "بیمار [PERSON_1] بستری شد."

    res2 = session.pseudonymize(text2, detectors=[ner])
    assert res2 == "وضعیت [PERSON_1] پایدار است."

    restored = session.restore(res2)
    assert restored == text2


def test_conflict_resolution_with_ner_and_other_detectors() -> None:
    """Verify PERSON detections participate in standard conflict resolution."""
    # Suppose span 0..10 is detected as IR_NATIONAL_ID and 0..10 is detected as PERSON
    d_nid = Detection(
        type="IR_NATIONAL_ID",
        value="0012345678",
        normalized_value="0012345678",
        start=0,
        end=10,
    )
    d_per = Detection(
        type="PERSON",
        value="0012345678",
        normalized_value="0012345678",
        start=0,
        end=10,
    )

    # 1. Default reject policy fails loudly on overlap
    with pytest.raises(ValueError, match="Overlapping detections"):
        resolve_detection_conflicts([d_nid, d_per], policy="reject")

    # 2. Priority policy resolves according to type_priority
    resolved = resolve_detection_conflicts(
        [d_nid, d_per],
        policy="priority",
        type_priority=["PERSON", "IR_NATIONAL_ID"],
    )
    assert len(resolved) == 1
    assert resolved[0].type == "PERSON"


def test_offline_mock_detector_when_torch_uninstalled() -> None:
    """Verify PersianNERDetector._create_for_test works when torch is not installed."""
    text = "علی رضایی"
    offsets = [(0, 0), (0, 3), (4, 9), (0, 0)]
    pred_indices = [0, 1, 2, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)

    with patch.dict(sys.modules, {"torch": None, "transformers": None}):
        detector = PersianNERDetector._create_for_test(tokenizer, model)
        detections = detector.detect(text, text)

    assert len(detections) == 1
    assert detections[0].type == "PERSON"
    assert detections[0].value == "علی رضایی"
