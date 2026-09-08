"""OpenMed Persian ONNX INT4 models adapter for Phase 29 research.

This module is strictly isolated to research/ and is NOT imported by production code.
"""

from __future__ import annotations

from typing import Any

from research.evaluation import EntitySpan
from research.phase29_adapters.base import OPENMED_TO_CANONICAL


class OpenMedONNXAdapter:
    """Benchmark adapter for OpenMed Persian ONNX INT4 models.

    Phase 29 research wrapper implementing the publicly documented sliding-window
    and span postprocessing subset:
    - Sliding window with stride token processing
    - Character offset mapping from subword tokens
    - Leading/trailing whitespace trimming
    - Adjacent/overlapping same-canonical-type span merging
    - Duplicate span removal

    Unimplemented model-card recommendations (not evaluated in this benchmark):
    - Rule-assisted pre-filtering or regex overrides
    - Heuristic dictionary lookup corrections
    - Title cue-word post-patching
    """

    def __init__(
        self,
        model_id: str,
        display_name: str,
        mode: str = "wrapper",
        max_length: int = 256,
        stride: int = 128,
    ) -> None:
        self.model_id = model_id
        self.adapter_id = (
            f"openmed_{'tookabert' if 'tooka' in model_id.lower() else 'mbert'}_{mode}"
        )
        self.display_name = f"{display_name} ({mode.capitalize()})"
        self.mode = mode
        self.max_length = max_length
        self.stride = stride
        self.is_available = False
        self._load_error: str | None = None

        self._session: Any = None
        self._tokenizer: Any = None
        self._id2label: dict[int, str] = {}
        self._init_model()

    def _init_model(self) -> None:
        try:
            # Preload torch on Windows to satisfy onnxruntime DLL runtime dependencies
            try:
                import torch  # noqa: F401
            except ImportError:
                pass

            import onnxruntime as ort  # type: ignore[import-untyped]
            from huggingface_hub import hf_hub_download
            from transformers import (  # type: ignore[import-untyped]
                AutoConfig,
                AutoTokenizer,
            )

            try:
                cfg = AutoConfig.from_pretrained(self.model_id, local_files_only=True)
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.model_id, local_files_only=True
                )
                onnx_path = hf_hub_download(
                    repo_id=self.model_id,
                    filename="model.onnx",
                    local_files_only=True,
                )
            except Exception:
                cfg = AutoConfig.from_pretrained(self.model_id)
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
                onnx_path = hf_hub_download(
                    repo_id=self.model_id, filename="model.onnx"
                )

            self._id2label = {int(k): v for k, v in cfg.id2label.items()}
            self._session = ort.InferenceSession(
                onnx_path, providers=["CPUExecutionProvider"]
            )
            self.is_available = True
        except Exception as e:
            self.is_available = False
            self._load_error = f"{type(e).__name__}: {e}"

    def detect_spans(self, text: str) -> list[EntitySpan]:
        """Run token classification and return canonicalized postprocessed spans."""
        if not self.is_available or not text:
            return []

        raw_spans = self._infer_raw_spans(text)
        return self._postprocess_spans(text, raw_spans)

    def detect_raw_spans(self, text: str) -> list[EntitySpan]:
        """Return raw token-extracted spans without canonical taxonomy mapping."""
        if not self.is_available or not text:
            return []

        raw_spans = self._infer_raw_spans(text)
        seen: set[tuple[int, int, str]] = set()
        out: list[EntitySpan] = []
        for r_type, s, e in raw_spans:
            if 0 <= s < e <= len(text):
                key = (s, e, r_type)
                if key not in seen:
                    seen.add(key)
                    out.append(EntitySpan(start=s, end=e, type=r_type))
        return out

    def _infer_raw_spans(self, text: str) -> list[tuple[str, int, int]]:
        import numpy as np

        raw_spans: list[tuple[str, int, int]] = []
        enc_full = self._tokenizer(
            text,
            return_offsets_mapping=True,
            return_tensors="np",
            truncation=False,
        )
        total_tokens = len(enc_full["input_ids"][0])

        if total_tokens <= self.max_length:
            window_enc = self._tokenizer(
                text,
                return_offsets_mapping=True,
                return_tensors="np",
                truncation=True,
                padding="max_length",
                max_length=self.max_length,
            )
            raw_spans.extend(self._infer_window(text, window_enc))
        else:
            input_ids = enc_full["input_ids"][0]
            offset_mapping = enc_full["offset_mapping"][0]

            step = self.max_length - self.stride
            for start_idx in range(0, total_tokens, step):
                end_idx = min(start_idx + self.max_length, total_tokens)
                chunk_ids = input_ids[start_idx:end_idx]
                chunk_offsets = offset_mapping[start_idx:end_idx]

                pad_len = self.max_length - len(chunk_ids)
                if pad_len > 0:
                    padded_ids = np.pad(
                        chunk_ids,
                        (0, pad_len),
                        constant_values=self._tokenizer.pad_token_id,
                    )
                    padded_mask = np.pad(
                        np.ones(len(chunk_ids), dtype=np.int64),
                        (0, pad_len),
                        constant_values=0,
                    )
                else:
                    padded_ids = chunk_ids
                    padded_mask = np.ones(len(chunk_ids), dtype=np.int64)

                session_inputs = {inp.name for inp in self._session.get_inputs()}
                feed: dict[str, Any] = {
                    "input_ids": padded_ids.reshape(1, -1).astype(np.int64),
                    "attention_mask": padded_mask.reshape(1, -1).astype(np.int64),
                }
                if "token_type_ids" in session_inputs:
                    feed["token_type_ids"] = np.zeros(
                        (1, self.max_length), dtype=np.int64
                    )

                logits = self._session.run(None, feed)[0][0]
                preds = np.argmax(logits, axis=-1)

                window_spans = self._spans_from_tokens(
                    text, preds[: len(chunk_ids)], chunk_offsets
                )
                raw_spans.extend(window_spans)

                if end_idx >= total_tokens:
                    break

        return raw_spans

    def _infer_window(
        self, text: str, enc: dict[str, Any]
    ) -> list[tuple[str, int, int]]:
        import numpy as np

        offsets = enc.pop("offset_mapping")[0]
        session_inputs = {inp.name for inp in self._session.get_inputs()}
        feed = {k: v.astype(np.int64) for k, v in enc.items() if k in session_inputs}
        if "token_type_ids" in session_inputs and "token_type_ids" not in feed:
            feed["token_type_ids"] = np.zeros_like(feed["input_ids"])
        logits = self._session.run(None, feed)[0][0]
        preds = np.argmax(logits, axis=-1)
        return self._spans_from_tokens(text, preds, offsets)

    def _spans_from_tokens(
        self, text: str, preds: Any, offsets: Any
    ) -> list[tuple[str, int, int]]:
        spans: list[tuple[str, int, int]] = []
        cur_type: str | None = None
        cur_start: int | None = None
        cur_end: int | None = None

        for p, (s, e) in zip(preds, offsets, strict=False):
            if s == e:
                continue
            lbl = self._id2label.get(int(p), "O")

            if lbl == "O":
                if (
                    cur_type is not None
                    and cur_start is not None
                    and cur_end is not None
                ):
                    spans.append((cur_type, cur_start, cur_end))
                    cur_type = None
            elif lbl.startswith("B-"):
                if (
                    cur_type is not None
                    and cur_start is not None
                    and cur_end is not None
                ):
                    spans.append((cur_type, cur_start, cur_end))
                cur_type = lbl[2:]
                cur_start = s
                cur_end = e
            elif lbl.startswith("I-"):
                t_name = lbl[2:]
                if cur_type == t_name:
                    cur_end = e
                else:
                    if (
                        cur_type is not None
                        and cur_start is not None
                        and cur_end is not None
                    ):
                        spans.append((cur_type, cur_start, cur_end))
                    cur_type = t_name
                    cur_start = s
                    cur_end = e

        if cur_type is not None and cur_start is not None and cur_end is not None:
            spans.append((cur_type, cur_start, cur_end))

        return spans

    def _postprocess_spans(
        self, text: str, raw_spans: list[tuple[str, int, int]]
    ) -> list[EntitySpan]:
        if not raw_spans:
            return []

        if self.mode == "raw":
            seen_raw: set[tuple[int, int, str]] = set()
            out_raw: list[EntitySpan] = []
            for r_type, s, e in raw_spans:
                if 0 <= s < e <= len(text):
                    key = (s, e, r_type)
                    if key not in seen_raw:
                        seen_raw.add(key)
                        out_raw.append(EntitySpan(start=s, end=e, type=r_type))
            return out_raw

        # Mode: wrapper (whitespace trimming, canonical mapping, merge, dedup)
        trimmed_spans: list[tuple[str, int, int]] = []
        for r_type, s, e in raw_spans:
            if not (0 <= s < e <= len(text)):
                continue
            sub = text[s:e]
            l_trim = len(sub) - len(sub.lstrip())
            r_trim = len(sub) - len(sub.rstrip())
            ts = s + l_trim
            te = e - r_trim
            if ts < te:
                canon_type = OPENMED_TO_CANONICAL.get(r_type, r_type)
                trimmed_spans.append((canon_type, ts, te))

        trimmed_spans.sort(key=lambda x: (x[1], x[2]))

        # Merge overlapping / adjacent same-label spans
        merged: list[tuple[str, int, int]] = []
        for span in trimmed_spans:
            if not merged:
                merged.append(span)
                continue
            last_type, last_start, last_end = merged[-1]
            cur_type, cur_start, cur_end = span

            if cur_type == last_type and cur_start <= last_end + 1:
                merged[-1] = (last_type, last_start, max(last_end, cur_end))
            elif cur_start >= last_end:
                merged.append(span)
            else:
                if (cur_end - cur_start) > (last_end - last_start):
                    merged[-1] = span

        seen_keys: set[tuple[int, int, str]] = set()
        processed: list[EntitySpan] = []
        for c_type, s, e in merged:
            key = (s, e, c_type)
            if key not in seen_keys and 0 <= s < e <= len(text):
                seen_keys.add(key)
                processed.append(EntitySpan(start=s, end=e, type=c_type))

        return processed
