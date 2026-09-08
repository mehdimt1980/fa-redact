"""Unit and integration tests for PersianNERDetector."""

from __future__ import annotations

import contextlib
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


class FakeTensor:
    """Mock tensor object implementing operations required by test assertions."""

    def __init__(self, data: Any) -> None:
        self._data = data

    def __getitem__(self, item: Any) -> FakeTensor:
        if isinstance(self._data, list):
            return FakeTensor(self._data[item])
        return FakeTensor(self._data)

    def tolist(self) -> Any:
        if isinstance(self._data, list):
            return self._data
        if hasattr(self._data, "tolist"):
            return self._data.tolist()
        return self._data


class FakeTorch:
    """Mock torch module implementing operations required by PersianNERDetector."""

    long: int = 0
    float32: int = 1

    @staticmethod
    def tensor(data: Any, dtype: Any = None) -> FakeTensor:
        return FakeTensor(data)

    @staticmethod
    def inference_mode() -> Any:
        return contextlib.nullcontext()

    @staticmethod
    def argmax(tensor: Any, dim: int = -1) -> FakeTensor:
        data = tensor._data if isinstance(tensor, FakeTensor) else tensor
        if hasattr(data, "argmax"):
            res = data.argmax(dim=dim)
            return FakeTensor(res.tolist() if hasattr(res, "tolist") else res)

        if isinstance(data, list):
            result: list[int] = []
            for row in data:
                if isinstance(row, list) and row:
                    max_idx = max(range(len(row)), key=lambda i: row[i])
                    result.append(max_idx)
                elif isinstance(row, (int, float)):
                    result.append(int(row))
            return FakeTensor(result)
        return FakeTensor([])


DEFAULT_FAKE_TORCH = FakeTorch()


def create_test_detector(
    tokenizer: Any,
    model: Any,
    *,
    max_length: int = 512,
    torch_module: Any = DEFAULT_FAKE_TORCH,
) -> PersianNERDetector:
    """Helper for constructing PersianNERDetector in tests with explicit torch mock."""
    return PersianNERDetector._create_for_test(
        tokenizer,
        model,
        max_length=max_length,
        torch_module=torch_module,
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
        pred_indices: list[int] | list[list[int]] | None = None,
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

        call_idx = len(self.call_kwargs) - 1
        input_ids = kwargs.get("input_ids")
        seq_len = 1
        if isinstance(input_ids, FakeTensor):
            if isinstance(input_ids._data, list) and input_ids._data:
                seq_len = (
                    len(input_ids._data[0])
                    if isinstance(input_ids._data[0], list)
                    else len(input_ids._data)
                )
        elif input_ids is not None and hasattr(input_ids, "shape"):
            seq_len = int(input_ids.shape[-1])
        elif isinstance(input_ids, list) and input_ids:
            seq_len = (
                len(input_ids[0]) if isinstance(input_ids[0], list) else len(input_ids)
            )

        curr_preds: list[int] = []
        if self.pred_indices:
            preds_any: Any = self.pred_indices
            if isinstance(preds_any[0], list):
                # Per-call predictions
                if call_idx < len(preds_any):
                    curr_preds = [int(x) for x in preds_any[call_idx]]
            else:
                curr_preds = [int(x) for x in preds_any]

        if not curr_preds:
            curr_preds = [0] * seq_len
        elif len(curr_preds) < seq_len:
            curr_preds = curr_preds + [0] * (seq_len - len(curr_preds))
        elif len(curr_preds) > seq_len:
            curr_preds = curr_preds[:seq_len]

        num_classes = max(
            len(self.config.id2label),
            (max(curr_preds) + 1) if curr_preds else 1,
        )
        batch_logits = []
        for idx in curr_preds:
            row = [-100.0] * num_classes
            row[idx] = 100.0
            batch_logits.append(row)
        logits_tensor = FakeTensor([batch_logits])

        return DummyOutput(logits=logits_tensor)


class DummyFastTokenizer:
    """Mock Hugging Face fast tokenizer."""

    def __init__(
        self,
        token_offsets: list[tuple[int, int]] | None = None,
        is_fast: bool = True,
        model_max_length: int = 512,
        cls_token_id: int | None = None,
        sep_token_id: int | None = None,
    ) -> None:
        self.token_offsets = token_offsets
        self.is_fast = is_fast
        self.model_max_length = model_max_length
        self.cls_token_id = cls_token_id
        self.sep_token_id = sep_token_id

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
        create_test_detector(tokenizer, model)


def test_missing_i_per_label_rejected(tmp_path: Path) -> None:
    """Verify model without I-PER label is rejected loudly."""
    config = DummyConfig(id2label={0: "O", 1: "B_PER", 2: "B_ORG"})
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)

    with pytest.raises(ValueError, match="missing required I-PER"):
        create_test_detector(tokenizer, model)


def test_string_numeric_id2label_keys_supported() -> None:
    """Verify string numeric keys in id2label (e.g. from JSON config) work."""
    config = DummyConfig(id2label={"0": "O", "1": "B-PERSON", "2": "I-PERSON"})
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)

    detector = create_test_detector(tokenizer, model)
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
            create_test_detector(tokenizer, model, max_length=invalid_val)


def test_max_length_exceeding_model_capacity_rejected() -> None:
    """Verify max_length > model max_position_embeddings is rejected."""
    config = DummyConfig(max_position_embeddings=256)
    tokenizer = DummyFastTokenizer(model_max_length=1024)
    model = DummyModel(config=config)

    with pytest.raises(ValueError, match="exceeds model positional capacity"):
        create_test_detector(tokenizer, model, max_length=512)


def test_max_length_exceeding_tokenizer_model_max_length_rejected() -> None:
    """Verify max_length > tokenizer model_max_length is rejected when credible."""
    config = DummyConfig(max_position_embeddings=1024)
    tokenizer = DummyFastTokenizer(model_max_length=256)
    model = DummyModel(config=config)

    with pytest.raises(ValueError, match="exceeds tokenizer maximum sequence length"):
        create_test_detector(tokenizer, model, max_length=512)


def test_huge_sentinel_tokenizer_model_max_length_ignored() -> None:
    """Verify huge sentinel model_max_length is ignored as non-authoritative."""
    config = DummyConfig(max_position_embeddings=512)
    tokenizer = DummyFastTokenizer(model_max_length=1000000000000000019884624838656)
    model = DummyModel(config=config)

    detector = create_test_detector(tokenizer, model, max_length=512)
    assert detector._max_length == 512


# =========================================================================
# 13-14. Basic Contract & Input Validation Tests
# =========================================================================


def test_empty_input_returns_empty_list() -> None:
    """Verify empty string returns empty list immediately without calling model."""
    config = DummyConfig()
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)
    detector = create_test_detector(tokenizer, model)

    assert detector.detect("", "") == []
    assert len(model.call_kwargs) == 0


def test_length_mismatch_rejected() -> None:
    """Verify unequal original_text and normalized_text lengths are rejected."""
    config = DummyConfig()
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)
    detector = create_test_detector(tokenizer, model)

    with pytest.raises(ValueError, match="length"):
        detector.detect("ali", "alii")


def test_non_string_inputs_rejected() -> None:
    """Verify non-string inputs raise TypeError."""
    config = DummyConfig()
    tokenizer = DummyFastTokenizer()
    model = DummyModel(config=config)
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

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
    detector = create_test_detector(tokenizer, model)

    detections = detector.detect(text, text)
    assert len(detections) == 2
    assert detections[0].start < detections[1].start


# =========================================================================
# 29-30. Long-Document Sliding-Window PERSON NER Tests (Phase 30)
# =========================================================================


def test_long_document_sliding_window_processes_without_error() -> None:
    """Verify input exceeding max_length processes successfully."""
    text = "کلمه " * 100
    # Over 100 tokens, with max_length=16
    tokenizer = DummyFastTokenizer()
    model = DummyModel()
    detector = create_test_detector(tokenizer, model, max_length=16)

    detections = detector.detect(text, text)
    assert detections == []
    # Verify sliding window partitioned into multiple model forward calls
    assert len(model.call_kwargs) > 1


def test_short_input_remains_single_window_pass() -> None:
    """Verify input within max_length runs single forward pass."""
    text = "علی رضایی آمد"
    offsets = [(0, 0), (0, 3), (4, 9), (10, 13), (0, 0)]
    pred_indices = [0, 1, 2, 0, 0]

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel(pred_indices=pred_indices)
    detector = create_test_detector(tokenizer, model, max_length=16)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    assert detections[0].value == "علی رضایی"
    # Exactly one forward call
    assert len(model.call_kwargs) == 1


def test_long_document_person_in_later_window() -> None:
    """Verify PERSON entity deep in a later window is detected with exact offsets."""
    # Build a 20-word text with max_length=8 (capacity=6, stride=3)
    # Words 0..11 are non-entity, 12..13 are PERSON, 14..19 are non-entity
    words = (
        [f"کلمه{i}" for i in range(12)]
        + ["سهراب", "سپهری"]
        + [f"کلمه{i}" for i in range(14, 20)]
    )
    text = " ".join(words)

    # Compute exact offsets
    offsets: list[tuple[int, int]] = [(0, 0)]  # [CLS]
    pos = 0
    sohrab_start = 0
    sohrab_end = 0
    for w in words:
        start = text.find(w, pos)
        end = start + len(w)
        offsets.append((start, end))
        if w == "سهراب":
            sohrab_start = start
        elif w == "سپهری":
            sohrab_end = end
        pos = end
    offsets.append((0, 0))  # [SEP]

    # Model returns 0 everywhere except for "سهراب" (B_PER=1) and "سپهری" (I_PER=2)
    # The tokens in full sequence:
    # 0:[CLS], 1..12:words, 13:"سهراب", 14:"سپهری", 15..20:words, 21:[SEP]
    # For windows, we can pass a mock model that checks token offsets or content IDs:
    class DynamicLookupModel:
        def __init__(self) -> None:
            self.config = DummyConfig()
            self.call_kwargs: list[dict[str, Any]] = []

        def eval(self) -> DynamicLookupModel:
            return self

        def __call__(self, **kwargs: Any) -> DummyOutput:
            self.call_kwargs.append(kwargs)
            input_ids = kwargs["input_ids"]._data[0]
            preds = []
            for tid in input_ids:
                # tid 1012 is "سهراب" (index 12 content token -> 1000 + 12 = 1012)
                # tid 1013 is "سپهری" (index 13 content token -> 1000 + 13 = 1013)
                if tid == 1012:
                    preds.append(1)  # B_PER
                elif tid == 1013:
                    preds.append(2)  # I_PER
                else:
                    preds.append(0)  # O
            batch_logits = []
            for p in preds:
                row = [-100.0] * 5
                row[p] = 100.0
                batch_logits.append(row)
            return DummyOutput(logits=FakeTensor([batch_logits]))

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DynamicLookupModel()
    detector = create_test_detector(tokenizer, model, max_length=8)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    d = detections[0]
    assert d.type == "PERSON"
    assert d.value == "سهراب سپهری"
    assert d.start == sohrab_start
    assert d.end == sohrab_end
    assert len(model.call_kwargs) > 1


def test_long_document_person_in_overlap_region_deduplicated() -> None:
    """Verify PERSON entity in overlapping window region is emitted once."""
    # 12 words with max_length=8 (capacity=6, stride=3)
    # Window 0: content tokens 0..6
    # Window 1: content tokens 3..9 (overlap is 3..6)
    # Let "فروغ فرخزاد" be at content tokens 4..5
    words = (
        [f"کلمه{i}" for i in range(4)]
        + ["فروغ", "فرخزاد"]
        + [f"کلمه{i}" for i in range(6, 12)]
    )
    text = " ".join(words)

    offsets: list[tuple[int, int]] = [(0, 0)]
    pos = 0
    for w in words:
        start = text.find(w, pos)
        end = start + len(w)
        offsets.append((start, end))
        pos = end
    offsets.append((0, 0))

    class OverlapModel:
        def __init__(self) -> None:
            self.config = DummyConfig()
            self.call_kwargs: list[dict[str, Any]] = []

        def eval(self) -> OverlapModel:
            return self

        def __call__(self, **kwargs: Any) -> DummyOutput:
            self.call_kwargs.append(kwargs)
            input_ids = kwargs["input_ids"]._data[0]
            preds = []
            for tid in input_ids:
                if tid == 1004:  # "فروغ" (content token 4)
                    preds.append(1)  # B_PER
                elif tid == 1005:  # "فرخزاد" (content token 5)
                    preds.append(2)  # I_PER
                else:
                    preds.append(0)
            batch_logits = []
            for p in preds:
                row = [-100.0] * 5
                row[p] = 100.0
                batch_logits.append(row)
            return DummyOutput(logits=FakeTensor([batch_logits]))

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = OverlapModel()
    detector = create_test_detector(tokenizer, model, max_length=8)

    detections = detector.detect(text, text)
    # Must be deduplicated into exactly 1 detection
    assert len(detections) == 1
    d = detections[0]
    assert d.value == "فروغ فرخزاد"
    assert d.type == "PERSON"
    # Ensure both Window 0 and Window 1 actually executed
    assert len(model.call_kwargs) >= 2


def test_long_document_person_crossing_window_boundary_merged() -> None:
    """Verify PERSON entity split across window boundaries is merged."""
    # max_length=6 (capacity=4, stride=2)
    # Window 0: content tokens 0..4
    # Window 1: content tokens 2..6
    # Let content token 3 be "سید" (end of first half), content token 4 be "علی"
    # Window 0 sees token 3 as B_PER (1)
    # Window 1 sees token 3 as B_PER (1) or token 4 as I_PER (2)
    words = ["الف", "ب", "ج", "سید", "علی", "د", "ه", "و"]
    text = " ".join(words)

    offsets: list[tuple[int, int]] = [(0, 0)]
    pos = 0
    for w in words:
        start = text.find(w, pos)
        end = start + len(w)
        offsets.append((start, end))
        pos = end
    offsets.append((0, 0))

    class SplitModel:
        def __init__(self) -> None:
            self.config = DummyConfig()
            self.call_kwargs: list[dict[str, Any]] = []

        def eval(self) -> SplitModel:
            return self

        def __call__(self, **kwargs: Any) -> DummyOutput:
            self.call_kwargs.append(kwargs)
            input_ids = kwargs["input_ids"]._data[0]
            preds = []
            for tid in input_ids:
                if tid == 1003:  # "سید" (content token 3)
                    preds.append(1)  # B_PER
                elif tid == 1004:  # "علی" (content token 4)
                    preds.append(2)  # I_PER
                else:
                    preds.append(0)
            batch_logits = []
            for p in preds:
                row = [-100.0] * 5
                row[p] = 100.0
                batch_logits.append(row)
            return DummyOutput(logits=FakeTensor([batch_logits]))

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = SplitModel()
    detector = create_test_detector(tokenizer, model, max_length=6)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    d = detections[0]
    assert d.value == "سید علی"
    assert d.type == "PERSON"


def test_long_document_distinct_adjacent_persons_across_boundary_not_merged() -> None:
    """Verify two distinct B-PER entities across window boundaries remain separate."""
    # content token 3 is "سارا" (B_PER), content token 4 is "مریم" (B_PER)
    words = ["الف", "ب", "ج", "سارا", "مریم", "د", "ه", "و"]
    text = " ".join(words)

    offsets: list[tuple[int, int]] = [(0, 0)]
    pos = 0
    for w in words:
        start = text.find(w, pos)
        end = start + len(w)
        offsets.append((start, end))
        pos = end
    offsets.append((0, 0))

    class DistinctModel:
        def __init__(self) -> None:
            self.config = DummyConfig()
            self.call_kwargs: list[dict[str, Any]] = []

        def eval(self) -> DistinctModel:
            return self

        def __call__(self, **kwargs: Any) -> DummyOutput:
            self.call_kwargs.append(kwargs)
            input_ids = kwargs["input_ids"]._data[0]
            preds = []
            for tid in input_ids:
                if tid in (1003, 1004):  # Both are B_PER (distinct individuals)
                    preds.append(1)
                else:
                    preds.append(0)
            batch_logits = []
            for p in preds:
                row = [-100.0] * 5
                row[p] = 100.0
                batch_logits.append(row)
            return DummyOutput(logits=FakeTensor([batch_logits]))

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DistinctModel()
    detector = create_test_detector(tokenizer, model, max_length=6)

    detections = detector.detect(text, text)
    assert len(detections) == 2
    assert detections[0].value == "سارا"
    assert detections[1].value == "مریم"


def test_long_document_conjunction_separated_persons_across_boundary_not_merged() -> (
    None
):
    """Verify PERSON entities separated by conjunction words are not merged."""
    words = ["الف", "ب", "سارا", "و", "مریم", "د", "ه", "و"]
    text = " ".join(words)

    offsets: list[tuple[int, int]] = [(0, 0)]
    pos = 0
    for w in words:
        start = text.find(w, pos)
        end = start + len(w)
        offsets.append((start, end))
        pos = end
    offsets.append((0, 0))

    class ConjunctionModel:
        def __init__(self) -> None:
            self.config = DummyConfig()
            self.call_kwargs: list[dict[str, Any]] = []

        def eval(self) -> ConjunctionModel:
            return self

        def __call__(self, **kwargs: Any) -> DummyOutput:
            self.call_kwargs.append(kwargs)
            input_ids = kwargs["input_ids"]._data[0]
            preds = []
            for tid in input_ids:
                if tid == 1002:  # "سارا"
                    preds.append(1)  # B_PER
                elif tid == 1004:  # "مریم"
                    preds.append(2)  # Even if noisy I_PER, gap has "و"
                else:
                    preds.append(0)
            batch_logits = []
            for p in preds:
                row = [-100.0] * 5
                row[p] = 100.0
                batch_logits.append(row)
            return DummyOutput(logits=FakeTensor([batch_logits]))

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = ConjunctionModel()
    detector = create_test_detector(tokenizer, model, max_length=6)

    detections = detector.detect(text, text)
    assert len(detections) == 2
    assert detections[0].value == "سارا"
    assert detections[1].value == "مریم"


def test_long_document_multiple_persons_across_several_windows() -> None:
    """Verify multiple PERSON entities across 4+ windows are collected and sorted."""
    words = (
        ["الف", "علی", "رضایی", "ب", "ج"]  # Window 0 area
        + ["د", "ه", "و", "ز", "ح"]
        + ["ط", "سارا", "حسینی", "ی", "ک"]  # Window 2 area
        + ["ل", "م", "ن", "س", "ع"]
        + ["ف", "محمد", "کاظمی", "ق", "ر"]  # Window 4 area
    )
    text = " ".join(words)

    offsets: list[tuple[int, int]] = [(0, 0)]
    pos = 0
    for w in words:
        start = text.find(w, pos)
        end = start + len(w)
        offsets.append((start, end))
        pos = end
    offsets.append((0, 0))

    class MultiPersonModel:
        def __init__(self) -> None:
            self.config = DummyConfig()
            self.call_kwargs: list[dict[str, Any]] = []

        def eval(self) -> MultiPersonModel:
            return self

        def __call__(self, **kwargs: Any) -> DummyOutput:
            self.call_kwargs.append(kwargs)
            input_ids = kwargs["input_ids"]._data[0]
            preds = []
            for tid in input_ids:
                if tid in (1001, 1011, 1021):  # Ali, Sara, Mohammad
                    preds.append(1)  # B_PER
                elif tid in (1002, 1012, 1022):  # Rezaei, Hosseini, Kazemi
                    preds.append(2)  # I_PER
                else:
                    preds.append(0)
            batch_logits = []
            for p in preds:
                row = [-100.0] * 5
                row[p] = 100.0
                batch_logits.append(row)
            return DummyOutput(logits=FakeTensor([batch_logits]))

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = MultiPersonModel()
    detector = create_test_detector(tokenizer, model, max_length=8)

    detections = detector.detect(text, text)
    assert len(detections) == 3
    assert [d.value for d in detections] == ["علی رضایی", "سارا حسینی", "محمد کاظمی"]
    assert detections[0].start < detections[1].start < detections[2].start


def test_long_document_arabic_persian_normalization_exact_offsets() -> None:
    """Verify Arabic kaf/yeh and Persian digits preserve original offsets."""
    # Original text with Arabic kaf '\u0643' and Arabic yeh '\u064a'
    orig_name = "\u0643\u0627\u0638\u0645\u064a"
    norm_name = "\u06a9\u0627\u0638\u0645\u06cc"

    words_orig = (
        [f"کلمه{i}" for i in range(12)]
        + [orig_name]
        + [f"کلمه{i}" for i in range(13, 20)]
    )
    words_norm = (
        [f"کلمه{i}" for i in range(12)]
        + [norm_name]
        + [f"کلمه{i}" for i in range(13, 20)]
    )
    orig_text = " ".join(words_orig)
    norm_text = " ".join(words_norm)

    offsets: list[tuple[int, int]] = [(0, 0)]
    pos = 0
    for w in words_norm:
        start = norm_text.find(w, pos)
        end = start + len(w)
        offsets.append((start, end))
        pos = end
    offsets.append((0, 0))

    class NormalizationModel:
        def __init__(self) -> None:
            self.config = DummyConfig()
            self.call_kwargs: list[dict[str, Any]] = []

        def eval(self) -> NormalizationModel:
            return self

        def __call__(self, **kwargs: Any) -> DummyOutput:
            self.call_kwargs.append(kwargs)
            input_ids = kwargs["input_ids"]._data[0]
            preds = [1 if tid == 1012 else 0 for tid in input_ids]
            batch_logits = []
            for p in preds:
                row = [-100.0] * 5
                row[p] = 100.0
                batch_logits.append(row)
            return DummyOutput(logits=FakeTensor([batch_logits]))

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = NormalizationModel()
    detector = create_test_detector(tokenizer, model, max_length=8)

    detections = detector.detect(orig_text, norm_text)
    assert len(detections) == 1
    d = detections[0]
    assert d.value == orig_name
    assert d.normalized_value == norm_name
    assert orig_text[d.start : d.end] == orig_name
    assert norm_text[d.start : d.end] == norm_name


def test_long_document_deterministic_repeated_calls() -> None:
    """Verify repeated calls on long documents produce identical results."""
    words = (
        [f"کلمه{i}" for i in range(8)]
        + ["سارا", "رضایی"]
        + [f"کلمه{i}" for i in range(10, 20)]
    )
    text = " ".join(words)

    offsets: list[tuple[int, int]] = [(0, 0)]
    pos = 0
    for w in words:
        start = text.find(w, pos)
        end = start + len(w)
        offsets.append((start, end))
        pos = end
    offsets.append((0, 0))

    class DeterministicModel:
        def __init__(self) -> None:
            self.config = DummyConfig()
            self.call_kwargs: list[dict[str, Any]] = []

        def eval(self) -> DeterministicModel:
            return self

        def __call__(self, **kwargs: Any) -> DummyOutput:
            self.call_kwargs.append(kwargs)
            input_ids = kwargs["input_ids"]._data[0]
            preds = [
                1 if tid == 1008 else (2 if tid == 1009 else 0) for tid in input_ids
            ]
            batch_logits = []
            for p in preds:
                row = [-100.0] * 5
                row[p] = 100.0
                batch_logits.append(row)
            return DummyOutput(logits=FakeTensor([batch_logits]))

    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DeterministicModel()
    detector = create_test_detector(tokenizer, model, max_length=8)

    res1 = detector.detect(text, text)
    res2 = detector.detect(text, text)
    res3 = detector.detect(text, text)

    assert len(res1) == 1
    assert res1 == res2 == res3
    assert res1[0].value == "سارا رضایی"


def test_long_document_structural_invalid_offsets_fail_loudly() -> None:
    """Verify structurally invalid tokenizer offsets on long documents fail loudly."""
    text = "کلمه " * 50
    # Out of bounds offset
    bad_offsets_oob = [(0, 0)] + [(0, 500)] + [(0, 0)]
    tokenizer_oob = DummyFastTokenizer(token_offsets=bad_offsets_oob)
    detector_oob = create_test_detector(tokenizer_oob, DummyModel(), max_length=16)

    with pytest.raises(ValueError, match="out-of-bounds"):
        detector_oob.detect(text, text)

    # Non-monotonic offset
    bad_offsets_nm = [(0, 0), (10, 20), (5, 15), (0, 0)]
    tokenizer_nm = DummyFastTokenizer(token_offsets=bad_offsets_nm)
    detector_nm = create_test_detector(tokenizer_nm, DummyModel(), max_length=16)

    with pytest.raises(ValueError, match="non-monotonic"):
        detector_nm.detect(text, text)


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
    ner = create_test_detector(tokenizer, model)

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
    ner = create_test_detector(tokenizer, model)

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
    ner = create_test_detector(tokenizer, model)

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
        detector = create_test_detector(tokenizer, model)
        detections = detector.detect(text, text)

    assert len(detections) == 1
    assert detections[0].type == "PERSON"
    assert detections[0].value == "علی رضایی"


# =========================================================================
# 37. Conservative Overlap & Sliding-Window Safety Regression Tests
# =========================================================================


def test_partially_overlapping_candidates_not_unioned() -> None:
    """Verify partially overlapping conflicting PERSON candidates are not unioned."""
    from fa_redact.detectors.persian_ner import _SpanCandidate

    text = "علی رضا محمدی"
    offsets = [(0, 0), (0, 3), (4, 7), (8, 13), (0, 0)]
    cand1 = _SpanCandidate(
        start=0,
        end=7,
        is_leading_continuation=False,
        is_trailing_boundary=False,
        window_idx=0,
    )
    cand2 = _SpanCandidate(
        start=4,
        end=13,
        is_leading_continuation=False,
        is_trailing_boundary=False,
        window_idx=1,
    )
    tokenizer = DummyFastTokenizer(token_offsets=offsets)
    model = DummyModel()
    detector = create_test_detector(tokenizer, model)

    merged = detector._merge_and_deduplicate_candidates([cand1, cand2], text)
    assert merged == [(0, 7), (4, 13)]


def test_zero_gap_adjacent_b_per_entities_remain_separate() -> None:
    """Verify zero-gap adjacent B-PER entities remain separate."""
    from fa_redact.detectors.persian_ner import _SpanCandidate

    text = "علیرضا"
    cand1 = _SpanCandidate(
        start=0,
        end=3,
        is_leading_continuation=False,
        is_trailing_boundary=True,
        window_idx=0,
    )
    cand2 = _SpanCandidate(
        start=3,
        end=6,
        is_leading_continuation=False,
        is_trailing_boundary=False,
        window_idx=1,
    )
    tokenizer = DummyFastTokenizer()
    model = DummyModel()
    detector = create_test_detector(tokenizer, model)

    merged = detector._merge_and_deduplicate_candidates([cand1, cand2], text)
    assert merged == [(0, 3), (3, 6)]


def test_leading_i_per_from_non_adjacent_window_not_merged() -> None:
    """Verify leading I-PER from non-adjacent window does not merge."""
    from fa_redact.detectors.persian_ner import _SpanCandidate

    text = "علی رضایی"
    cand1 = _SpanCandidate(
        start=0,
        end=3,
        is_leading_continuation=False,
        is_trailing_boundary=True,
        window_idx=0,
    )
    cand2 = _SpanCandidate(
        start=4,
        end=9,
        is_leading_continuation=True,
        is_trailing_boundary=False,
        window_idx=2,
    )
    tokenizer = DummyFastTokenizer()
    model = DummyModel()
    detector = create_test_detector(tokenizer, model)

    merged = detector._merge_and_deduplicate_candidates([cand1, cand2], text)
    assert merged == [(0, 3), (4, 9)]


def test_leading_i_per_not_merged_when_previous_span_not_trailing_boundary() -> None:
    """Verify leading I-PER does not merge if previous span is not at boundary."""
    from fa_redact.detectors.persian_ner import _SpanCandidate

    text = "علی رضایی"
    cand1 = _SpanCandidate(
        start=0,
        end=3,
        is_leading_continuation=False,
        is_trailing_boundary=False,
        window_idx=0,
    )
    cand2 = _SpanCandidate(
        start=4,
        end=9,
        is_leading_continuation=True,
        is_trailing_boundary=False,
        window_idx=1,
    )
    tokenizer = DummyFastTokenizer()
    model = DummyModel()
    detector = create_test_detector(tokenizer, model)

    merged = detector._merge_and_deduplicate_candidates([cand1, cand2], text)
    assert merged == [(0, 3), (4, 9)]


def test_too_small_max_length_fails_loudly_on_long_input() -> None:
    """Verify max_length < 3 on long input fails loudly before model call."""
    text = "کلمه " * 10
    tokenizer = DummyFastTokenizer()
    model = DummyModel()
    detector = create_test_detector(tokenizer, model, max_length=2)

    with pytest.raises(ValueError) as exc_info:
        detector.detect(text, text)

    err_msg = str(exc_info.value)
    assert "too small for sliding-window inference" in err_msg
    assert "کلمه" not in err_msg
    assert len(model.call_kwargs) == 0


def test_missing_unidentifiable_special_tokens_fails_loudly() -> None:
    """Verify missing/unidentifiable special token IDs fail loudly."""
    text = "کلمه " * 10
    content_offsets = [(0, 4), (5, 9), (10, 14), (15, 19), (20, 24)]
    tokenizer = DummyFastTokenizer(token_offsets=content_offsets)
    tokenizer.cls_token_id = None
    tokenizer.sep_token_id = None
    model = DummyModel()
    detector = create_test_detector(tokenizer, model, max_length=4)

    with pytest.raises(ValueError) as exc_info:
        detector.detect(text, text)

    assert "Tokenizer missing required special token configuration" in str(
        exc_info.value
    )


def test_subsumed_candidate_preserves_boundary_provenance_3_windows() -> None:
    """Verify subsumed boundary candidate preserves provenance for 3-window split."""
    from fa_redact.detectors.persian_ner import _SpanCandidate

    text = "علی رضا محمدی"
    # Window 0: retained outer span (0, 7) ending at 7, trailing boundary
    cand0 = _SpanCandidate(
        start=0,
        end=7,
        is_leading_continuation=False,
        is_trailing_boundary=True,
        window_idx=0,
    )
    # Window 1: subsumed duplicate span (4, 7) also ending at 7, trailing boundary
    cand1 = _SpanCandidate(
        start=4,
        end=7,
        is_leading_continuation=False,
        is_trailing_boundary=True,
        window_idx=1,
    )
    # Window 2: leading I-PER continuation (8, 13)
    cand2 = _SpanCandidate(
        start=8,
        end=13,
        is_leading_continuation=True,
        is_trailing_boundary=False,
        window_idx=2,
    )
    tokenizer = DummyFastTokenizer()
    model = DummyModel()
    detector = create_test_detector(tokenizer, model)

    merged = detector._merge_and_deduplicate_candidates([cand0, cand1, cand2], text)
    assert merged == [(0, 13)]


def test_subsumed_candidate_interior_end_does_not_advance_provenance() -> None:
    """Verify subsumed candidate ending inside retained span doesn't advance window."""
    from fa_redact.detectors.persian_ner import _SpanCandidate

    text = "علی رضا محمدی رحیمی"
    # Window 0: retained outer span (0, 10), trailing boundary
    cand0 = _SpanCandidate(
        start=0,
        end=10,
        is_leading_continuation=False,
        is_trailing_boundary=True,
        window_idx=0,
    )
    # Window 1: subsumed span (4, 7) ending at 7 (< 10), trailing boundary
    cand1 = _SpanCandidate(
        start=4,
        end=7,
        is_leading_continuation=False,
        is_trailing_boundary=True,
        window_idx=1,
    )
    # Window 2: leading I-PER continuation (11, 16)
    cand2 = _SpanCandidate(
        start=11,
        end=16,
        is_leading_continuation=True,
        is_trailing_boundary=False,
        window_idx=2,
    )
    tokenizer = DummyFastTokenizer()
    model = DummyModel()
    detector = create_test_detector(tokenizer, model)

    merged = detector._merge_and_deduplicate_candidates([cand0, cand1, cand2], text)
    # Window 2 must NOT merge with Window 0 because window_idx was not updated
    assert merged == [(0, 10), (11, 16)]
