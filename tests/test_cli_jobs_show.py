"""CLI ``jobs show`` tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.cli import main
from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.store import MetadataStore

_REPO = Path(__file__).resolve().parent.parent
_SAMPLE_LINEAGE = _REPO / "examples" / "sample_lineage.json"
_SAMPLE_RUNS = _REPO / "examples" / "sample_runs.json"


def test_jobs_show_json_with_latest_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "jobs_show.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    load_runs_json(store, _SAMPLE_RUNS)
    assert main(["--db", str(db), "jobs", "show", "clean_orders_job", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "job_show"
    assert payload["job"]["name"] == "clean_orders_job"
    assert payload["inputs"] == ["raw_orders"]
    assert payload["outputs"] == ["clean_orders"]
    assert payload["latest_run"] == {"run_id": "run_004", "status": "success"}
    assert payload["run_count"] == 2


def test_jobs_show_no_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "jobs_show.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "jobs", "show", "daily_sales_job", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["latest_run"] is None
    assert payload["run_count"] == 0
    assert payload["inputs"] == ["clean_orders"]
    assert payload["outputs"] == ["mart_daily_sales"]


def test_jobs_show_unknown_job(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "jobs_show.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "jobs", "show", "missing_job"]) == 1
    assert "Unknown job" in capsys.readouterr().err


def test_jobs_show_text_latest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "jobs_show.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    load_runs_json(store, _SAMPLE_RUNS)
    assert main(["--db", str(db), "jobs", "show", "clean_orders_job"]) == 0
    out = capsys.readouterr().out
    assert "Job: clean_orders_job" in out
    assert "Latest run:" in out
    assert "run_004" in out
    assert "Recent runs: 2" in out
