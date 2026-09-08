"""ParsiKit adapter for Phase 29 research.

This module is strictly isolated to research/ and is NOT imported by production code.
"""

from __future__ import annotations

import re
from typing import Any

from research.evaluation import EntitySpan


class ParsiKitAdapter:
    """Benchmark adapter for ParsiKit utility capabilities.

    NOTE ON NON-NATIVE CHARACTER OFFSETS:
    ParsiKit does NOT provide a native free-text document PII span engine. Its
    extract_* methods return normalized string values (not source character offsets).
    This adapter reconstructs character offsets via regex match searching for offline
    comparison purposes only. Results represent RESEARCH-RECONSTRUCTED / NON-NATIVE
    offsets, not native document-level PII extraction performance.
    """

    adapter_id = "parsikit_reconstructed"
    display_name = "ParsiKit (v3.3.0) [Non-Native Reconstructed Offsets]"

    def __init__(self) -> None:
        self.is_available = False
        self._load_error: str | None = None
        self._text_mod: Any = None
        self._val_mod: Any = None
        self._init_module()

    def _init_module(self) -> None:
        try:
            import importlib.util
            import os
            import sys

            # Handle ParsiKit import
            for p in sys.path:
                target = os.path.join(p, "parsikit", "text.py")
                if os.path.exists(target):
                    spec_t = importlib.util.spec_from_file_location(
                        "parsikit_text", target
                    )
                    if spec_t and spec_t.loader:
                        self._text_mod = importlib.util.module_from_spec(spec_t)
                        spec_t.loader.exec_module(self._text_mod)
                        self.is_available = True
                        break
            if not self.is_available:
                import parsikit.text as pt  # type: ignore[import-untyped]

                self._text_mod = pt
                self.is_available = True
        except Exception as e:
            self.is_available = False
            self._load_error = f"{type(e).__name__}: {e}"

    def detect_spans(self, text: str) -> list[EntitySpan]:
        """Attempt to extract entities using ParsiKit extract_* and regex search."""
        if not self.is_available or not self._text_mod or not text:
            return []

        spans: list[EntitySpan] = []

        # 1. Mobile extraction
        if hasattr(self._text_mod, "extract_mobiles"):
            mobiles = self._text_mod.extract_mobiles(text)
            for mob in mobiles:
                for m in re.finditer(re.escape(mob), text):
                    spans.append(
                        EntitySpan(start=m.start(), end=m.end(), type="IR_MOBILE")
                    )

        # 2. National Code extraction
        if hasattr(self._text_mod, "extract_national_codes"):
            codes = self._text_mod.extract_national_codes(text)
            for code in codes:
                for m in re.finditer(re.escape(code), text):
                    spans.append(
                        EntitySpan(start=m.start(), end=m.end(), type="IR_NATIONAL_ID")
                    )

        # Deduplicate
        seen: set[tuple[int, int, str]] = set()
        deduped: list[EntitySpan] = []
        for sp in sorted(spans, key=lambda x: (x.start, x.end)):
            key = (sp.start, sp.end, sp.type)
            if key not in seen:
                seen.add(key)
                deduped.append(sp)

        return deduped
