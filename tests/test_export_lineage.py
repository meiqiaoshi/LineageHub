"""Tests for ``lineage_export_payload`` / lineage JSON export."""

from __future__ import annotations

import json
from pathlib import Path

from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.output import lineage_export_payload
from lineagehub.store import MetadataStore

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LINEAGE = REPO_ROOT / "examples" / "sample_lineage.json"
SAMPLE_RUNS = REPO_ROOT / "examples" / "sample_runs.json"


def test_lineage_export_empty_database(empty_store: MetadataStore) -> None:
    out = lineage_export_payload(empty_store)
    assert out["query_type"] == "lineage_export"
    assert out["datasets"] == []
    assert out["jobs"] == []
    assert out["lineage_edges"] == []
    assert out["runs"] == []


def test_lineage_export_includes_datasets_jobs_edges_runs(tmp_path: Path) -> None:
    db = tmp_path / "ex.db"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE)
    load_runs_json(store, SAMPLE_RUNS)
    out = lineage_export_payload(store)
    assert out["query_type"] == "lineage_export"
    assert len(out["datasets"]) == 4
    assert {d["name"] for d in out["datasets"]} == {
        "raw_orders",
        "clean_orders",
        "mart_daily_sales",
        "sales_dashboard",
    }
    assert len(out["jobs"]) == 3
    j = next(x for x in out["jobs"] if x["name"] == "clean_orders_job")
    assert j["inputs"] == ["raw_orders"]
    assert j["outputs"] == ["clean_orders"]
    assert len(out["lineage_edges"]) == 3
    assert {"upstream": "raw_orders", "downstream": "clean_orders", "job": "clean_orders_job"} in [
        dict(x) for x in out["lineage_edges"]
    ]
    assert len(out["runs"]) == 5
    ids = {r["run_id"] for r in out["runs"]}
    assert "run_001" in ids


def test_lineage_export_roundtrip_reloadable(tmp_path: Path) -> None:
    db = tmp_path / "ex.db"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE)
    load_runs_json(store, SAMPLE_RUNS)
    out = lineage_export_payload(store)
    lineage_part = {k: out[k] for k in ("datasets", "jobs", "lineage_edges")}
    runs_part = {"runs": out["runs"]}
    db2 = tmp_path / "ex2.db"
    s2 = MetadataStore(db2)
    p1 = tmp_path / "lineage.json"
    p2 = tmp_path / "runs.json"
    p1.write_text(json.dumps(lineage_part), encoding="utf-8")
    p2.write_text(json.dumps(runs_part), encoding="utf-8")
    load_lineage_json(s2, p1)
    load_runs_json(s2, p2)
    out2 = lineage_export_payload(s2)
    assert len(out2["datasets"]) == len(out["datasets"])
    assert len(out2["jobs"]) == len(out["jobs"])
    assert len(out2["lineage_edges"]) == len(out["lineage_edges"])
    assert len(out2["runs"]) == len(out["runs"])
