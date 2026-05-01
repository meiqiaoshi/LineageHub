"""Tests for JSON lineage loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.loader import load_lineage_json
from lineagehub.store import MetadataStore


def test_load_sample_populates_edges(empty_store: MetadataStore, tmp_path: Path) -> None:
    sample = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"
    load_lineage_json(empty_store, sample)
    assert len(empty_store.list_datasets()) == 4
    assert len(empty_store.list_lineage_edges()) == 3


def test_loader_rejects_unknown_upstream_dataset(empty_store: MetadataStore, tmp_path: Path) -> None:
    payload = {
        "datasets": [{"name": "only", "type": "table"}],
        "jobs": [{"name": "j", "inputs": ["missing"], "outputs": ["only"]}],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown upstream"):
        load_lineage_json(empty_store, path)


def test_loader_rejects_bad_jobs_key(empty_store: MetadataStore, tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"datasets": [], "jobs": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="'jobs' must be a list"):
        load_lineage_json(empty_store, path)
