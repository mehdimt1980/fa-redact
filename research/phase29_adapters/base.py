"""Base benchmark adapter interface for Phase 29 Persian PII research.

This module is strictly isolated to research/ and is NOT imported by production code.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from research.evaluation import EntitySpan
from research.phase29_challenge_set import (
    OPENMED_TO_CANONICAL,
    canonicalize_gold_spans,
)

__all__ = [
    "BenchmarkAdapter",
    "OPENMED_TO_CANONICAL",
    "canonicalize_gold_spans",
]


@runtime_checkable
class BenchmarkAdapter(Protocol):
    """Protocol for PII detection adapters evaluated in Phase 29."""

    adapter_id: str
    display_name: str
    is_available: bool

    def detect_spans(self, text: str) -> list[EntitySpan]:
        """Detect entity spans in text and return exact character spans."""
        ...
