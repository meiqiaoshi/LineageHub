"""CLI ``graph cycles`` tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lineagehub.cli import main
from lineagehub.loader import load_lineage_json
from lineagehub.models import Dataset, LineageEdge
from lineagehub.store import MetadataStore

_SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_lineage.json"


def test_graph_cycles_no_cycles_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "gc.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE)
    assert main(["--db", str(db), "graph", "cycles"]) == 0
    assert "No lineage cycles detected." in capsys.readouterr().out


def test_graph_cycles_no_cycles_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "gc.db"
    store = MetadataStore(db)
    load_lineage_json(store, _SAMPLE)
    assert main(["--db", str(db), "graph", "cycles", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_type"] == "graph_cycles"
    assert payload["cycle_count"] == 0
    assert payload["cycles"] == []


def test_graph_cycles_one_cycle_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "gc.db"
    store = MetadataStore(db)
    a = store.upsert_dataset(Dataset(name="A"))
    b = store.upsert_dataset(Dataset(name="B"))
    store.insert_lineage_edge(LineageEdge(upstream_dataset_id=a, downstream_dataset_id=b, job_id=None))
    store.insert_lineage_edge(LineageEdge(upstream_dataset_id=b, downstream_dataset_id=a, job_id=None))
    assert main(["--db", str(db), "graph", "cycles"]) == 0
    out = capsys.readouterr().out
    assert "Detected lineage cycles:" in out
    assert "A -> B -> A" in out


def test_graph_cycles_one_cycle_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "gc.db"
    store = MetadataStore(db)
    a = store.upsert_dataset(Dataset(name="A"))
    b = store.upsert_dataset(Dataset(name="B"))
    store.insert_lineage_edge(LineageEdge(upstream_dataset_id=a, downstream_dataset_id=b, job_id=None))
    store.insert_lineage_edge(LineageEdge(upstream_dataset_id=b, downstream_dataset_id=a, job_id=None))
    assert main(["--db", str(db), "graph", "cycles", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cycle_count"] == 1
    assert payload["cycles"] == [["A", "B", "A"]]
