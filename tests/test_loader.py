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


def test_load_sample_includes_catalog_metadata(empty_store: MetadataStore) -> None:
    sample = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"
    load_lineage_json(empty_store, sample)
    raw = empty_store.get_dataset_by_name("raw_orders")
    assert raw is not None
    assert raw.criticality == "low"
    assert raw.owner == "ingestion-team"
    assert "bronze" in (raw.tags or ())
    mart = empty_store.get_dataset_by_name("mart_daily_sales")
    assert mart is not None
    assert mart.criticality == "high"
    dash = empty_store.get_dataset_by_name("sales_dashboard")
    assert dash is not None
    assert dash.criticality == "critical"
    assert dash.system == "bi"


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


def test_loader_full_dataset_catalog_metadata(empty_store: MetadataStore, tmp_path: Path) -> None:
    payload = {
        "datasets": [
            {
                "name": "sales_dashboard",
                "type": "dashboard",
                "uri": "dashboard://sales/daily",
                "owner": "analytics",
                "description": "Daily sales dashboard used by business stakeholders.",
                "tags": ["sales", "executive"],
                "criticality": "high",
                "system": "bi",
            }
        ],
        "jobs": [],
    }
    path = tmp_path / "full.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    load_lineage_json(empty_store, path)
    ds = empty_store.get_dataset_by_name("sales_dashboard")
    assert ds is not None
    assert ds.dataset_type == "dashboard"
    assert ds.uri == "dashboard://sales/daily"
    assert ds.description == "Daily sales dashboard used by business stakeholders."
    assert ds.owner == "analytics"
    assert ds.tags == ("sales", "executive")
    assert ds.criticality == "high"
    assert ds.system == "bi"


def test_loader_criticality_case_insensitive(empty_store: MetadataStore, tmp_path: Path) -> None:
    payload = {
        "datasets": [{"name": "x", "criticality": "HIGH"}],
        "jobs": [],
    }
    path = tmp_path / "c.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    load_lineage_json(empty_store, path)
    assert empty_store.get_dataset_by_name("x").criticality == "high"


def test_loader_rejects_invalid_criticality(empty_store: MetadataStore, tmp_path: Path) -> None:
    payload = {
        "datasets": [{"name": "bad", "criticality": "urgent"}],
        "jobs": [],
    }
    path = tmp_path / "bad_crit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid criticality"):
        load_lineage_json(empty_store, path)


def test_loader_rejects_non_string_tags(empty_store: MetadataStore, tmp_path: Path) -> None:
    payload = {"datasets": [{"name": "t", "tags": [1, 2]}], "jobs": []}
    path = tmp_path / "bad_tags.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="'tags' must be a list of strings"):
        load_lineage_json(empty_store, path)
