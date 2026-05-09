"""CLI ``datasets show`` tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.cli import main
from lineagehub.loader import load_lineage_json
from lineagehub.store import MetadataStore

_SAMPLE_LINEAGE = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"


def test_datasets_show_raw_orders_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "show.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "datasets", "show", "raw_orders", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "dataset_show"
    assert payload["dataset"]["name"] == "raw_orders"
    assert payload["dataset"]["type"] == "table"
    assert payload["producer_jobs"] == []
    assert payload["consumer_jobs"] == ["clean_orders_job"]
    assert payload["upstream"] == []
    assert [d["name"] for d in payload["downstream"]] == [
        "clean_orders",
        "mart_daily_sales",
        "sales_dashboard",
    ]
    assert [d["distance"] for d in payload["downstream"]] == [1, 2, 3]


def test_datasets_show_sales_dashboard_no_downstream(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "show.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "datasets", "show", "sales_dashboard", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["downstream"] == []
    assert [d["name"] for d in payload["upstream"]] == [
        "mart_daily_sales",
        "clean_orders",
        "raw_orders",
    ]


def test_datasets_show_unknown_dataset(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "show.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "datasets", "show", "no_such_table"]) == 1
    assert "Unknown dataset" in capsys.readouterr().err


def test_datasets_show_text_contains_sections(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "show.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "datasets", "show", "mart_daily_sales"]) == 0
    out = capsys.readouterr().out
    assert "Dataset: mart_daily_sales" in out
    assert "Produced by:" in out
    assert "Consumed by:" in out
    assert "Upstream datasets:" in out
    assert "Downstream datasets:" in out
    assert "- sales_dashboard" in out
