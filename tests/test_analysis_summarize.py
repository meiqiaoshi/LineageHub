"""Incident summary analysis (summarize_failed_runs)."""

from __future__ import annotations

import json
from pathlib import Path

from lineagehub.analysis import summarize_failed_runs
from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.store import MetadataStore

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LINEAGE_JSON = REPO_ROOT / "examples" / "sample_lineage.json"


def test_summarize_no_matching_runs(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    out = summarize_failed_runs(store, status="failed")
    assert out["query_type"] == "incident_summary"
    assert out["incident_count"] == 0
    assert out["incidents"] == []


def test_summarize_one_failed_run_with_downstream(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    runs_path = tmp_path / "runs.json"
    runs_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "run_bad",
                        "job_name": "clean_orders_job",
                        "status": "failed",
                        "started_at": "2026-05-01T09:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    load_runs_json(store, runs_path)

    out = summarize_failed_runs(store)
    assert out["incident_count"] == 1
    inc = out["incidents"][0]
    assert inc["run_id"] == "run_bad"
    assert inc["job_name"] == "clean_orders_job"
    assert inc["output_datasets"] == ["clean_orders"]
    names = [a["name"] for a in inc["affected_datasets"]]
    assert names == ["mart_daily_sales", "sales_dashboard"]
    assert inc["affected_datasets"][0]["distance"] == 1
    assert inc["affected_datasets"][0]["source_output"] == "clean_orders"


def test_summarize_multiple_failed_runs(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    runs_path = tmp_path / "runs.json"
    runs_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "run_a",
                        "job_name": "clean_orders_job",
                        "status": "failed",
                        "started_at": "2026-05-01T09:00:00Z",
                    },
                    {
                        "run_id": "run_b",
                        "job_name": "daily_sales_job",
                        "status": "failed",
                        "started_at": "2026-05-01T10:00:00Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    load_runs_json(store, runs_path)

    out = summarize_failed_runs(store)
    assert out["incident_count"] == 2
    assert [i["run_id"] for i in out["incidents"]] == ["run_b", "run_a"]


def test_summarize_failed_run_no_downstream_impact(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    runs_path = tmp_path / "runs.json"
    runs_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "run_leaf",
                        "job_name": "sales_dashboard_refresh",
                        "status": "failed",
                        "started_at": "2026-05-01T11:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    load_runs_json(store, runs_path)

    out = summarize_failed_runs(store)
    assert out["incident_count"] == 1
    inc = out["incidents"][0]
    assert inc["output_datasets"] == ["sales_dashboard"]
    assert inc["affected_datasets"] == []
