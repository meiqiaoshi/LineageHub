"""Default SQLite path for CLI and optional HTTP API (``LINEAGEHUB_DB`` env)."""

from __future__ import annotations

import os


def default_db_path() -> str:
    return os.environ.get("LINEAGEHUB_DB", "lineagehub.db")
