"""Opt-in ONNX Runtime detector for Persian personal name (PERSON) entities."""

from __future__ import annotations

import importlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fa_redact.detectors._ner_utils import (
    _SpanCandidate,
    merge_and_deduplicate_candidates,
    validate_tokenizer_offsets,
)
from fa_redact.models import Detection

_ENTITY_TYPE: str = "PERSON"
_MAX_CREDIBLE_POSITION_LIMIT: int = 100_000

# Supported BIO label prefixes and normalization maps
_B_PER_VARIANTS: frozenset[str] = frozenset({"B-PER", "B-PERSON"})
_I_PER_VARIANTS: frozenset[str] = frozenset({"I-PER", "I-PERSON"})
_B_GIVEN_VARIANTS: frozenset[str] = frozenset({"B-GIVENNAME", "B-FIRSTNAME"})
_I_GIVEN_VARIANTS: frozenset[str] = frozenset({"I-GIVENNAME", "I-FIRSTNAME"})
_B_SUR_VARIANTS: frozenset[str] = frozenset({"B-SURNAME", "B-LASTNAME"})
_I_SUR_VARIANTS: frozenset[str] = frozenset({"I-SURNAME", "I-LASTNAME"})


def _trim_span_whitespace(start: int, end: int, text: str) -> tuple[int, int] | None:
    """Trim leading and trailing Unicode whitespace from a character offset span.

    Adjusts start and end using text directly. Does not trim internal characters
    such as Persian ZWNJ. Returns (trimmed_start, trimmed_end) or None if the
    trimmed span is empty.
    """
    s = start
    e = end
    text_len = len(text)
    s = max(0, min(s, text_len))
    e = max(s, min(e, text_len))

    while s < e and text[s].isspace():
        s += 1
    while e > s and text[e - 1].isspace():
        e -= 1

    if s >= e:
        return None
    return (s, e)


class ONNXPersianNERDetector:
    """Opt-in detector for Persian personal name (PERSON) entities using ONNX Runtime.

    Uses an explicitly supplied local ONNX model directory to perform offline
    PERSON named-entity recognition. Operates on position-preserving normalized text
    and emits exact source-aligned Detection instances.
    """

    def __init__(
        self,
        model_path: str | Path,
        *,
        max_length: int = 512,
    ) -> None:
        """Initialize ONNXPersianNERDetector from a local model directory.

        Args:
            model_path: Local filesystem path to ONNX model directory.
            max_length: Maximum tokenized sequence length (positive integer).

        Raises:
            TypeError: If arguments are of incorrect types.
            ValueError: If max_length is non-positive, exceeds model position limits,
                exceeds tokenizer maximum length, or model labels are incompatible.
            FileNotFoundError: If model_path does not exist or no ONNX model is found.
            NotADirectoryError: If model_path is not a directory.
            ImportError: If optional 'onnx' dependencies are not installed.
        """
        if (
            isinstance(max_length, bool)
            or not isinstance(max_length, int)
            or max_length <= 0
        ):
            raise ValueError(
                f"max_length must be a positive integer, got {max_length!r}"
            )

        if not isinstance(model_path, (str, Path)):
            raise TypeError(
                f"model_path must be a str or Path, got {type(model_path).__name__}"
            )

        resolved_path = Path(model_path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Local model path does not exist: {model_path}")
        if not resolved_path.is_dir():
            raise NotADirectoryError(
                f"Local model path is not a directory: {model_path}"
            )

        try:
            np = importlib.import_module("numpy")
            ort = importlib.import_module("onnxruntime")
            transformers = importlib.import_module("transformers")
        except ImportError as exc:
            raise ImportError(
                "ONNXPersianNERDetector requires optional dependencies. "
                'Install them with: pip install "fa-redact[onnx]"'
            ) from exc

        AutoTokenizer = getattr(transformers, "AutoTokenizer", None)
        if AutoTokenizer is None:
            raise ImportError(
                "ONNXPersianNERDetector requires optional dependencies with "
                "AutoTokenizer. "
                'Install them with: pip install "fa-redact[onnx]"'
            )

        # Locate ONNX model file under resolved_path
        onnx_file = resolved_path / "model.onnx"
        if not onnx_file.is_file():
            onnx_files = sorted(resolved_path.glob("*.onnx"))
            if len(onnx_files) == 1:
                onnx_file = onnx_files[0]
            elif len(onnx_files) == 0:
                raise FileNotFoundError(
                    f"No ONNX model file (*.onnx) found in directory: {model_path}"
                )
            else:
                raise ValueError(
                    "Multiple ONNX model files found in directory without "
                    f"'model.onnx': {[f.name for f in onnx_files]}"
                )

        tokenizer = AutoTokenizer.from_pretrained(
            str(resolved_path),
            local_files_only=True,
            trust_remote_code=False,
        )
        if not getattr(tokenizer, "is_fast", False):
            raise ValueError(
                "ONNXPersianNERDetector requires a fast tokenizer (is_fast=True) "
                "with character offset mapping support"
            )

        # Read model configuration (config.json)
        id2label_raw: Any = None
        max_pos_embed: int | None = None
        config_file = resolved_path / "config.json"
        if config_file.is_file():
            try:
                config_data = json.loads(config_file.read_text(encoding="utf-8"))
                if isinstance(config_data, dict):
                    id2label_raw = config_data.get("id2label")
                    raw_pos = config_data.get("max_position_embeddings")
                    if (
                        isinstance(raw_pos, int)
                        and not isinstance(raw_pos, bool)
                        and raw_pos > 0
                    ):
                        max_pos_embed = raw_pos
            except Exception as exc:
                raise ValueError(
                    f"Failed to parse config.json in {model_path}"
                ) from exc

        if id2label_raw is None:
            AutoConfig = getattr(transformers, "AutoConfig", None)
            if AutoConfig is not None:
                try:
                    cfg = AutoConfig.from_pretrained(
                        str(resolved_path),
                        local_files_only=True,
                        trust_remote_code=False,
                    )
                    id2label_raw = getattr(cfg, "id2label", None)
                    if max_pos_embed is None:
                        raw_pos = getattr(cfg, "max_position_embeddings", None)
                        if (
                            isinstance(raw_pos, int)
                            and not isinstance(raw_pos, bool)
                            and raw_pos > 0
                        ):
                            max_pos_embed = raw_pos
                except Exception:
                    pass

        if not id2label_raw or not isinstance(id2label_raw, dict):
            raise ValueError(
                f"Model configuration in '{model_path}' "
                "missing required 'id2label' mapping"
            )

        try:
            id2label: dict[int, str] = {int(k): str(v) for k, v in id2label_raw.items()}
        except (ValueError, TypeError) as e:
            raise ValueError(
                "Invalid non-numeric keys in model id2label mapping"
            ) from e

        session_options = ort.SessionOptions()
        session = ort.InferenceSession(
            str(onnx_file),
            sess_options=session_options,
            providers=["CPUExecutionProvider"],
        )

        self._init_from_components(
            model_path=resolved_path,
            tokenizer=tokenizer,
            session=session,
            id2label=id2label,
            max_length=max_length,
            max_position_embeddings=max_pos_embed,
            np_module=np,
        )

    @classmethod
    def _create_for_test(
        cls,
        tokenizer: Any,
        session: Any,
        *,
        id2label: dict[Any, str] | None = None,
        max_length: int = 512,
        max_position_embeddings: int | None = 512,
        np_module: Any = None,
    ) -> ONNXPersianNERDetector:
        """Internal constructor for testing without loading files from disk."""
        instance = cls.__new__(cls)
        default_id2label = id2label or {
            0: "O",
            1: "B-PER",
            2: "I-PER",
        }
        parsed_id2label = {int(k): str(v) for k, v in default_id2label.items()}
        instance._init_from_components(
            model_path=Path("fake_onnx_model"),
            tokenizer=tokenizer,
            session=session,
            id2label=parsed_id2label,
            max_length=max_length,
            max_position_embeddings=max_position_embeddings,
            np_module=np_module,
        )
        return instance

    def _init_from_components(
        self,
        model_path: Path,
        tokenizer: Any,
        session: Any,
        id2label: dict[int, str],
        max_length: int,
        max_position_embeddings: int | None,
        np_module: Any,
    ) -> None:
        """Validate components and initialize detector state."""
        if (
            isinstance(max_length, bool)
            or not isinstance(max_length, int)
            or max_length <= 0
        ):
            raise ValueError(
                f"max_length must be a positive integer, got {max_length!r}"
            )

        if (
            max_position_embeddings is not None
            and isinstance(max_position_embeddings, int)
            and not isinstance(max_position_embeddings, bool)
            and 0 < max_position_embeddings <= _MAX_CREDIBLE_POSITION_LIMIT
        ):
            if max_length > max_position_embeddings:
                raise ValueError(
                    f"Configured max_length ({max_length}) exceeds model "
                    f"positional capacity ({max_position_embeddings})"
                )

        tok_max_len = getattr(tokenizer, "model_max_length", None)
        if (
            tok_max_len is not None
            and isinstance(tok_max_len, int)
            and not isinstance(tok_max_len, bool)
            and 0 < tok_max_len <= _MAX_CREDIBLE_POSITION_LIMIT
        ):
            if max_length > tok_max_len:
                raise ValueError(
                    f"Configured max_length ({max_length}) exceeds tokenizer "
                    f"maximum sequence length ({tok_max_len})"
                )

        b_per_ids: set[int] = set()
        i_per_ids: set[int] = set()
        b_given_ids: set[int] = set()
        i_given_ids: set[int] = set()
        b_sur_ids: set[int] = set()
        i_sur_ids: set[int] = set()

        for idx, label_str in id2label.items():
            norm_label = label_str.strip().upper().replace("_", "-")
            if norm_label in _B_PER_VARIANTS:
                b_per_ids.add(idx)
            elif norm_label in _I_PER_VARIANTS:
                i_per_ids.add(idx)
            elif norm_label in _B_GIVEN_VARIANTS:
                b_given_ids.add(idx)
            elif norm_label in _I_GIVEN_VARIANTS:
                i_given_ids.add(idx)
            elif norm_label in _B_SUR_VARIANTS:
                b_sur_ids.add(idx)
            elif norm_label in _I_SUR_VARIANTS:
                i_sur_ids.add(idx)

        has_person_labels = bool(b_per_ids or b_given_ids or b_sur_ids)
        if not has_person_labels:
            raise ValueError(
                f"Model at '{model_path}' missing required person-name label "
                f"configuration (available labels: {sorted(set(id2label.values()))})"
            )

        self._model_path = model_path
        self._max_length = max_length
        self._tokenizer = tokenizer
        self._session = session
        self._id2label = id2label
        self._b_per_ids = frozenset(b_per_ids)
        self._i_per_ids = frozenset(i_per_ids)
        self._b_given_ids = frozenset(b_given_ids)
        self._i_given_ids = frozenset(i_given_ids)
        self._b_sur_ids = frozenset(b_sur_ids)
        self._i_sur_ids = frozenset(i_sur_ids)
        self._np = np_module

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        """Detect PERSON entities across source texts using ONNX Runtime.

        For sequences that fit within `max_length`, runs a single ONNX forward pass.
        For sequences exceeding `max_length`, runs deterministic overlapping
        sliding-window inference and merges PERSON detections with exact source
        offsets.

        Args:
            original_text: Raw input text.
            normalized_text: Position-preserving normalized text of identical length.

        Returns:
            Sequence of Detection instances with type="PERSON" sorted
            by (start, end, type).

        Raises:
            TypeError: If original_text or normalized_text is not a str.
            ValueError: If text lengths differ or tokenizer character
                offsets are structurally invalid.
        """
        if not isinstance(original_text, str):
            raise TypeError(
                f"original_text must be a str, got {type(original_text).__name__}"
            )
        if not isinstance(normalized_text, str):
            raise TypeError(
                f"normalized_text must be a str, got {type(normalized_text).__name__}"
            )

        if len(original_text) != len(normalized_text):
            raise ValueError(
                f"original_text length ({len(original_text)}) must equal "
                f"normalized_text length ({len(normalized_text)})"
            )

        if not original_text:
            return []

        # Tokenize normalized_text without truncation to inspect full sequence length
        full_encoding = self._tokenizer(
            normalized_text,
            return_offsets_mapping=True,
            add_special_tokens=True,
        )

        input_ids_list: list[int] = full_encoding["input_ids"]
        token_offsets: list[tuple[int, int]] = full_encoding["offset_mapping"]
        text_len = len(normalized_text)

        # Structural tokenizer offset safety audit on full sequence
        validate_tokenizer_offsets(token_offsets, text_len)

        seq_len = len(input_ids_list)

        # 1. Single window pass if input fits within max_length
        if seq_len <= self._max_length:
            return self._detect_single_window(
                original_text=original_text,
                normalized_text=normalized_text,
                input_ids_list=input_ids_list,
                token_offsets=token_offsets,
                full_encoding=full_encoding,
            )

        # 2. Multi-window sliding window pass for long documents
        return self._detect_sliding_window(
            original_text=original_text,
            normalized_text=normalized_text,
            input_ids_list=input_ids_list,
            token_offsets=token_offsets,
            full_encoding=full_encoding,
        )

    def _run_session(
        self,
        input_ids_list: list[int],
        attention_mask_list: list[int],
        token_type_ids_list: list[int] | None = None,
    ) -> list[int]:
        """Execute ONNX inference session and return argmax prediction indices."""
        session_inputs: list[str] = []
        if hasattr(self._session, "get_inputs"):
            session_inputs = [inp.name for inp in self._session.get_inputs()]

        feed: dict[str, Any] = {}
        seq_len = len(input_ids_list)
        np_mod = self._np
        if np_mod is not None:
            feed["input_ids"] = np_mod.array([input_ids_list], dtype=np_mod.int64)
            if "attention_mask" in session_inputs or not session_inputs:
                feed["attention_mask"] = np_mod.array(
                    [attention_mask_list], dtype=np_mod.int64
                )
            if "token_type_ids" in session_inputs:
                if token_type_ids_list is not None:
                    feed["token_type_ids"] = np_mod.array(
                        [token_type_ids_list], dtype=np_mod.int64
                    )
                else:
                    feed["token_type_ids"] = np_mod.zeros(
                        (1, seq_len), dtype=np_mod.int64
                    )
            elif token_type_ids_list is not None and not session_inputs:
                feed["token_type_ids"] = np_mod.array(
                    [token_type_ids_list], dtype=np_mod.int64
                )
        else:
            # Fallback for lightweight testing without full numpy
            feed["input_ids"] = [input_ids_list]
            if "attention_mask" in session_inputs or not session_inputs:
                feed["attention_mask"] = [attention_mask_list]
            if "token_type_ids" in session_inputs:
                if token_type_ids_list is not None:
                    feed["token_type_ids"] = [token_type_ids_list]
                else:
                    feed["token_type_ids"] = [[0] * seq_len]
            elif token_type_ids_list is not None and not session_inputs:
                feed["token_type_ids"] = [token_type_ids_list]

        outputs = self._session.run(None, feed)
        logits = outputs[0]

        # Extract argmax across classes for batch element 0
        if np_mod is not None and hasattr(logits, "ndim"):
            if logits.ndim == 3:
                return np_mod.argmax(logits[0], axis=-1).tolist()  # type: ignore[no-any-return]
            return np_mod.argmax(logits, axis=-1).tolist()  # type: ignore[no-any-return]

        # Nested list fallback
        if isinstance(logits, list) and logits and isinstance(logits[0], list):
            first_elem = logits[0]
            if first_elem and isinstance(first_elem[0], list):
                # 3D list: [batch, seq, classes]
                return [
                    max(range(len(step)), key=lambda c: step[c]) for step in first_elem
                ]
            # 2D list: [seq, classes]
            return [max(range(len(step)), key=lambda c: step[c]) for step in logits]

        return []

    def _detect_single_window(
        self,
        original_text: str,
        normalized_text: str,
        input_ids_list: list[int],
        token_offsets: list[tuple[int, int]],
        full_encoding: dict[str, Any],
    ) -> list[Detection]:
        """Run single forward pass for sequences fitting within max_length."""
        attention_mask = full_encoding.get("attention_mask", [1] * len(input_ids_list))
        token_type_ids = full_encoding.get("token_type_ids")

        pred_indices = self._run_session(
            input_ids_list=input_ids_list,
            attention_mask_list=attention_mask,
            token_type_ids_list=token_type_ids,
        )

        return self._extract_detections_from_predictions(
            original_text=original_text,
            normalized_text=normalized_text,
            token_offsets=token_offsets,
            pred_indices=pred_indices,
        )

    def _detect_sliding_window(
        self,
        original_text: str,
        normalized_text: str,
        input_ids_list: list[int],
        token_offsets: list[tuple[int, int]],
        full_encoding: dict[str, Any],
    ) -> list[Detection]:
        """Run sliding-window forward passes for long documents exceeding max_length."""
        if self._max_length < 3:
            raise ValueError(
                f"Configured max_length ({self._max_length}) is too small for "
                "sliding-window inference; requires at least 3 tokens for "
                "[CLS] + content + [SEP]"
            )

        # Separate content tokens from special tokens
        content_tokens: list[int] = []
        content_offsets: list[tuple[int, int]] = []
        content_type_ids: list[int] = []
        raw_type_ids = full_encoding.get("token_type_ids")

        for i, (offset, tok_id) in enumerate(
            zip(token_offsets, input_ids_list, strict=True)
        ):
            if offset == (0, 0):
                continue
            content_tokens.append(tok_id)
            content_offsets.append(offset)
            if raw_type_ids is not None:
                content_type_ids.append(raw_type_ids[i])

        if not content_tokens:
            return []

        # Identify special tokens without guessing fabricated token IDs
        cls_token_id = getattr(self._tokenizer, "cls_token_id", None)
        if cls_token_id is None:
            if token_offsets and token_offsets[0] == (0, 0):
                cls_token_id = input_ids_list[0]
            else:
                raise ValueError(
                    "Tokenizer missing required special token configuration "
                    "(cls_token_id) for sliding-window inference"
                )

        sep_token_id = getattr(self._tokenizer, "sep_token_id", None)
        if sep_token_id is None:
            if token_offsets and token_offsets[-1] == (0, 0):
                sep_token_id = input_ids_list[-1]
            else:
                raise ValueError(
                    "Tokenizer missing required special token configuration "
                    "(sep_token_id) for sliding-window inference"
                )

        window_capacity = self._max_length - 2
        stride = max(1, window_capacity // 2)
        num_content = len(content_tokens)

        windows: list[tuple[int, int]] = []
        w_start = 0
        while w_start < num_content:
            w_end = min(w_start + window_capacity, num_content)
            windows.append((w_start, w_end))
            if w_end >= num_content:
                break
            w_start += stride

        candidates: list[_SpanCandidate] = []

        for window_idx, (win_start, win_end) in enumerate(windows):
            win_content_ids = content_tokens[win_start:win_end]
            win_content_offsets = content_offsets[win_start:win_end]

            w_ids = [cls_token_id] + win_content_ids + [sep_token_id]
            w_mask = [1] * len(w_ids)
            w_types: list[int] | None = None
            if raw_type_ids is not None:
                w_types = [0] + content_type_ids[win_start:win_end] + [0]

            pred_indices = self._run_session(
                input_ids_list=w_ids,
                attention_mask_list=w_mask,
                token_type_ids_list=w_types,
            )

            # Content token predictions start at index 1
            win_preds = pred_indices[1 : 1 + len(win_content_ids)]
            win_candidates = self._extract_window_candidates(
                original_text=original_text,
                content_offsets=win_content_offsets,
                win_preds=win_preds,
                window_idx=window_idx,
            )
            candidates.extend(win_candidates)

        merged_spans = merge_and_deduplicate_candidates(candidates, original_text)

        detections: list[Detection] = []
        for s, e in merged_spans:
            trimmed = _trim_span_whitespace(s, e, original_text)
            if trimmed is not None:
                ts, te = trimmed
                detections.append(
                    Detection.from_texts(
                        type=_ENTITY_TYPE,
                        original_text=original_text,
                        normalized_text=normalized_text,
                        start=ts,
                        end=te,
                    )
                )
        detections.sort(key=lambda d: (d.start, d.end, d.type))
        return detections

    def _extract_window_candidates(
        self,
        original_text: str,
        content_offsets: list[tuple[int, int]],
        win_preds: list[int],
        window_idx: int,
    ) -> list[_SpanCandidate]:
        """Extract candidate PERSON spans for a single sliding window."""
        candidates: list[_SpanCandidate] = []
        active_s: int | None = None
        active_e: int | None = None
        active_cat: str | None = None  # "PER", "GIVEN", "SUR"
        active_leading_i = False

        def _is_gap_whitespace_only(s1: int, s2: int) -> bool:
            if s1 >= s2:
                return True
            gap_str = original_text[s1:s2]
            return gap_str.strip(" \t\n\r\u200c\u200b\u200d") == ""

        for j, (offset, pred_id) in enumerate(
            zip(content_offsets, win_preds, strict=True)
        ):
            s, e = offset

            is_b_per = pred_id in self._b_per_ids
            is_i_per = pred_id in self._i_per_ids
            is_b_given = pred_id in self._b_given_ids
            is_i_given = pred_id in self._i_given_ids
            is_b_sur = pred_id in self._b_sur_ids
            is_i_sur = pred_id in self._i_sur_ids

            if is_b_per:
                if active_s is not None and active_e is not None:
                    candidates.append(
                        _SpanCandidate(
                            start=active_s,
                            end=active_e,
                            is_leading_continuation=active_leading_i,
                            is_trailing_boundary=False,
                            window_idx=window_idx,
                        )
                    )
                active_s = s
                active_e = e
                active_cat = "PER"
                active_leading_i = False

            elif is_b_given:
                # Compatible sequence: SURNAME + GIVENNAME across whitespace only
                if (
                    active_s is not None
                    and active_e is not None
                    and active_cat == "SUR"
                    and _is_gap_whitespace_only(active_e, s)
                ):
                    active_e = e
                    active_cat = "GIVEN"
                else:
                    if active_s is not None and active_e is not None:
                        candidates.append(
                            _SpanCandidate(
                                start=active_s,
                                end=active_e,
                                is_leading_continuation=active_leading_i,
                                is_trailing_boundary=False,
                                window_idx=window_idx,
                            )
                        )
                    active_s = s
                    active_e = e
                    active_cat = "GIVEN"
                    active_leading_i = False

            elif is_b_sur:
                # Compatible sequence: GIVENNAME + SURNAME across whitespace only
                if (
                    active_s is not None
                    and active_e is not None
                    and active_cat == "GIVEN"
                    and _is_gap_whitespace_only(active_e, s)
                ):
                    active_e = e
                    active_cat = "SUR"
                else:
                    if active_s is not None and active_e is not None:
                        candidates.append(
                            _SpanCandidate(
                                start=active_s,
                                end=active_e,
                                is_leading_continuation=active_leading_i,
                                is_trailing_boundary=False,
                                window_idx=window_idx,
                            )
                        )
                    active_s = s
                    active_e = e
                    active_cat = "SUR"
                    active_leading_i = False

            elif is_i_per:
                if (
                    active_s is not None
                    and active_e is not None
                    and active_cat == "PER"
                    and _is_gap_whitespace_only(active_e, s)
                ):
                    active_e = e
                else:
                    if active_s is not None and active_e is not None:
                        candidates.append(
                            _SpanCandidate(
                                start=active_s,
                                end=active_e,
                                is_leading_continuation=active_leading_i,
                                is_trailing_boundary=False,
                                window_idx=window_idx,
                            )
                        )
                    active_s = s
                    active_e = e
                    active_cat = "PER"
                    active_leading_i = j == 0

            elif is_i_given:
                if (
                    active_s is not None
                    and active_e is not None
                    and active_cat == "GIVEN"
                    and _is_gap_whitespace_only(active_e, s)
                ):
                    active_e = e
                else:
                    if active_s is not None and active_e is not None:
                        candidates.append(
                            _SpanCandidate(
                                start=active_s,
                                end=active_e,
                                is_leading_continuation=active_leading_i,
                                is_trailing_boundary=False,
                                window_idx=window_idx,
                            )
                        )
                    active_s = s
                    active_e = e
                    active_cat = "GIVEN"
                    active_leading_i = j == 0

            elif is_i_sur:
                if (
                    active_s is not None
                    and active_e is not None
                    and active_cat == "SUR"
                    and _is_gap_whitespace_only(active_e, s)
                ):
                    active_e = e
                else:
                    if active_s is not None and active_e is not None:
                        candidates.append(
                            _SpanCandidate(
                                start=active_s,
                                end=active_e,
                                is_leading_continuation=active_leading_i,
                                is_trailing_boundary=False,
                                window_idx=window_idx,
                            )
                        )
                    active_s = s
                    active_e = e
                    active_cat = "SUR"
                    active_leading_i = j == 0

            else:
                # Outside token (O, TITLE, ADDRESS, CITY, EMAIL, etc.)
                if active_s is not None and active_e is not None:
                    candidates.append(
                        _SpanCandidate(
                            start=active_s,
                            end=active_e,
                            is_leading_continuation=active_leading_i,
                            is_trailing_boundary=False,
                            window_idx=window_idx,
                        )
                    )
                    active_s = None
                    active_e = None
                    active_cat = None
                    active_leading_i = False

        if active_s is not None and active_e is not None:
            candidates.append(
                _SpanCandidate(
                    start=active_s,
                    end=active_e,
                    is_leading_continuation=active_leading_i,
                    is_trailing_boundary=True,
                    window_idx=window_idx,
                )
            )

        return candidates

    def _extract_detections_from_predictions(
        self,
        original_text: str,
        normalized_text: str,
        token_offsets: list[tuple[int, int]],
        pred_indices: list[int],
    ) -> list[Detection]:
        """Convert BIO predictions and token offsets into Detection instances."""
        content_offsets: list[tuple[int, int]] = []
        content_preds: list[int] = []

        for offset, pred_id in zip(
            token_offsets, pred_indices[: len(token_offsets)], strict=True
        ):
            if offset == (0, 0):
                continue
            content_offsets.append(offset)
            content_preds.append(pred_id)

        candidates = self._extract_window_candidates(
            original_text=original_text,
            content_offsets=content_offsets,
            win_preds=content_preds,
            window_idx=0,
        )

        detections: list[Detection] = []
        for cand in candidates:
            trimmed = _trim_span_whitespace(cand.start, cand.end, original_text)
            if trimmed is not None:
                ts, te = trimmed
                detections.append(
                    Detection.from_texts(
                        type=_ENTITY_TYPE,
                        original_text=original_text,
                        normalized_text=normalized_text,
                        start=ts,
                        end=te,
                    )
                )
        detections.sort(key=lambda d: (d.start, d.end, d.type))
        return detections
