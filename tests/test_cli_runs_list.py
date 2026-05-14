from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.cli import main
from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.store import MetadataStore

_SAMPLE_LINEAGE = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"


def _seed_db_with_runs(tmp_path: Path) -> Path:
    db = tmp_path / "runs_cli.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)

    runs_path = tmp_path / "runs.json"
    runs_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "run_001",
                        "job_name": "clean_orders_job",
                        "status": "failed",
                        "started_at": "2026-05-01T10:00:00Z",
                        "ended_at": "2026-05-01T10:02:00Z",
                    },
                    {
                        "run_id": "run_002",
                        "job_name": "daily_sales_job",
                        "status": "success",
                        "started_at": "2026-05-01T11:00:00Z",
                        "ended_at": "2026-05-01T11:03:00Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    load_runs_json(store, runs_path)
    return db


def test_runs_list_text_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_db_with_runs(tmp_path)
    assert main(["--db", str(db), "runs", "list"]) == 0
    out = capsys.readouterr().out
    assert "Recent runs" in out
    assert "- run_002" in out
    assert "Job: daily_sales_job" in out


def test_runs_list_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_db_with_runs(tmp_path)
    assert main(["--db", str(db), "runs", "list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "runs_list"
    assert payload["filters"]["status"] is None
    assert [r["run_id"] for r in payload["runs"]] == ["run_002", "run_001"]


def test_runs_list_status_filter(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_db_with_runs(tmp_path)
    assert main(["--db", str(db), "runs", "list", "--status", "failed", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [r["run_id"] for r in payload["runs"]] == ["run_001"]


def test_runs_list_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "empty.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "runs", "list"]) == 0
    out = capsys.readouterr().out
    assert "(none)" in out


def _seed_db_two_runs_same_job(tmp_path: Path) -> Path:
    db = tmp_path / "runs_latest.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    runs_path = tmp_path / "runs_multi.json"
    runs_path.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "run_id": "run_old",
                        "job_name": "clean_orders_job",
                        "status": "failed",
                        "started_at": "2026-05-01T09:00:00Z",
                        "ended_at": "2026-05-01T09:03:00Z",
                    },
                    {
                        "run_id": "run_new",
                        "job_name": "clean_orders_job",
                        "status": "success",
                        "started_at": "2026-05-01T12:00:00Z",
                        "ended_at": "2026-05-01T12:02:00Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    load_runs_json(store, runs_path)
    return db


def test_runs_latest_text_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_db_two_runs_same_job(tmp_path)
    assert main(["--db", str(db), "runs", "latest", "--job", "clean_orders_job"]) == 0
    out = capsys.readouterr().out
    assert "Latest run for clean_orders_job" in out
    assert "Run: run_new" in out
    assert "Status: success" in out
    assert "Started: 2026-05-01T12:00:00Z" in out


def test_runs_latest_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_db_two_runs_same_job(tmp_path)
    assert main(["--db", str(db), "runs", "latest", "--job", "clean_orders_job", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "latest_run"
    assert payload["job_name"] == "clean_orders_job"
    assert payload["run"]["run_id"] == "run_new"
    assert payload["run"]["status"] == "success"


def test_runs_latest_json_no_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "no_runs.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "runs", "latest", "--job", "clean_orders_job", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run"] is None


def test_runs_latest_text_no_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "no_runs_text.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "runs", "latest", "--job", "clean_orders_job"]) == 0
    assert "(no runs)" in capsys.readouterr().out


def test_runs_show_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_db_with_runs(tmp_path)
    assert main(["--db", str(db), "runs", "show", "run_001", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "run_show"
    assert payload["run"]["run_id"] == "run_001"
    assert payload["run"]["job_name"] == "clean_orders_job"
    assert payload["run"]["status"] == "failed"


def test_runs_show_unknown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_db_with_runs(tmp_path)
    assert main(["--db", str(db), "runs", "show", "nope"]) == 1
    assert "Unknown run" in capsys.readouterr().err

