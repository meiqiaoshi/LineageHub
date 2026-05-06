"""Incident summary analysis (summarize_failed_runs)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.analysis import summarize_failed_runs
from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.models import RunImpactAnalysis, RunImpactRow
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
    assert out["max_blast_radius_score"] == 0
    assert out["highest_severity"] == "none"


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
    assert inc["blast_radius_score"] == 2
    assert inc["severity"] == "low"
    assert out["max_blast_radius_score"] == 2
    assert out["highest_severity"] == "low"


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
    assert out["incidents"][0]["blast_radius_score"] == 1
    assert out["incidents"][0]["severity"] == "low"
    assert out["incidents"][1]["blast_radius_score"] == 2
    assert out["max_blast_radius_score"] == 2
    assert out["highest_severity"] == "low"


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
    assert inc["blast_radius_score"] == 0
    assert inc["severity"] == "none"
    assert out["max_blast_radius_score"] == 0
    assert out["highest_severity"] == "none"


def test_summarize_blast_radius_medium_severity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "db.sqlite"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    runs_path = tmp_path / "runs.json"
    runs_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "run_med",
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

    affected = tuple(
        RunImpactRow(name=f"d{i}", distance=1, source_output="clean_orders") for i in range(4)
    )

    def fake_impact(_store: MetadataStore, ext: str) -> RunImpactAnalysis:
        return RunImpactAnalysis(
            external_run_id=ext,
            job_name="clean_orders_job",
            status="failed",
            error_message=None,
            output_datasets=("clean_orders",),
            affected=affected,
        )

    monkeypatch.setattr("lineagehub.analysis.analyze_run_impact", fake_impact)

    out = summarize_failed_runs(store)
    assert out["incidents"][0]["blast_radius_score"] == 4
    assert out["incidents"][0]["severity"] == "medium"
    assert out["max_blast_radius_score"] == 4
    assert out["highest_severity"] == "medium"


def test_summarize_blast_radius_low_boundary_score_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "db.sqlite"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    runs_path = tmp_path / "runs.json"
    runs_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "run_one",
                        "job_name": "daily_sales_job",
                        "status": "failed",
                        "started_at": "2026-05-01T10:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    load_runs_json(store, runs_path)

    affected = (RunImpactRow(name="only_ds", distance=1, source_output="mart_daily_sales"),)

    def fake_impact(_store: MetadataStore, ext: str) -> RunImpactAnalysis:
        return RunImpactAnalysis(
            external_run_id=ext,
            job_name="daily_sales_job",
            status="failed",
            error_message=None,
            output_datasets=("mart_daily_sales",),
            affected=affected,
        )

    monkeypatch.setattr("lineagehub.analysis.analyze_run_impact", fake_impact)

    out = summarize_failed_runs(store)
    assert out["incidents"][0]["blast_radius_score"] == 1
    assert out["incidents"][0]["severity"] == "low"


def test_summarize_blast_radius_high_severity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "db.sqlite"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    runs_path = tmp_path / "runs.json"
    runs_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "run_hi",
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

    affected = tuple(
        RunImpactRow(name=f"n{i}", distance=1, source_output="clean_orders") for i in range(6)
    )

    def fake_impact(_store: MetadataStore, ext: str) -> RunImpactAnalysis:
        return RunImpactAnalysis(
            external_run_id=ext,
            job_name="clean_orders_job",
            status="failed",
            error_message=None,
            output_datasets=("clean_orders",),
            affected=affected,
        )

    monkeypatch.setattr("lineagehub.analysis.analyze_run_impact", fake_impact)

    out = summarize_failed_runs(store)
    assert out["incidents"][0]["blast_radius_score"] == 6
    assert out["incidents"][0]["severity"] == "high"
    assert out["max_blast_radius_score"] == 6
    assert out["highest_severity"] == "high"
