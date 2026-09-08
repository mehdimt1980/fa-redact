"""py-persian-tools adapter for Phase 29 research.

This module is strictly isolated to research/ and is NOT imported by production code.
"""

from __future__ import annotations

import re
from typing import Any

from research.evaluation import EntitySpan


class PersianToolsAdapter:
    """Benchmark adapter for py-persian-tools utility capabilities.

    NOTE ON NON-NATIVE CHARACTER OFFSETS:
    py-persian-tools (v0.0.11) does NOT provide a native free-text document PII span
    engine. Its card extraction function returns matched digit strings without
    character offsets. This adapter reconstructs character offsets via regex match
    searching. Results represent RESEARCH-RECONSTRUCTED / NON-NATIVE offsets.
    """

    adapter_id = "persian_tools_reconstructed"
    display_name = "py-persian-tools (v0.0.11) [Non-Native Reconstructed Offsets]"

    def __init__(self) -> None:
        self.is_available = False
        self._load_error: str | None = None
        self._card_mod: Any = None
        self._init_module()

    def _init_module(self) -> None:
        try:
            import persian_tools.bank.card_number as cn  # type: ignore[import-untyped]

            self._card_mod = cn
            self.is_available = True
        except Exception as e:
            self.is_available = False
            self._load_error = f"{type(e).__name__}: {e}"

    def detect_spans(self, text: str) -> list[EntitySpan]:
        """Attempt to extract entities using py-persian-tools and regex search."""
        if not self.is_available or not self._card_mod or not text:
            return []

        spans: list[EntitySpan] = []

        # 1. Bank card extraction
        try:
            results = self._card_mod.extract_card_numbers(text, check_validation=True)
            for res in results:
                base_str = res.get("base", "")
                if base_str:
                    for m in re.finditer(re.escape(base_str), text):
                        spans.append(
                            EntitySpan(start=m.start(), end=m.end(), type="BANK_CARD")
                        )
        except Exception as e:
            raise RuntimeError(f"PersianTools card extraction error: {e}") from e

        seen: set[tuple[int, int, str]] = set()
        deduped: list[EntitySpan] = []
        for sp in sorted(spans, key=lambda x: (x.start, x.end)):
            key = (sp.start, sp.end, sp.type)
            if key not in seen:
                seen.add(key)
                deduped.append(sp)

        return deduped
