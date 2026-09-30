#!/usr/bin/env python3
"""Repo wrapper for the terminal show — the implementation now ships in the wheel.

    python scripts/demo.py [--fast] [--keep]

The real code is ``rag_ai_scientist/demo.py`` so that ``ras demo`` and pip
users get the same show. This wrapper only forwards argv.
"""

from __future__ import annotations

import sys

from rag_ai_scientist.demo import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
