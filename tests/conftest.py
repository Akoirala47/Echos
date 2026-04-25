"""Ensure the project root is on sys.path so `scout.*` imports work
regardless of how pytest is invoked."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
