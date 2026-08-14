from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DATABASE_ROOT = REPO_ROOT / "database"
CURRENT_DATABASE_DIR = DATABASE_ROOT / "current"
HISTORY_DIR = DATABASE_ROOT / "history"
CHANGELOG_DIR = DATABASE_ROOT / "changelog"
# The raw HTML capture is ~60MB per run — far too large to commit weekly. It is
# kept out of the tracked database (gitignored, uploaded as a CI artifact) so that
# a failing parse still has its exact input available for diagnosis.
RAW_CAPTURE_DIR = REPO_ROOT / ".capture" / "artificial-analysis"
