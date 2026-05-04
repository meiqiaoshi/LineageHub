"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from lineagehub.loader import load_lineage_json
from lineagehub.store import MetadataStore

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LINEAGE_JSON = REPO_ROOT / "examples" / "sample_lineage.json"
SAMPLE_RUNS_JSON = REPO_ROOT / "examples" / "sample_runs.json"


@pytest.fixture
def empty_store(tmp_path: Path) -> MetadataStore:
    db = tmp_path / "meta.db"
    store = MetadataStore(db)
    store.init_schema()
    return store


@pytest.fixture
def sample_store(tmp_path: Path) -> MetadataStore:
    db = tmp_path / "sample.db"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    return store
