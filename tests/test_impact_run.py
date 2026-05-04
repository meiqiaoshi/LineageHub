"""Run-aware downstream impact tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.cli import main
from lineagehub.graph import analyze_run_impact
from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.store import MetadataStore

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LINEAGE_JSON = REPO_ROOT / "examples" / "sample_lineage.json"
SAMPLE_RUNS_JSON = REPO_ROOT / "examples" / "sample_runs.json"


def test_analyze_run_impact_transitive_downstream(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    load_runs_json(store, SAMPLE_RUNS_JSON)

    analysis = analyze_run_impact(store, "run_001")
    assert analysis.job_name == "clean_orders_job"
    assert analysis.status == "failed"
    assert analysis.output_datasets == ("clean_orders",)
    assert [r.name for r in analysis.affected] == ["mart_daily_sales", "sales_dashboard"]


def test_impact_run_cli_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "db.sqlite"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)
    load_runs_json(store, SAMPLE_RUNS_JSON)

    assert main(["--db", str(db), "impact-run", "run_001", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "run_impact"
    assert payload["run_id"] == "run_001"
    assert payload["affected_count"] == 2


def test_impact_run_unknown_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "db.sqlite"
    store = MetadataStore(db)
    load_lineage_json(store, SAMPLE_LINEAGE_JSON)

    assert main(["--db", str(db), "impact-run", "missing_run"]) == 1
    assert "Unknown run" in capsys.readouterr().err
