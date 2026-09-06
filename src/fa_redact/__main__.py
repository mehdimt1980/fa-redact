"""Module entry point for python -m fa_redact."""

from __future__ import annotations

import sys

from fa_redact.cli import main

if __name__ == "__main__":
    sys.exit(main())
