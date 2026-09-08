"""Internal shared utilities for Persian NER detectors.

This module provides sliding-window calculation, offset validation, and
deterministic candidate span merging shared across PyTorch and ONNX backends.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


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


def validate_tokenizer_offsets(
    token_offsets: Sequence[tuple[int, int]],
    text_len: int,
) -> None:
    """Validate that tokenizer character offsets are within bounds and monotonic.

    Args:
        token_offsets: List or sequence of (start, end) token character offsets.
        text_len: Length of the input text.

    Raises:
        ValueError: If offsets are out of bounds or non-monotonic.
    """
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


def merge_and_deduplicate_candidates(
    candidates: Sequence[_SpanCandidate],
    original_text: str,
) -> list[tuple[int, int]]:
    """Deduplicate and merge window candidates deterministically.

    Args:
        candidates: Candidate PERSON spans emitted across all sliding windows.
        original_text: Raw input text used to inspect boundary gaps.

    Returns:
        List of merged (start, end) character offsets sorted in ascending order.
    """
    if not candidates:
        return []

    sorted_candidates = sorted(candidates, key=lambda c: (c.start, c.end, c.window_idx))

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
        # 2) cand begins as an I-PER / continuation token
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
