"""Shared test configuration."""

from __future__ import annotations

import os
from pathlib import Path

# Force a known environment BEFORE any wolf_trading_os import caches settings.
os.environ.setdefault("WTOS_ENVIRONMENT", "test")
os.environ.setdefault("WTOS_LOG_FORMAT", "json")

FIXTURES = Path(__file__).parent / "fixtures"
