from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DATABASE_ROOT = REPO_ROOT / "database"
CURRENT_DATABASE_DIR = DATABASE_ROOT / "current"
HISTORY_DIR = DATABASE_ROOT / "history"
CHANGELOG_DIR = DATABASE_ROOT / "changelog"
