"""CLI ``incidents rank`` tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.cli import main
from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.store import MetadataStore

_SAMPLE_LINEAGE = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"


def _seed_lineage_and_runs(tmp_path: Path, runs: list[dict]) -> Path:
    db = tmp_path / "incidents_rank.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    path = tmp_path / "runs.json"
    path.write_text(json.dumps({"runs": runs}, indent=2), encoding="utf-8")
    load_runs_json(store, path)
    return db


def test_incidents_rank_order(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_lineage_and_runs(
        tmp_path,
        [
            {
                "run_id": "run_leaf",
                "job_name": "sales_dashboard_refresh",
                "status": "failed",
                "started_at": "2026-05-01T11:00:00Z",
            },
            {
                "run_id": "run_mid",
                "job_name": "daily_sales_job",
                "status": "failed",
                "started_at": "2026-05-01T10:00:00Z",
            },
            {
                "run_id": "run_big",
                "job_name": "clean_orders_job",
                "status": "failed",
                "started_at": "2026-05-01T09:00:00Z",
            },
        ],
    )
    assert main(["--db", str(db), "incidents", "rank"]) == 0
    out = capsys.readouterr().out
    # clean_orders_job affects 2 downstream, daily_sales_job affects 1, dashboard_refresh affects 0
    first = out.splitlines()[2]
    assert "run_big" in first


def test_incidents_rank_json_shape(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_lineage_and_runs(
        tmp_path,
        [
            {
                "run_id": "run_mid",
                "job_name": "daily_sales_job",
                "status": "failed",
                "started_at": "2026-05-01T10:00:00Z",
            },
            {
                "run_id": "run_big",
                "job_name": "clean_orders_job",
                "status": "failed",
                "started_at": "2026-05-01T09:00:00Z",
            },
        ],
    )
    assert main(["--db", str(db), "incidents", "rank", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "incident_ranking"
    assert payload["ranking_method"] == "affected_dataset_count"
    assert payload["incidents"][0]["rank"] == 1
    assert payload["incidents"][0]["affected_count"] == payload["incidents"][0]["blast_radius_score"]


def test_incidents_rank_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "empty.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "incidents", "rank"]) == 0
    assert "(none)" in capsys.readouterr().out

    assert main(["--db", str(db), "incidents", "rank", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["incidents"] == []


def test_incidents_rank_limit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_lineage_and_runs(
        tmp_path,
        [
            {
                "run_id": "run_leaf",
                "job_name": "sales_dashboard_refresh",
                "status": "failed",
                "started_at": "2026-05-01T11:00:00Z",
            },
            {
                "run_id": "run_mid",
                "job_name": "daily_sales_job",
                "status": "failed",
                "started_at": "2026-05-01T10:00:00Z",
            },
            {
                "run_id": "run_big",
                "job_name": "clean_orders_job",
                "status": "failed",
                "started_at": "2026-05-01T09:00:00Z",
            },
        ],
    )
    assert main(["--db", str(db), "incidents", "rank", "--limit", "2", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["incidents"]) == 2

