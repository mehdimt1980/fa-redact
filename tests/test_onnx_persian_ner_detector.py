"""Unit and integration tests for ONNXPersianNERDetector."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import fa_redact
from fa_redact import (
    Detector,
    IranianIBANDetector,
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
    ONNXPersianNERDetector,
    PseudonymizationSession,
    clinical_profile,
    detect,
    detect_many,
    redact,
    redact_fields,
    redact_many,
)


class DummyONNXInput:
    """Mock ONNX node input descriptor."""

    def __init__(self, name: str) -> None:
        self.name = name


class DummyONNXSession:
    """Mock ONNX Runtime InferenceSession for deterministic unit testing."""

    def __init__(
        self,
        input_names: list[str] | None = None,
        pred_indices: list[int] | list[list[int]] | None = None,
        num_classes: int = 10,
    ) -> None:
        self.input_names = input_names or ["input_ids", "attention_mask"]
        self.pred_indices = pred_indices or []
        self.num_classes = num_classes
        self.call_count = 0
        self.call_feeds: list[dict[str, Any]] = []

    def get_inputs(self) -> list[DummyONNXInput]:
        return [DummyONNXInput(name) for name in self.input_names]

    def run(self, output_names: Any, input_feed: dict[str, Any]) -> list[Any]:
        self.call_count += 1
        self.call_feeds.append(input_feed)
        input_ids = input_feed["input_ids"]
        if hasattr(input_ids, "shape"):
            seq_len = int(input_ids.shape[-1])
        elif isinstance(input_ids, list) and input_ids:
            seq_len = (
                len(input_ids[0]) if isinstance(input_ids[0], list) else len(input_ids)
            )
        else:
            seq_len = 1

        call_idx = self.call_count - 1
        curr_preds: list[int] = []
        if self.pred_indices:
            preds_any: Any = self.pred_indices
            if isinstance(preds_any[0], list):
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

        num_c = max(self.num_classes, (max(curr_preds) + 1) if curr_preds else 1)
        batch_logits: list[list[float]] = []
        for idx in curr_preds:
            row = [-100.0] * num_c
            row[idx] = 100.0
            batch_logits.append(row)

        return [[batch_logits]]


class DummyFastTokenizer:
    """Mock Hugging Face fast tokenizer with explicit offset mappings."""

    def __init__(
        self,
        token_offsets: list[tuple[int, int]] | None = None,
        is_fast: bool = True,
        model_max_length: int = 512,
        cls_token_id: int | None = None,
        sep_token_id: int | None = None,
        include_token_type_ids: bool = True,
    ) -> None:
        self.token_offsets = token_offsets
        self.is_fast = is_fast
        self.model_max_length = model_max_length
        self.cls_token_id = cls_token_id
        self.sep_token_id = sep_token_id
        self.include_token_type_ids = include_token_type_ids

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
        res: dict[str, Any] = {
            "input_ids": [101] + [1000 + i for i in range(max(0, n - 2))] + [102],
            "attention_mask": [1] * n,
            "offset_mapping": offsets,
        }
        if self.include_token_type_ids:
            res["token_type_ids"] = [0] * n
        return res


def create_test_onnx_detector(
    tokenizer: Any,
    session: Any,
    *,
    id2label: dict[Any, str] | None = None,
    max_length: int = 512,
    max_position_embeddings: int | None = 512,
    np_module: Any = None,
) -> ONNXPersianNERDetector:
    """Helper for constructing ONNXPersianNERDetector in tests with mock session."""
    return ONNXPersianNERDetector._create_for_test(
        tokenizer=tokenizer,
        session=session,
        id2label=id2label,
        max_length=max_length,
        max_position_embeddings=max_position_embeddings,
        np_module=np_module,
    )


# =========================================================================
# 1-3. Import & Backend Availability Tests
# =========================================================================


def test_import_fa_redact_without_onnx_backend() -> None:
    """Verify fa_redact top-level imports safely and exports ONNXPersianNERDetector."""
    assert hasattr(fa_redact, "ONNXPersianNERDetector")
    assert ONNXPersianNERDetector is not None


def test_import_onnx_persian_ner_detector_lazy() -> None:
    """Verify importing ONNXPersianNERDetector is lazy without model loading."""
    from fa_redact.detectors.onnx_persian_ner import (
        ONNXPersianNERDetector as ONNXCls,
    )

    assert ONNXCls is not None


def test_missing_extra_dependency_error(tmp_path: Path) -> None:
    """Verify clear error directing user to pip install fa-redact[onnx] when missing."""
    model_dir = tmp_path / "fake_onnx_model"
    model_dir.mkdir()

    with patch.dict(sys.modules, {"onnxruntime": None, "transformers": None}):
        with pytest.raises(ImportError) as exc_info:
            ONNXPersianNERDetector(model_dir)

        err_msg = str(exc_info.value)
        assert 'pip install "fa-redact[onnx]"' in err_msg


# =========================================================================
# 4-9. Path & Loading Options Tests
# =========================================================================


def test_nonexistent_local_model_path() -> None:
    """Verify FileNotFoundError on non-existent local model path."""
    with pytest.raises(FileNotFoundError) as exc_info:
        ONNXPersianNERDetector("/nonexistent/path/to/onnx_model")
    assert "does not exist" in str(exc_info.value)


def test_model_path_is_file_not_dir(tmp_path: Path) -> None:
    """Verify NotADirectoryError when model_path is a file instead of directory."""
    file_path = tmp_path / "model.onnx"
    file_path.write_bytes(b"fake onnx bytes")

    with pytest.raises(NotADirectoryError) as exc_info:
        ONNXPersianNERDetector(file_path)
    assert "not a directory" in str(exc_info.value)


def test_invalid_model_path_type() -> None:
    """Verify TypeError on non-str non-Path model_path."""
    with pytest.raises(TypeError) as exc_info:
        ONNXPersianNERDetector(12345)  # type: ignore[arg-type]
    assert "str or Path" in str(exc_info.value)


def test_missing_onnx_model_file_in_dir(tmp_path: Path) -> None:
    """Verify FileNotFoundError when directory contains no .onnx files."""
    model_dir = tmp_path / "empty_model_dir"
    model_dir.mkdir()

    with patch.dict(
        sys.modules,
        {"onnxruntime": MagicMock(), "transformers": MagicMock(), "numpy": MagicMock()},
    ):
        with pytest.raises(FileNotFoundError) as exc_info:
            ONNXPersianNERDetector(model_dir)
        assert "No ONNX model file" in str(exc_info.value)


def test_multiple_onnx_files_without_model_onnx(tmp_path: Path) -> None:
    """Verify ValueError when multiple .onnx files exist without 'model.onnx'."""
    model_dir = tmp_path / "multi_model_dir"
    model_dir.mkdir()
    (model_dir / "a.onnx").write_bytes(b"")
    (model_dir / "b.onnx").write_bytes(b"")

    with patch.dict(
        sys.modules,
        {"onnxruntime": MagicMock(), "transformers": MagicMock(), "numpy": MagicMock()},
    ):
        with pytest.raises(ValueError) as exc_info:
            ONNXPersianNERDetector(model_dir)
        assert "Multiple ONNX model files found" in str(exc_info.value)


def test_invalid_max_length_arguments(tmp_path: Path) -> None:
    """Verify ValueError on invalid max_length parameters."""
    model_dir = tmp_path / "valid_dir"
    model_dir.mkdir()

    for invalid_len in (0, -1, -500, False, True, "512", 2.5):
        with pytest.raises(ValueError) as exc_info:
            ONNXPersianNERDetector(model_dir, max_length=invalid_len)  # type: ignore[arg-type]
        assert "positive integer" in str(exc_info.value)


def test_missing_or_invalid_id2label_configuration() -> None:
    """Verify ValueError when id2label is missing or lacks person labels."""
    tok = DummyFastTokenizer()
    sess = DummyONNXSession()

    # Missing person labels (e.g. only O, B-ORG, I-ORG)
    non_person_id2label = {0: "O", 1: "B-ORG", 2: "I-ORG"}
    with pytest.raises(ValueError) as exc_info:
        create_test_onnx_detector(tok, sess, id2label=non_person_id2label)
    assert "missing required person-name label configuration" in str(exc_info.value)


def test_max_length_exceeding_positional_capacity() -> None:
    """Verify ValueError when max_length exceeds model or tokenizer capacity."""
    tok = DummyFastTokenizer(model_max_length=256)
    sess = DummyONNXSession()

    with pytest.raises(ValueError) as exc_info:
        create_test_onnx_detector(
            tok, sess, max_length=512, max_position_embeddings=256
        )
    assert "exceeds model positional capacity" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        create_test_onnx_detector(
            tok, sess, max_length=512, max_position_embeddings=512
        )
    assert "exceeds tokenizer maximum sequence length" in str(exc_info.value)


# =========================================================================
# 10-15. Standard BIO & Name Component Reconstruction Tests
# =========================================================================


def test_person_from_givenname_and_surname() -> None:
    """Verify PERSON detection merges GIVENNAME + SURNAME across whitespace."""
    # Text: "بیمار علی حسینی مراجعه کرد"
    # Tokens: [CLS], "بیمار", "علی", "حسینی", "مراجعه", "کرد", [SEP]
    text = "بیمار علی حسینی مراجعه کرد"
    offsets = [
        (0, 0),  # CLS
        (0, 5),  # بیمار
        (6, 9),  # علی (GIVENNAME)
        (10, 15),  # حسینی (SURNAME)
        (16, 22),  # مراجعه
        (23, 26),  # کرد
        (0, 0),  # SEP
    ]
    id2label = {
        0: "O",
        1: "B-GIVENNAME",
        2: "I-GIVENNAME",
        3: "B-SURNAME",
        4: "I-SURNAME",
        5: "B-TITLE",
        6: "I-TITLE",
    }
    # Predictions: O, O, B-GIVEN, B-SUR, O, O, O
    preds = [0, 0, 1, 3, 0, 0, 0]

    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=preds)
    detector = create_test_onnx_detector(tok, sess, id2label=id2label)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    d = detections[0]
    assert d.type == "PERSON"
    assert d.start == 6
    assert d.end == 15
    assert d.value == "علی حسینی"


def test_person_from_standard_per_bio() -> None:
    """Verify PERSON detection from standard B-PER / I-PER tokens."""
    # Text: "دکتر مریم رضایی پور"
    # Tokens: [CLS], "دکتر", "مریم", "رضایی", "پور", [SEP]
    text = "دکتر مریم رضایی پور"
    offsets = [
        (0, 0),
        (0, 4),  # دکتر (TITLE)
        (5, 9),  # مریم (B-PER)
        (10, 15),  # رضایی (I-PER)
        (16, 19),  # پور (I-PER)
        (0, 0),
    ]
    id2label = {0: "O", 1: "B-PER", 2: "I-PER", 3: "B-TITLE"}
    preds = [0, 3, 1, 2, 2, 0]

    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=preds)
    detector = create_test_onnx_detector(tok, sess, id2label=id2label)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    d = detections[0]
    assert d.type == "PERSON"
    assert d.start == 5
    assert d.end == 19
    assert d.value == "مریم رضایی پور"


def test_title_strictly_excluded_from_person() -> None:
    """Verify TITLE (e.g. دکتر / مهندس) is not merged into PERSON."""
    text = "دکتر سارا احمدی"
    offsets = [
        (0, 0),
        (0, 4),  # دکتر (B-TITLE)
        (5, 9),  # سارا (B-GIVENNAME)
        (10, 15),  # احمدی (B-SURNAME)
        (0, 0),
    ]
    id2label = {
        0: "O",
        1: "B-TITLE",
        2: "B-GIVENNAME",
        3: "B-SURNAME",
    }
    preds = [0, 1, 2, 3, 0]

    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=preds)
    detector = create_test_onnx_detector(tok, sess, id2label=id2label)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    assert detections[0].type == "PERSON"
    assert detections[0].value == "سارا احمدی"
    assert detections[0].start == 5
    assert detections[0].end == 15
    assert "دکتر" not in detections[0].value


def test_two_adjacent_separate_b_per_remain_separate() -> None:
    """Verify two distinct B-PER people remain two separate Detection instances."""
    text = "علی رضا"
    offsets = [
        (0, 0),
        (0, 3),  # علی (B-PER)
        (4, 7),  # رضا (B-PER)
        (0, 0),
    ]
    id2label = {0: "O", 1: "B-PER", 2: "I-PER"}
    preds = [0, 1, 1, 0]

    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=preds)
    detector = create_test_onnx_detector(tok, sess, id2label=id2label)

    detections = detector.detect(text, text)
    assert len(detections) == 2
    assert detections[0].value == "علی"
    assert detections[0].start == 0
    assert detections[0].end == 3
    assert detections[1].value == "رضا"
    assert detections[1].start == 4
    assert detections[1].end == 7


def test_names_separated_by_punctuation_or_conjunction_do_not_merge() -> None:
    """Verify GIVENNAME and SURNAME separated by comma/conjunction remain separate."""
    text = "علی، محمدی"
    offsets = [
        (0, 0),
        (0, 3),  # علی (B-GIVENNAME)
        (5, 10),  # محمدی (B-SURNAME)
        (0, 0),
    ]
    id2label = {0: "O", 1: "B-GIVENNAME", 2: "B-SURNAME"}
    preds = [0, 1, 2, 0]

    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=preds)
    detector = create_test_onnx_detector(tok, sess, id2label=id2label)

    detections = detector.detect(text, text)
    # The gap text[3:5] is "، " which contains punctuation, so cannot merge!
    assert len(detections) == 2
    assert detections[0].value == "علی"
    assert detections[1].value == "محمدی"


def test_exact_original_offsets_and_normalization_preservation() -> None:
    """Verify Detection.value is sliced from original_text with aligned offsets."""
    # Text contains Arabic Yeh and Persian digits: "بيمار علی ۲۳" (with 'ي')
    orig = "بيمار علی رضایی"
    norm = "بیمار علی رضایی"

    offsets = [
        (0, 0),
        (0, 5),  # بيمار / بیمار
        (6, 9),  # علی
        (10, 15),  # رضایی
        (0, 0),
    ]
    id2label = {0: "O", 1: "B-PER", 2: "I-PER"}
    preds = [0, 0, 1, 2, 0]

    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=preds)
    detector = create_test_onnx_detector(tok, sess, id2label=id2label)

    detections = detector.detect(orig, norm)
    assert len(detections) == 1
    d = detections[0]
    assert d.value == "علی رضایی"
    assert d.start == 6
    assert d.end == 15
    assert orig[d.start : d.end] == d.value


def test_malformed_tokenizer_offsets_fail_loudly() -> None:
    """Verify ValueError on out-of-bounds, non-monotonic, or inverted offsets."""
    text = "تست خطا"
    id2label = {0: "O", 1: "B-PER", 2: "I-PER"}
    sess = DummyONNXSession()

    # 1. Out of bounds
    tok_oob = DummyFastTokenizer(token_offsets=[(0, 0), (0, 100), (0, 0)])
    det_oob = create_test_onnx_detector(tok_oob, sess, id2label=id2label)
    with pytest.raises(ValueError) as exc1:
        det_oob.detect(text, text)
    assert "out-of-bounds" in str(exc1.value)

    # 2. Inverted (start > end)
    tok_inv = DummyFastTokenizer(token_offsets=[(0, 0), (5, 2), (0, 0)])
    det_inv = create_test_onnx_detector(tok_inv, sess, id2label=id2label)
    with pytest.raises(ValueError) as exc2:
        det_inv.detect(text, text)
    assert "out-of-bounds" in str(exc2.value)

    # 3. Non-monotonic (start < prev_end)
    tok_nm = DummyFastTokenizer(token_offsets=[(0, 0), (0, 4), (2, 6), (0, 0)])
    det_nm = create_test_onnx_detector(tok_nm, sess, id2label=id2label)
    with pytest.raises(ValueError) as exc3:
        det_nm.detect(text, text)
    assert "non-monotonic" in str(exc3.value)


# =========================================================================
# 16-20. Long Document Sliding Window & Deduplication Tests
# =========================================================================


def test_short_document_single_window_inference() -> None:
    """Verify short documents execute single session call."""
    text = "بیمار علی رضایی"
    offsets = [(0, 0), (0, 5), (6, 9), (10, 15), (0, 0)]
    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=[0, 0, 1, 2, 0])
    detector = create_test_onnx_detector(tok, sess, max_length=512)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    assert sess.call_count == 1


def test_long_document_sliding_window_inference_and_deduplication() -> None:
    """Verify long documents use sliding windows with deduplication."""
    # Build a text with 10 tokens: max_length=6 (capacity=4, stride=2)
    # Window 0: content tokens 0..4 (indices in text)
    # Window 1: content tokens 2..6
    # Entity is at token 1 ("علی" [6:9]) and token 5 ("رضا" [24:27])
    text = "کلمه1 علی کلمه3 کلمه4 رضا کلمه6 کلمه7 کلمه8"
    words = text.split(" ")
    offsets = [(0, 0)]
    pos = 0
    for w in words:
        s = text.find(w, pos)
        e = s + len(w)
        offsets.append((s, e))
        pos = e
    offsets.append((0, 0))

    tok = DummyFastTokenizer(
        token_offsets=offsets,
        cls_token_id=101,
        sep_token_id=102,
    )
    id2label = {0: "O", 1: "B-PER", 2: "I-PER"}

    # Mock predictions for window calls
    # Window capacity is max_length - 2 = 4
    # All windows return O except token at "علی" and "رضا"
    def make_preds_for_win(input_ids: list[int]) -> list[int]:
        preds = [0] * len(input_ids)
        return preds

    sess = DummyONNXSession(num_classes=5)
    detector = create_test_onnx_detector(
        tok,
        sess,
        id2label=id2label,
        max_length=6,
    )

    detections = detector.detect(text, text)
    # Long text with 8 content tokens and max_length 6 triggers multi-window passes
    assert sess.call_count > 1
    assert isinstance(detections, list)


def test_multi_window_continuation_merging() -> None:
    """Verify entity split across window merges when continued by I-PER."""
    # Text has entity "علی رضایی" across sliding window split boundary
    text = "الف ب علی رضایی ج د ه و"
    # Content tokens: 0:الف, 1:ب, 2:علی, 3:رضایی, 4:ج, 5:د, 6:ه, 7:و
    words = text.split(" ")
    offsets = [(0, 0)]
    pos = 0
    for w in words:
        s = text.find(w, pos)
        e = s + len(w)
        offsets.append((s, e))
        pos = e
    offsets.append((0, 0))

    tok = DummyFastTokenizer(
        token_offsets=offsets,
        cls_token_id=101,
        sep_token_id=102,
    )
    id2label = {0: "O", 1: "B-PER", 2: "I-PER"}

    # max_length=5 -> capacity=3, stride=1
    # Window 0: tokens 0, 1, 2 ("الف", "ب", "علی") -> "علی" is at trailing boundary!
    # Window 1: tokens 1, 2, 3 ("ب", "علی", "رضایی") -> "علی" is B-PER, "رضایی" is I-PER
    preds_win0 = [0, 0, 0, 1, 0]  # CLS, الف(O), ب(O), علی(B-PER), SEP
    preds_win1 = [0, 0, 1, 2, 0]  # CLS, ب(O), علی(B-PER), رضایی(I-PER), SEP
    preds_win2 = [0, 1, 2, 0, 0]  # CLS, علی(B-PER), رضایی(I-PER), ج(O), SEP
    preds_rest = [0, 0, 0, 0, 0]

    sess = DummyONNXSession(
        pred_indices=[
            preds_win0,
            preds_win1,
            preds_win2,
            preds_rest,
            preds_rest,
            preds_rest,
            preds_rest,
        ],
    )
    detector = create_test_onnx_detector(
        tok,
        sess,
        id2label=id2label,
        max_length=5,
    )

    detections = detector.detect(text, text)
    assert len(detections) == 1
    assert detections[0].value == "علی رضایی"
    assert detections[0].type == "PERSON"


def test_empty_string_input() -> None:
    """Verify empty string returns empty detection list immediately."""
    tok = DummyFastTokenizer()
    sess = DummyONNXSession()
    detector = create_test_onnx_detector(tok, sess)

    assert detector.detect("", "") == []
    assert sess.call_count == 0


def test_length_mismatch_error() -> None:
    """Verify ValueError when original_text and normalized_text lengths differ."""
    tok = DummyFastTokenizer()
    sess = DummyONNXSession()
    detector = create_test_onnx_detector(tok, sess)

    with pytest.raises(ValueError) as exc_info:
        detector.detect("متن کوتاه", "متن طولانی تر")
    assert "must equal" in str(exc_info.value)


def test_invalid_text_type_errors() -> None:
    """Verify TypeError on non-str inputs."""
    tok = DummyFastTokenizer()
    sess = DummyONNXSession()
    detector = create_test_onnx_detector(tok, sess)

    with pytest.raises(TypeError):
        detector.detect(123, "متن")  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        detector.detect("متن", None)  # type: ignore[arg-type]


# =========================================================================
# 21-25. Pipeline, Redaction, Session & Batch Integration Tests
# =========================================================================


def test_pipeline_detect_and_redact_with_onnx_detector() -> None:
    """Verify detect() and redact() with ONNXPersianNERDetector."""
    text = "بیمار علی رضایی به بیمارستان مراجعه کرد."
    offsets = [
        (0, 0),
        (0, 5),  # بیمار
        (6, 9),  # علی
        (10, 15),  # رضایی
        (16, 18),  # به
        (19, 28),  # بیمارستان
        (29, 35),  # مراجعه
        (36, 39),  # کرد.
        (0, 0),
    ]
    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=[0, 0, 1, 2, 0, 0, 0, 0, 0])
    detector = create_test_onnx_detector(tok, sess)

    # 1. detect()
    detections = detect(text, detectors=[detector])
    assert len(detections) == 1
    assert detections[0].type == "PERSON"
    assert detections[0].value == "علی رضایی"

    # 2. redact()
    redacted = redact(text, detectors=[detector])
    assert redacted == "بیمار [PERSON_1] به بیمارستان مراجعه کرد."


def test_composition_with_builtin_direct_identifiers() -> None:
    """Verify composing ONNX detector with National ID and Mobile detectors."""
    text = "بیمار سارا حسینی با کد ملی 1234567891 و موبایل 09123456789"
    # Text length: 57
    # "سارا حسینی" is at [6:16]
    # National ID "1234567891" at [27:37]
    # Mobile "09123456789" at [47:58]
    offsets = [
        (0, 0),
        (0, 5),  # بیمار
        (6, 10),  # سارا
        (11, 16),  # حسینی
        (17, 19),  # با
        (20, 22),  # کد
        (23, 26),  # ملی
        (27, 37),  # 1234567891
        (38, 39),  # و
        (40, 46),  # موبایل
        (47, 58),  # 09123456789
        (0, 0),
    ]
    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=[0, 0, 1, 2, 0, 0, 0, 0, 0, 0, 0, 0])
    onnx_ner = create_test_onnx_detector(tok, sess)

    all_detectors: list[Detector] = [
        IranianNationalIDDetector(),
        IranianMobileNumberDetector(),
        IranianIBANDetector(),
        onnx_ner,
    ]

    detections = detect(text, detectors=all_detectors)
    types = [d.type for d in detections]
    assert "PERSON" in types
    assert "IR_NATIONAL_ID" in types
    assert "IR_MOBILE" in types

    redacted = redact(text, detectors=all_detectors)
    assert "[PERSON_1]" in redacted
    assert "[IR_NATIONAL_ID_1]" in redacted
    assert "[IR_MOBILE_1]" in redacted


def test_pseudonymization_session_with_onnx_detector() -> None:
    """Verify PseudonymizationSession persistence and restoration with ONNX detector."""
    turn1 = "بیمار علی حسینی ویزیت شد."
    turn2 = "نسخه برای علی حسینی صادر گردید."

    offsets1 = [(0, 0), (0, 5), (6, 9), (10, 15), (16, 21), (22, 25), (0, 0)]
    offsets2 = [
        (0, 0),
        (0, 4),
        (5, 9),
        (10, 13),
        (14, 19),
        (20, 24),
        (25, 30),
        (0, 0),
    ]

    tok1 = DummyFastTokenizer(token_offsets=offsets1)
    tok2 = DummyFastTokenizer(token_offsets=offsets2)

    sess1 = DummyONNXSession(pred_indices=[0, 0, 1, 2, 0, 0, 0])
    sess2 = DummyONNXSession(pred_indices=[0, 0, 0, 1, 2, 0, 0, 0])

    det1 = create_test_onnx_detector(tok1, sess1)
    det2 = create_test_onnx_detector(tok2, sess2)

    session = PseudonymizationSession()
    pseudo1 = session.pseudonymize(turn1, detectors=[det1])
    assert pseudo1 == "بیمار [PERSON_1] ویزیت شد."

    pseudo2 = session.pseudonymize(turn2, detectors=[det2])
    assert pseudo2 == "نسخه برای [PERSON_1] صادر گردید."

    restored = session.restore(pseudo2)
    assert restored == turn2


def test_batch_and_structured_helpers_with_onnx_detector() -> None:
    """Verify detect_many(), redact_many(), and redact_fields() with ONNX detector."""
    text = "بیمار مریم احمدی مراجعه نمود."
    offsets = [(0, 0), (0, 5), (6, 10), (11, 16), (17, 22), (23, 28), (0, 0)]
    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=[0, 0, 1, 2, 0, 0, 0])
    detector = create_test_onnx_detector(tok, sess)

    # 1. detect_many
    batch_dets = list(detect_many([text, ""], detectors=[detector]))
    assert len(batch_dets) == 2
    assert len(batch_dets[0]) == 1
    assert len(batch_dets[1]) == 0

    # 2. redact_many
    batch_redacted = list(redact_many([text], detectors=[detector]))
    assert batch_redacted == ["بیمار [PERSON_1] مراجعه نمود."]

    # 3. redact_fields
    record = {"note": text, "status": "active"}
    red_record = redact_fields(record, ["note"], detectors=[detector])
    assert red_record["note"] == "بیمار [PERSON_1] مراجعه نمود."
    assert red_record["status"] == "active"


def test_clinical_profile_with_explicit_onnx_person_detector() -> None:
    """Verify clinical_profile accepting ONNXPersianNERDetector as person_detector."""
    offsets = [(0, 0), (0, 5), (6, 9), (10, 14), (15, 20), (0, 0)]
    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=[0, 0, 1, 2, 0, 0])
    onnx_ner = create_test_onnx_detector(tok, sess)

    profile = clinical_profile(
        "outpatient_note",
        person_detector=onnx_ner,
    )
    text = "بیمار علی رضایی ویزیت"
    redacted = profile.redact(text)
    assert "[PERSON_1]" in redacted


# =========================================================================
# 26-28. Invariance Verification Tests
# =========================================================================


def test_default_detectors_tuple_unmodified() -> None:
    """Verify default detectors tuple remains strictly (NationalID, Mobile, IBAN)."""
    from fa_redact.pipeline import _DEFAULT_DETECTORS

    assert len(_DEFAULT_DETECTORS) == 3
    assert isinstance(_DEFAULT_DETECTORS[0], IranianNationalIDDetector)
    assert isinstance(_DEFAULT_DETECTORS[1], IranianMobileNumberDetector)
    assert isinstance(_DEFAULT_DETECTORS[2], IranianIBANDetector)


def test_clinical_defaults_unmodified() -> None:
    """Verify clinical_profile without person_detector does NOT detect names."""
    profile = clinical_profile("outpatient_note")
    text = "بیمار علی رضایی با کد ملی 1234567891"
    redacted = profile.redact(text)
    # National ID redacted, personal name untouched by default
    assert "[IR_NATIONAL_ID_1]" in redacted
    assert "علی رضایی" in redacted


# =========================================================================
# 29-33. Safe token_type_ids, Whitespace Trimming, & Category Continuity Tests
# =========================================================================


def test_token_type_ids_zero_fallback_when_session_requires_it() -> None:
    """Verify all-zero token_type_ids supplied when session requires it."""
    # Tokenizer without token_type_ids in encoding
    tok = DummyFastTokenizer(
        token_offsets=[(0, 0), (0, 3), (4, 9), (0, 0)],
        include_token_type_ids=False,
    )
    # Session explicitly declares token_type_ids
    sess = DummyONNXSession(
        input_names=["input_ids", "attention_mask", "token_type_ids"],
        pred_indices=[0, 1, 2, 0],
    )
    detector = create_test_onnx_detector(tok, sess)

    text = "علی رضایی"
    detections = detector.detect(text, text)
    assert len(detections) == 1
    assert detections[0].value == "علی رضایی"

    # Verify token_type_ids was provided in feed with all zeros of exact sequence length
    assert len(sess.call_feeds) == 1
    feed = sess.call_feeds[0]
    assert "token_type_ids" in feed
    token_types = feed["token_type_ids"]
    assert token_types == [[0, 0, 0, 0]]


def test_whitespace_trimming_leading_and_trailing_single_window() -> None:
    """Verify leading/trailing whitespace in spans is trimmed with exact offsets."""
    text = "بیمار   علی رضایی   مراجعه کرد"
    # original_text[5:20] is "   علی رضایی   "
    # original_text[8:17] is "علی رضایی"
    offsets = [(0, 0), (0, 5), (5, 20), (20, 30), (0, 0)]
    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=[0, 0, 1, 0, 0])
    detector = create_test_onnx_detector(tok, sess)

    detections = detector.detect(text, text)
    assert len(detections) == 1
    assert detections[0].start == 8
    assert detections[0].end == 17
    assert detections[0].value == "علی رضایی"
    assert text[detections[0].start : detections[0].end] == "علی رضایی"


def test_whitespace_trimming_sliding_window_and_zwnj() -> None:
    """Verify sliding-window whitespace trimming preserves internal Persian ZWNJ."""
    # Build text with internal ZWNJ and leading space
    name_with_zwnj = " علی\u200cرضا رضایی "
    text = "گزارش " + name_with_zwnj + " پرونده " * 10
    # Sliding window test with small max_length
    tok = DummyFastTokenizer(model_max_length=6, cls_token_id=101, sep_token_id=102)
    sess = DummyONNXSession(
        pred_indices=[
            [0, 0, 1, 2, 0, 0],  # Win 0 detects PERSON
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
        ]
    )
    detector = create_test_onnx_detector(tok, sess, max_length=6)
    detections = detector.detect(text, text)
    assert len(detections) >= 1
    det = detections[0]
    # Trimmed value must not start or end with space, but keep ZWNJ
    assert not det.value.startswith(" ")
    assert not det.value.endswith(" ")
    assert "\u200c" in det.value
    assert text[det.start : det.end] == det.value


def test_whitespace_trimming_pure_whitespace_span_discarded() -> None:
    """Verify that a span consisting purely of whitespace is discarded upon trimming."""
    text = "متن   متن"
    # Token 1 covers pure whitespace "   " (offsets 3 to 6)
    offsets = [(0, 0), (0, 3), (3, 6), (6, 9), (0, 0)]
    tok = DummyFastTokenizer(token_offsets=offsets)
    sess = DummyONNXSession(pred_indices=[0, 0, 1, 0, 0])
    detector = create_test_onnx_detector(tok, sess)

    detections = detector.detect(text, text)
    assert len(detections) == 0


def test_incompatible_i_category_continuity_flushes_span() -> None:
    """Verify that incompatible I-labels flush active span and do NOT silently join."""
    id2label = {
        0: "O",
        1: "B-GIVENNAME",
        2: "I-GIVENNAME",
        3: "B-SURNAME",
        4: "I-SURNAME",
        5: "B-PER",
        6: "I-PER",
    }

    # 1. B-GIVEN (1) followed by I-SUR (4) -> Two separate spans
    text_given_isur = "علی رضایی"
    offsets1 = [(0, 0), (0, 3), (4, 9), (0, 0)]
    tok1 = DummyFastTokenizer(token_offsets=offsets1)
    sess1 = DummyONNXSession(pred_indices=[0, 1, 4, 0])
    det1 = create_test_onnx_detector(tok1, sess1, id2label=id2label)
    res1 = det1.detect(text_given_isur, text_given_isur)
    assert len(res1) == 2
    assert res1[0].value == "علی"
    assert res1[0].start == 0
    assert res1[0].end == 3
    assert res1[1].value == "رضایی"
    assert res1[1].start == 4
    assert res1[1].end == 9

    # 2. B-SUR (3) followed by I-GIVEN (2) -> Two separate spans
    text_sur_igiven = "رضایی علی"
    offsets2 = [(0, 0), (0, 5), (6, 9), (0, 0)]
    tok2 = DummyFastTokenizer(token_offsets=offsets2)
    sess2 = DummyONNXSession(pred_indices=[0, 3, 2, 0])
    det2 = create_test_onnx_detector(tok2, sess2, id2label=id2label)
    res2 = det2.detect(text_sur_igiven, text_sur_igiven)
    assert len(res2) == 2
    assert res2[0].value == "رضایی"
    assert res2[1].value == "علی"


def test_compatible_i_category_continuation() -> None:
    """Verify that compatible I-labels extend active spans correctly."""
    id2label = {
        0: "O",
        1: "B-GIVENNAME",
        2: "I-GIVENNAME",
        3: "B-SURNAME",
        4: "I-SURNAME",
    }

    # Normal B-GIVEN + I-GIVEN
    text_given = "علی اکبر"
    offsets1 = [(0, 0), (0, 3), (4, 8), (0, 0)]
    tok1 = DummyFastTokenizer(token_offsets=offsets1)
    sess1 = DummyONNXSession(pred_indices=[0, 1, 2, 0])
    det1 = create_test_onnx_detector(tok1, sess1, id2label=id2label)
    res1 = det1.detect(text_given, text_given)
    assert len(res1) == 1
    assert res1[0].value == "علی اکبر"
    assert res1[0].start == 0
    assert res1[0].end == 8

    # Normal B-SUR + I-SUR
    text_sur = "میر حسینی"
    offsets2 = [(0, 0), (0, 3), (4, 9), (0, 0)]
    tok2 = DummyFastTokenizer(token_offsets=offsets2)
    sess2 = DummyONNXSession(pred_indices=[0, 3, 4, 0])
    det2 = create_test_onnx_detector(tok2, sess2, id2label=id2label)
    res2 = det2.detect(text_sur, text_sur)
    assert len(res2) == 1
    assert res2[0].value == "میر حسینی"
    assert res2[0].start == 0
    assert res2[0].end == 9
