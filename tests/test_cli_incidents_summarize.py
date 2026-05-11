"""CLI ``incidents summarize`` tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.cli import main
from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.store import MetadataStore

_SAMPLE_LINEAGE = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"


def _seed_lineage_and_runs(tmp_path: Path, runs: list[dict]) -> Path:
    db = tmp_path / "incidents.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    path = tmp_path / "runs.json"
    path.write_text(json.dumps({"runs": runs}, indent=2), encoding="utf-8")
    load_runs_json(store, path)
    return db


def test_incidents_summarize_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_lineage_and_runs(
        tmp_path,
        [
            {
                "run_id": "run_bad",
                "job_name": "clean_orders_job",
                "status": "failed",
                "started_at": "2026-05-01T09:00:00Z",
            },
        ],
    )
    assert main(["--db", str(db), "incidents", "summarize"]) == 0
    out = capsys.readouterr().out
    assert "Incident summary for failed runs" in out
    assert "Run: run_bad" in out
    assert "Output datasets:" in out
    assert "- clean_orders" in out
    assert "Affected downstream datasets:" in out
    assert "- mart_daily_sales (distance: 1)" in out


def test_incidents_summarize_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_lineage_and_runs(
        tmp_path,
        [
            {
                "run_id": "run_bad",
                "job_name": "clean_orders_job",
                "status": "failed",
                "started_at": "2026-05-01T09:00:00Z",
            },
        ],
    )
    assert main(["--db", str(db), "incidents", "summarize", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "incident_summary"
    assert payload["scoring_method"] == "criticality_weighted"
    assert payload["incident_count"] == 1
    assert payload["incidents"][0]["run_id"] == "run_bad"
    assert payload["incidents"][0]["scoring_method"] == "criticality_weighted"


def test_incidents_summarize_no_incidents(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "empty_runs.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "incidents", "summarize"]) == 0
    assert "(none)" in capsys.readouterr().out

    assert main(["--db", str(db), "incidents", "summarize", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["incident_count"] == 0
    assert payload["incidents"] == []


def test_incidents_summarize_limit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_lineage_and_runs(
        tmp_path,
        [
            {
                "run_id": "run_old",
                "job_name": "clean_orders_job",
                "status": "failed",
                "started_at": "2026-05-01T09:00:00Z",
            },
            {
                "run_id": "run_mid",
                "job_name": "daily_sales_job",
                "status": "failed",
                "started_at": "2026-05-01T10:00:00Z",
            },
            {
                "run_id": "run_new",
                "job_name": "sales_dashboard_refresh",
                "status": "failed",
                "started_at": "2026-05-01T11:00:00Z",
            },
        ],
    )
    assert main(["--db", str(db), "incidents", "summarize", "--limit", "2", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["incident_count"] == 2
    assert [i["run_id"] for i in payload["incidents"]] == ["run_new", "run_mid"]
