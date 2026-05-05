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

