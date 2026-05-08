"""CLI ``datasets list`` tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.cli import main
from lineagehub.loader import load_lineage_json
from lineagehub.store import MetadataStore

_SAMPLE_LINEAGE = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"


def test_datasets_list_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "cat.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "datasets", "list"]) == 0
    out = capsys.readouterr().out
    assert "Datasets:" in out
    assert "- raw_orders" in out
    assert "Type: table" in out
    assert "URI: duckdb://warehouse/raw_orders" in out


def test_datasets_list_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "cat.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE_LINEAGE)
    assert main(["--db", str(db), "datasets", "list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "datasets_list"
    assert payload["count"] == 4
    names = {d["name"] for d in payload["datasets"]}
    assert names == {"raw_orders", "clean_orders", "mart_daily_sales", "sales_dashboard"}
    raw = next(d for d in payload["datasets"] if d["name"] == "raw_orders")
    assert raw["type"] == "table"
    assert "duckdb" in (raw["uri"] or "")


def test_datasets_list_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "empty.db"
    MetadataStore(db).init_schema()
    assert main(["--db", str(db), "datasets", "list"]) == 0
    assert "(none)" in capsys.readouterr().out

    assert main(["--db", str(db), "datasets", "list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 0
    assert payload["datasets"] == []
