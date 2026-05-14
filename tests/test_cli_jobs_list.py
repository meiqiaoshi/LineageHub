"""CLI ``jobs list`` tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.cli import main
from lineagehub.loader import load_lineage_json
from lineagehub.store import MetadataStore

_SAMPLE_LINEAGE = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"


def test_jobs_list_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "jobs_cli.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "jobs", "list"]) == 0
    out = capsys.readouterr().out
    assert "Jobs:" in out
    assert "- clean_orders_job" in out
    assert "Description: (none)" in out
    assert "System: (none)" in out


def test_jobs_list_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "jobs_cli.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "jobs", "list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "jobs_list"
    assert payload["count"] == 3
    names = {j["name"] for j in payload["jobs"]}
    assert names == {"clean_orders_job", "daily_sales_job", "sales_dashboard_refresh"}
    for j in payload["jobs"]:
        assert "description" in j
        assert "system" in j
        assert j["system"] is None


def test_jobs_list_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "empty_jobs.db"
    MetadataStore(db).init_schema()
    assert main(["--db", str(db), "jobs", "list"]) == 0
    assert "(none)" in capsys.readouterr().out

    assert main(["--db", str(db), "jobs", "list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 0
    assert payload["jobs"] == []
