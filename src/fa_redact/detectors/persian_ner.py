"""Opt-in Persian Named Entity Recognition (NER) detector for PERSON entities."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fa_redact.models import Detection

_ENTITY_TYPE: str = "PERSON"
_SUPPORTED_B_LABELS: frozenset[str] = frozenset(
    {"B_PER", "B-PER", "B_PERSON", "B-PERSON"}
)
_SUPPORTED_I_LABELS: frozenset[str] = frozenset(
    {"I_PER", "I-PER", "I_PERSON", "I-PERSON"}
)
_MAX_CREDIBLE_POSITION_LIMIT: int = 100_000


class PersianNERDetector:
    """Opt-in detector for Persian personal name (PERSON) entities.

    Uses an explicitly supplied local Hugging Face-compatible token-classification
    model directory to perform offline PERSON named-entity recognition. Operates
    on position-preserving normalized text and emits exact source-aligned Detection
    instances.
    """

    def __init__(
        self,
        model_path: str | Path,
        *,
        max_length: int = 512,
    ) -> None:
        """Initialize PersianNERDetector from a local model directory.

        Args:
            model_path: Local filesystem path to Hugging Face model directory.
            max_length: Maximum tokenized sequence length (positive integer).

        Raises:
            TypeError: If arguments are of incorrect types.
            ValueError: If max_length is non-positive, exceeds model position limits,
                exceeds tokenizer maximum length, or model labels are incompatible.
            FileNotFoundError: If model_path does not exist.
            NotADirectoryError: If model_path is not a directory.
            ImportError: If optional 'ner' dependencies are not installed.
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
            torch = importlib.import_module("torch")
            transformers = importlib.import_module("transformers")
        except ImportError as exc:
            raise ImportError(
                "PersianNERDetector requires optional dependencies. "
                'Install them with: pip install "fa-redact[ner]"'
            ) from exc

        AutoTokenizer = getattr(transformers, "AutoTokenizer", None)
        AutoModelForTokenClassification = getattr(
            transformers, "AutoModelForTokenClassification", None
        )
        if AutoTokenizer is None or AutoModelForTokenClassification is None:
            raise ImportError(
                "PersianNERDetector requires optional dependencies with "
                "AutoTokenizer and AutoModelForTokenClassification. "
                'Install them with: pip install "fa-redact[ner]"'
            )

        tokenizer = AutoTokenizer.from_pretrained(
            str(resolved_path),
            local_files_only=True,
            trust_remote_code=False,
        )
        if not getattr(tokenizer, "is_fast", False):
            raise ValueError(
                "PersianNERDetector requires a fast tokenizer (is_fast=True) "
                "with character offset mapping support"
            )

        model = AutoModelForTokenClassification.from_pretrained(
            str(resolved_path),
            local_files_only=True,
            trust_remote_code=False,
        )
        model.eval()

        self._init_from_components(
            model_path=resolved_path,
            tokenizer=tokenizer,
            model=model,
            max_length=max_length,
            torch_module=torch,
        )

    @classmethod
    def _create_for_test(
        cls,
        tokenizer: Any,
        model: Any,
        *,
        max_length: int = 512,
        torch_module: Any,
    ) -> PersianNERDetector:
        """Internal constructor for testing without loading files from disk."""
        instance = cls.__new__(cls)
        instance._init_from_components(
            model_path=Path("fake_test_model"),
            tokenizer=tokenizer,
            model=model,
            max_length=max_length,
            torch_module=torch_module,
        )
        return instance

    def _init_from_components(
        self,
        model_path: Path,
        tokenizer: Any,
        model: Any,
        max_length: int,
        torch_module: Any,
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

        # Check model positional capacity where reliably declared
        model_pos_limit = getattr(model.config, "max_position_embeddings", None)
        if (
            model_pos_limit is not None
            and isinstance(model_pos_limit, int)
            and not isinstance(model_pos_limit, bool)
            and 0 < model_pos_limit <= _MAX_CREDIBLE_POSITION_LIMIT
        ):
            if max_length > model_pos_limit:
                raise ValueError(
                    f"Configured max_length ({max_length}) exceeds model "
                    f"positional capacity ({model_pos_limit})"
                )

        # Check tokenizer model_max_length capacity where reliably declared
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

        # Validate model label configuration
        id2label_raw = getattr(model.config, "id2label", None)
        if not id2label_raw or not isinstance(id2label_raw, dict):
            raise ValueError("Model configuration missing required 'id2label' mapping")

        try:
            id2label: dict[int, str] = {int(k): str(v) for k, v in id2label_raw.items()}
        except (ValueError, TypeError) as e:
            raise ValueError(
                "Invalid non-numeric keys in model id2label mapping"
            ) from e

        b_per_ids: set[int] = set()
        i_per_ids: set[int] = set()

        for idx, label_str in id2label.items():
            norm_label = label_str.strip().upper().replace("_", "-")
            if norm_label in ("B-PER", "B-PERSON"):
                b_per_ids.add(idx)
            elif norm_label in ("I-PER", "I-PERSON"):
                i_per_ids.add(idx)

        if not b_per_ids:
            raise ValueError(
                f"Model at '{model_path}' missing required B-PER label configuration "
                f"(available labels: {sorted(set(id2label.values()))})"
            )
        if not i_per_ids:
            raise ValueError(
                f"Model at '{model_path}' missing required I-PER label configuration "
                f"(available labels: {sorted(set(id2label.values()))})"
            )

        self._model_path = model_path
        self._max_length = max_length
        self._tokenizer = tokenizer
        self._model = model
        self._b_per_ids = frozenset(b_per_ids)
        self._i_per_ids = frozenset(i_per_ids)
        self._id2label = id2label
        self._torch = torch_module

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        """Detect PERSON entities across source texts.

        For sequences that fit within `max_length`, runs a single model forward
        pass. For sequences exceeding `max_length`, runs deterministic overlapping
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

        # Tokenize normalized_text without truncation to inspect sequence length
        full_encoding = self._tokenizer(
            normalized_text,
            return_offsets_mapping=True,
            add_special_tokens=True,
        )

        input_ids_list: list[int] = full_encoding["input_ids"]
        token_offsets: list[tuple[int, int]] = full_encoding["offset_mapping"]
        text_len = len(normalized_text)

        # Structural tokenizer offset safety audit on full sequence
        prev_end = 0
        for start, end in token_offsets:
            if start == 0 and end == 0:
                continue
            if start < 0 or end > text_len or start > end:
                raise ValueError(
                    f"Tokenizer returned out-of-bounds character offsets "
                    f"({start}, {end}) for text length {text_len}"
                )
            if start < prev_end:
                raise ValueError(
                    f"Tokenizer returned non-monotonic character offsets "
                    f"({start}, {end}) after previous end {prev_end}"
                )
            prev_end = end

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

    def _detect_single_window(
        self,
        original_text: str,
        normalized_text: str,
        input_ids_list: list[int],
        token_offsets: list[tuple[int, int]],
        full_encoding: dict[str, Any],
    ) -> list[Detection]:
        """Run single forward pass for sequences fitting within max_length."""
        torch = self._torch
        input_ids = torch.tensor([input_ids_list], dtype=torch.long)
        attention_mask = torch.tensor(
            [full_encoding.get("attention_mask", [1] * len(input_ids_list))],
            dtype=torch.long,
        )

        model_kwargs: dict[str, Any] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in full_encoding:
            model_kwargs["token_type_ids"] = torch.tensor(
                [full_encoding["token_type_ids"]], dtype=torch.long
            )

        with torch.inference_mode():
            outputs = self._model(**model_kwargs)
            logits = outputs.logits[0]
            pred_indices: list[int] = torch.argmax(logits, dim=-1).tolist()

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

        torch = self._torch
        candidates: list[_SpanCandidate] = []

        for window_idx, (win_start, win_end) in enumerate(windows):
            win_content_ids = content_tokens[win_start:win_end]
            win_content_offsets = content_offsets[win_start:win_end]

            w_ids = [cls_token_id] + win_content_ids + [sep_token_id]
            w_mask = [1] * len(w_ids)

            input_ids = torch.tensor([w_ids], dtype=torch.long)
            attention_mask = torch.tensor([w_mask], dtype=torch.long)
            model_kwargs = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            }

            if raw_type_ids is not None:
                w_types = [0] + content_type_ids[win_start:win_end] + [0]
                model_kwargs["token_type_ids"] = torch.tensor(
                    [w_types], dtype=torch.long
                )

            with torch.inference_mode():
                outputs = self._model(**model_kwargs)
                logits = outputs.logits[0]
                pred_indices = torch.argmax(logits, dim=-1).tolist()

            # Content token predictions start at index 1
            win_preds = pred_indices[1 : 1 + len(win_content_ids)]
            active_s: int | None = None
            active_e: int | None = None
            active_leading_i = False

            for j, (offset, pred_id) in enumerate(
                zip(win_content_offsets, win_preds, strict=True)
            ):
                s, e = offset
                is_b = pred_id in self._b_per_ids
                is_i = pred_id in self._i_per_ids

                if is_b:
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
                    active_leading_i = False
                elif is_i:
                    if active_s is not None:
                        active_e = e
                    else:
                        active_s = s
                        active_e = e
                        active_leading_i = j == 0
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
                        active_s = None
                        active_e = None
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

        merged_spans = self._merge_and_deduplicate_candidates(candidates, original_text)

        detections: list[Detection] = [
            Detection.from_texts(
                type=_ENTITY_TYPE,
                original_text=original_text,
                normalized_text=normalized_text,
                start=s,
                end=e,
            )
            for s, e in merged_spans
        ]
        detections.sort(key=lambda d: (d.start, d.end, d.type))
        return detections

    def _merge_and_deduplicate_candidates(
        self,
        candidates: list[_SpanCandidate],
        original_text: str,
    ) -> list[tuple[int, int]]:
        """Deduplicate and merge window candidates deterministically."""
        if not candidates:
            return []

        sorted_candidates = sorted(
            candidates, key=lambda c: (c.start, c.end, c.window_idx)
        )

        merged: list[dict[str, Any]] = []

        for cand in sorted_candidates:
            if not merged:
                merged.append(
                    {
                        "start": cand.start,
                        "end": cand.end,
                        "window_idx": cand.window_idx,
                        "is_trailing_boundary": cand.is_trailing_boundary,
                    }
                )
                continue

            # 1. Exact duplicate or fully subsumed by existing span in merged
            subsumed = False
            for item in merged:
                if item["start"] <= cand.start and item["end"] >= cand.end:
                    subsumed = True
                    # If candidate ends exactly at boundary of existing span and is
                    # a trailing boundary with a later window index, update provenance
                    if (
                        cand.end == item["end"]
                        and cand.is_trailing_boundary
                        and cand.window_idx > item["window_idx"]
                    ):
                        item["window_idx"] = cand.window_idx
                        item["is_trailing_boundary"] = True
                    break

            if subsumed:
                continue

            curr = merged[-1]

            # 2. Candidate extends current span from exact same start
            if cand.start == curr["start"] and cand.end > curr["end"]:
                curr["end"] = cand.end
                curr["window_idx"] = cand.window_idx
                curr["is_trailing_boundary"] = cand.is_trailing_boundary
                continue

            # 3. Disjoint boundary split merge:
            # Require ALL four conditions:
            # 1) curr ended at a window boundary
            # 2) cand begins as an I-PER continuation
            # 3) cand is from immediately adjacent window (curr.window_idx + 1)
            # 4) gap between them is whitespace/ZWNJ only
            if cand.start >= curr["end"]:
                gap_text = original_text[curr["end"] : cand.start]
                gap_is_whitespace_or_zwnj_only = (
                    gap_text.strip(" \t\n\r\u200c\u200b\u200d") == ""
                )
                can_merge = (
                    curr["is_trailing_boundary"]
                    and cand.is_leading_continuation
                    and cand.window_idx == curr["window_idx"] + 1
                    and gap_is_whitespace_or_zwnj_only
                )
                if can_merge:
                    curr["end"] = cand.end
                    curr["window_idx"] = cand.window_idx
                    curr["is_trailing_boundary"] = cand.is_trailing_boundary
                    continue

            # In all other cases (e.g. partial overlap without containment,
            # distinct adjacent B-PER, non-adjacent window, or gap with non-whitespace):
            # preserve separate evidence span!
            merged.append(
                {
                    "start": cand.start,
                    "end": cand.end,
                    "window_idx": cand.window_idx,
                    "is_trailing_boundary": cand.is_trailing_boundary,
                }
            )

        return [(int(item["start"]), int(item["end"])) for item in merged]

    def _extract_detections_from_predictions(
        self,
        original_text: str,
        normalized_text: str,
        token_offsets: list[tuple[int, int]],
        pred_indices: list[int],
    ) -> list[Detection]:
        """Convert BIO predictions and token offsets into Detection instances."""
        detections: list[Detection] = []
        active_start: int | None = None
        active_end: int | None = None

        def _flush_active() -> None:
            nonlocal active_start, active_end
            if active_start is not None and active_end is not None:
                detections.append(
                    Detection.from_texts(
                        type=_ENTITY_TYPE,
                        original_text=original_text,
                        normalized_text=normalized_text,
                        start=active_start,
                        end=active_end,
                    )
                )
                active_start = None
                active_end = None

        for offset, pred_id in zip(
            token_offsets, pred_indices[: len(token_offsets)], strict=True
        ):
            start, end = offset
            if start == end:  # Special token
                continue

            is_b = pred_id in self._b_per_ids
            is_i = pred_id in self._i_per_ids

            if is_b:
                _flush_active()
                active_start = start
                active_end = end
            elif is_i:
                if active_start is not None:
                    active_end = end
                else:
                    # Deterministic recovery for leading I-PER token
                    active_start = start
                    active_end = end
            else:
                _flush_active()

        _flush_active()
        detections.sort(key=lambda d: (d.start, d.end, d.type))
        return detections


class _SpanCandidate:
    """Internal candidate PERSON span emitted from a window forward pass."""

    __slots__ = (
        "start",
        "end",
        "is_leading_continuation",
        "is_trailing_boundary",
        "window_idx",
    )

    def __init__(
        self,
        start: int,
        end: int,
        is_leading_continuation: bool,
        is_trailing_boundary: bool,
        window_idx: int,
    ) -> None:
        self.start = start
        self.end = end
        self.is_leading_continuation = is_leading_continuation
        self.is_trailing_boundary = is_trailing_boundary
        self.window_idx = window_idx
