"""Module entry point so ``python -m failbench`` works from a plain checkout.

This module intentionally contains almost no logic: the CLI lives in
:mod:`failbench.cli` and every sibling module is imported lazily from there.
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
