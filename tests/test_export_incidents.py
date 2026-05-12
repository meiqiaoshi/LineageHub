"""CLI ``export incidents`` tests (requires Python 3.10+ for ``match``/``case`` in cli)."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

from lineagehub.analysis import incident_ranking, summarize_failed_runs
from lineagehub.loader import load_lineage_json, load_runs_json
from lineagehub.store import MetadataStore

_SAMPLE_LINEAGE = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"


def _main():
    if sys.version_info < (3, 10):
        pytest.skip("cli requires Python 3.10+")
    return importlib.import_module("lineagehub.cli").main


def _seed_db(tmp_path: Path) -> Path:
    db = tmp_path / "exp_inc.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
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
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    load_runs_json(store, runs_path)
    return db


def test_export_incidents_summary_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main = _main()
    db = _seed_db(tmp_path)
    assert main(["--db", str(db), "export", "incidents"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == summarize_failed_runs(MetadataStore(db))


def test_export_incidents_ranked_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main = _main()
    db = _seed_db(tmp_path)
    assert main(["--db", str(db), "export", "incidents", "--ranked"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == incident_ranking(MetadataStore(db))


def test_export_incidents_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main = _main()
    db = tmp_path / "empty_inc.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "export", "incidents"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "incident_summary"
    assert payload["incident_count"] == 0
    assert payload["incidents"] == []

    assert main(["--db", str(db), "export", "incidents", "--ranked"]) == 0
    ranked = json.loads(capsys.readouterr().out)
    assert ranked["query_type"] == "incident_ranking"
    assert ranked["incidents"] == []
