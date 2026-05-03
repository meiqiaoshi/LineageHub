"""CLI `--json` output tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.cli import main
from lineagehub.loader import load_lineage_json
from lineagehub.store import MetadataStore

_SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"


def _seed_db(tmp_path: Path) -> Path:
    db = tmp_path / "cli_json.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE)
    return db


def test_upstream_json_transitive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_db(tmp_path)
    assert main(["--db", str(db), "upstream", "mart_daily_sales", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "upstream"
    assert payload["depth"] == "all"
    assert [d["name"] for d in payload["datasets"]] == ["clean_orders", "raw_orders"]
    assert payload["datasets"][0]["distance"] == 1
    assert payload["datasets"][1]["distance"] == 2


def test_downstream_json_direct(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_db(tmp_path)
    assert (
        main(
            ["--db", str(db), "downstream", "raw_orders", "--depth", "direct", "--json"],
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["depth"] == "direct"
    assert payload["datasets"] == [{"name": "clean_orders", "distance": 1}]


def test_impact_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_db(tmp_path)
    assert main(["--db", str(db), "impact", "raw_orders", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "impact"
    assert payload["affected_count"] == 3
    assert payload["impact_type"] == "transitive_downstream"

