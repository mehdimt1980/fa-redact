"""Opt-in Persian Named Entity Recognition (NER) detector for PERSON entities."""

from __future__ import annotations

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
                or model labels are incompatible.
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
            import torch
            from transformers import (  # type: ignore[import-untyped]
                AutoModelForTokenClassification,
                AutoTokenizer,
            )
        except ImportError as e:
            raise ImportError(
                "PersianNERDetector requires optional 'ner' dependencies. "
                'Install them with: pip install "fa-redact[ner]"'
            ) from e

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
        torch_module: Any = None,
    ) -> PersianNERDetector:
        """Internal constructor for testing without loading files from disk."""
        if torch_module is None:
            try:
                import torch

                torch_module = torch
            except ImportError as e:
                raise ImportError("torch required for _create_for_test") from e

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
            and model_pos_limit > 0
        ):
            if max_length > model_pos_limit:
                raise ValueError(
                    f"Configured max_length ({max_length}) exceeds model "
                    f"positional capacity ({model_pos_limit})"
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

        Args:
            original_text: Raw input text.
            normalized_text: Position-preserving normalized text of identical length.

        Returns:
            Sequence of Detection instances with type="PERSON" sorted
            by (start, end, type).

        Raises:
            TypeError: If original_text or normalized_text is not a str.
            ValueError: If text lengths differ, input exceeds max_length,
                or tokenizer character offsets are structurally invalid.
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

        # Tokenize normalized_text without truncation to check sequence length
        full_encoding = self._tokenizer(
            normalized_text,
            return_offsets_mapping=True,
            add_special_tokens=True,
        )

        input_ids_list: list[int] = full_encoding["input_ids"]
        seq_len = len(input_ids_list)
        if seq_len > self._max_length:
            raise ValueError(
                f"Input tokenized length ({seq_len}) exceeds PersianNERDetector "
                f"max_length ({self._max_length}); long-document chunking is not "
                "implemented in Phase 21.2"
            )

        token_offsets: list[tuple[int, int]] = full_encoding["offset_mapping"]

        # Structural tokenizer offset safety audit
        text_len = len(normalized_text)
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

        # Prepare model forward inputs
        torch = self._torch
        input_ids = torch.tensor([input_ids_list], dtype=torch.long)
        attention_mask = torch.tensor(
            [full_encoding["attention_mask"]], dtype=torch.long
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

        # Reconstruct BIO entities into exact PERSON Detection spans
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
