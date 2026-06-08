from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_ROOT = REPO_ROOT / "data"
CURRENT_DATA_DIR = DATA_ROOT / "current"
HISTORY_DIR = DATA_ROOT / "history"
CHANGELOG_DIR = DATA_ROOT / "changelog"
